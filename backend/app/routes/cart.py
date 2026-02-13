"""Cart, coupon, and checkout endpoints with intentional business logic vulnerabilities.

Provides cart CRUD, coupon application, and checkout flow for the e-commerce
storefront. Contains deliberate vulnerabilities:
  - Float quantity truncation (CWE-681) on PATCH
  - IDOR via JWT trust on PATCH/DELETE (CWE-639)
  - Race condition on coupon redemption — TOCTOU (CWE-362)
  - Coupon stacking without limits (CWE-840)
  - Negative total via unclamped discounts (CWE-840)
  - Client-supplied exchange_rate on checkout (CWE-20)
  - Stale unit_price from cart instead of live DB prices (CWE-472)
"""

from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.middleware.auth_middleware import get_current_user
from app.models.cart import CartItem
from app.models.coupon import Coupon, CouponUse
from app.models.order import Order, OrderItem
from app.models.product import Product
from app.schemas.cart import (
    AddCartItemRequest,
    ApplyCouponRequest,
    CartItemResponse,
    CartResponse,
    CheckoutRequest,
    CheckoutResponse,
    CouponAppliedResponse,
    UpdateCartItemRequest,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_cart_items_with_products(
    user_id: int,
    db: AsyncSession,
) -> list[CartItem]:
    """Fetch all cart items for a user with eagerly loaded product data.

    Args:
        user_id: The authenticated user's ID.
        db: Async database session.

    Returns:
        List of CartItem ORM instances with product relationship loaded.
    """
    result = await db.execute(
        select(CartItem)
        .where(CartItem.user_id == user_id)
        .options(selectinload(CartItem.product))
        .order_by(CartItem.added_at)
    )
    return list(result.scalars().all())


def _calculate_cart_subtotal(items: list[CartItem]) -> Decimal:
    """Sum up item quantities times unit prices.

    Args:
        items: Cart items with unit_price populated.

    Returns:
        Total subtotal before any coupon discounts.
    """
    total = Decimal("0")
    for item in items:
        total += item.quantity * item.unit_price
    return total


async def _get_applied_discounts(
    user_id: int,
    subtotal: Decimal,
    db: AsyncSession,
) -> tuple[Decimal, list[str]]:
    """Calculate total discount from all coupons the user has redeemed.

    VULN: CWE-840 — No limit on how many DIFFERENT coupons can be stacked.
    VULN: CWE-840 — No clamp to min 0; total can go negative = store credit.

    Args:
        user_id: The authenticated user's ID.
        subtotal: Cart subtotal before discounts.
        db: Async database session.

    Returns:
        Tuple of (total_discount_amount, list_of_coupon_codes).
    """
    # Fetch all coupon uses for this user, joining the coupon details
    result = await db.execute(
        select(CouponUse)
        .where(CouponUse.user_id == user_id)
        .options(selectinload(CouponUse.coupon))
        .order_by(CouponUse.used_at)
    )
    coupon_uses = result.scalars().all()

    total_discount = Decimal("0")
    coupon_codes: list[str] = []

    # VULN: Coupon Stacking - Each coupon_use adds its discount independently.
    # No check prevents accumulating discounts from DIFFERENT coupons beyond 100%.
    # VULN: Negative Total - discount is never clamped, so total can go negative.
    # Ref: https://hackerone.com/reports/894543
    for use in coupon_uses:
        coupon = use.coupon
        if not coupon.is_active:
            continue

        if coupon.discount_type == "percent":
            total_discount += subtotal * (coupon.discount_value / Decimal("100"))
        else:
            total_discount += coupon.discount_value

        coupon_codes.append(coupon.code)

    return total_discount, coupon_codes


def _build_cart_item_response(item: CartItem) -> CartItemResponse:
    """Build a CartItemResponse from an ORM CartItem with loaded product.

    Args:
        item: CartItem ORM instance with product relationship loaded.

    Returns:
        Pydantic CartItemResponse with product_name and computed subtotal.
    """
    return CartItemResponse(
        id=item.id,
        product_id=item.product_id,
        product_name=item.product.name,
        quantity=item.quantity,
        unit_price=item.unit_price,
        subtotal=item.quantity * item.unit_price,
        added_at=item.added_at,
    )


# ---------------------------------------------------------------------------
# GET /api/cart — View cart (secure)
# ---------------------------------------------------------------------------


@router.get("", response_model=CartResponse)
async def get_cart(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> CartResponse:
    """Retrieve the authenticated user's shopping cart.

    Fetches all cart items with product details, calculates subtotal,
    applies any redeemed coupons, and returns the full cart view.
    Uses parameterized ORM queries (secure).

    Args:
        db: Database session (injected).
        current_user: Authenticated user from JWT (injected).

    Returns:
        Full cart with items, subtotal, discount, total, and applied coupons.
    """
    items = await _get_cart_items_with_products(current_user["user_id"], db)
    subtotal = _calculate_cart_subtotal(items)
    discount, coupon_codes = await _get_applied_discounts(
        current_user["user_id"], subtotal, db
    )

    return CartResponse(
        items=[_build_cart_item_response(i) for i in items],
        subtotal=subtotal,
        discount=discount,
        total=subtotal - discount,
        applied_coupons=coupon_codes,
    )


# ---------------------------------------------------------------------------
# POST /api/cart/items — Add item to cart (secure)
# ---------------------------------------------------------------------------


@router.post(
    "/items",
    response_model=CartItemResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_cart_item(
    data: AddCartItemRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> CartItemResponse:
    """Add a product to the cart or increment quantity if already present.

    This is the SECURE add path: quantity is validated as ``int > 0``
    by the schema, and ``unit_price`` is fetched from the database
    (not accepted from the client).

    Args:
        data: Product ID and quantity to add.
        db: Database session (injected).
        current_user: Authenticated user from JWT (injected).

    Returns:
        The created or updated cart item.

    Raises:
        HTTPException: 404 if product not found/inactive/out of stock.
    """
    # Validate product exists, is active, and has stock
    result = await db.execute(
        select(Product).where(
            Product.id == data.product_id,
            Product.is_active.is_(True),
        )
    )
    product = result.scalar_one_or_none()

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found or inactive",
        )

    if product.stock <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Product is out of stock",
        )

    # UPSERT: if item already in cart, increment quantity
    existing_result = await db.execute(
        select(CartItem)
        .where(
            CartItem.user_id == current_user["user_id"],
            CartItem.product_id == data.product_id,
        )
        .options(selectinload(CartItem.product))
    )
    existing_item = existing_result.scalar_one_or_none()

    if existing_item:
        existing_item.quantity += data.quantity
        await db.commit()
        await db.refresh(existing_item, attribute_names=["product"])
        return _build_cart_item_response(existing_item)

    # Fetch price from DB — not from client request (secure)
    cart_item = CartItem(
        user_id=current_user["user_id"],
        product_id=data.product_id,
        quantity=data.quantity,
        unit_price=product.price,
    )
    db.add(cart_item)

    # Handle race condition: two concurrent requests may both pass the
    # existing-item check above, but UNIQUE(user_id, product_id) rejects
    # the second INSERT — retry as quantity increment
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        retry_result = await db.execute(
            select(CartItem)
            .where(
                CartItem.user_id == current_user["user_id"],
                CartItem.product_id == data.product_id,
            )
            .options(selectinload(CartItem.product))
        )
        existing_item = retry_result.scalar_one()
        existing_item.quantity += data.quantity
        await db.commit()
        await db.refresh(existing_item, attribute_names=["product"])
        return _build_cart_item_response(existing_item)

    await db.refresh(cart_item, attribute_names=["product"])

    return _build_cart_item_response(cart_item)


# ---------------------------------------------------------------------------
# PATCH /api/cart/items/{item_id} — Update quantity (VULN: Float + IDOR)
# ---------------------------------------------------------------------------


@router.patch("/items/{item_id}", response_model=CartItemResponse)
async def update_cart_item(
    item_id: int,
    data: UpdateCartItemRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> CartItemResponse:
    """Update a cart item's quantity.

    Contains two intentional vulnerabilities:

    1. **VULN: CWE-681 (Float Quantity)** — The schema accepts ``float``
       for quantity. Values like ``0.001`` pass the ``> 0`` check but
       truncate to ``0`` via ``int()``, creating a zero-quantity item
       that still exists in the cart. At checkout, ``int(0) = 0`` items
       cost nothing and don't decrement stock.

    2. **VULN: CWE-639 (IDOR)** — Ownership verified by comparing
       ``cart_item.user_id`` against ``current_user["user_id"]`` from
       JWT. Since ``get_current_user`` trusts JWT without DB lookup,
       a forged token bypasses this check.

    Args:
        item_id: Cart item ID to update.
        data: New quantity (float — intentionally insecure type).
        db: Database session (injected).
        current_user: Authenticated user from JWT (injected).

    Returns:
        The updated cart item.

    Raises:
        HTTPException: 404 if item not found, 403 if not owner.
    """
    result = await db.execute(
        select(CartItem)
        .where(CartItem.id == item_id)
        .options(selectinload(CartItem.product))
    )
    cart_item = result.scalar_one_or_none()

    if not cart_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cart item not found",
        )

    # VULN: IDOR - Ownership check uses JWT user_id which is trusted without
    # DB verification. Combined with JWT secret confusion, an attacker can
    # forge a token with any user_id and modify arbitrary cart items.
    # Ref: https://hackerone.com/reports/314808
    if cart_item.user_id != current_user["user_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only modify your own cart items",
        )

    # VULN: Float Quantity - int() truncates float to integer. quantity=0.5
    # becomes 0, quantity=1.7 becomes 1. A zero-quantity item persists in
    # the cart and costs $0 at checkout while not decrementing stock.
    # Ref: https://hackerone.com/reports/1032610
    cart_item.quantity = int(data.quantity)

    await db.commit()
    await db.refresh(cart_item, attribute_names=["product"])

    return _build_cart_item_response(cart_item)


# ---------------------------------------------------------------------------
# DELETE /api/cart/items/{item_id} — Remove item (secure)
# ---------------------------------------------------------------------------


@router.delete(
    "/items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_cart_item(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> None:
    """Remove an item from the cart.

    Ownership check uses the same JWT-trust pattern as PATCH (IDOR vector
    exists but is secondary — deleting another user's cart item is less
    impactful than modifying quantity).

    Args:
        item_id: Cart item ID to remove.
        db: Database session (injected).
        current_user: Authenticated user from JWT (injected).

    Raises:
        HTTPException: 404 if item not found, 403 if not owner.
    """
    result = await db.execute(
        select(CartItem).where(CartItem.id == item_id)
    )
    cart_item = result.scalar_one_or_none()

    if not cart_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cart item not found",
        )

    if cart_item.user_id != current_user["user_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only remove your own cart items",
        )

    await db.delete(cart_item)
    await db.commit()


# ---------------------------------------------------------------------------
# POST /api/cart/apply-coupon — Apply coupon (VULN: Race + Stacking + Negative)
# ---------------------------------------------------------------------------


@router.post("/apply-coupon", response_model=CouponAppliedResponse)
async def apply_coupon(
    data: ApplyCouponRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> CouponAppliedResponse:
    """Apply a discount coupon to the current user's cart.

    Contains three intentional vulnerabilities:

    1. **VULN: CWE-362 (Race Condition)** — The check for "already used"
       (SELECT) and the record insertion (INSERT) are not atomic. No
       ``SELECT FOR UPDATE`` and no UNIQUE(coupon_id, user_id) constraint
       means concurrent requests can both pass the check and redeem the
       same coupon multiple times (TOCTOU).

    2. **VULN: CWE-840 (Coupon Stacking)** — No validation prevents
       applying multiple DIFFERENT coupons. Discounts accumulate without
       limit, potentially exceeding 100%.

    3. **VULN: CWE-840 (Negative Total)** — The resulting total is not
       clamped to a minimum of 0. When stacked discounts exceed the
       subtotal, the total goes negative — effectively store credit.

    Args:
        data: Coupon code to apply.
        db: Database session (injected).
        current_user: Authenticated user from JWT (injected).

    Returns:
        Applied coupon details with discount amount and new cart total.

    Raises:
        HTTPException: 404 if coupon not found, 400 if expired/maxed/
            already used/cart below minimum.
    """
    user_id = current_user["user_id"]

    # Find the coupon by code
    result = await db.execute(
        select(Coupon).where(Coupon.code == data.code)
    )
    coupon = result.scalar_one_or_none()

    if not coupon:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Coupon not found",
        )

    if not coupon.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Coupon is no longer active",
        )

    if coupon.expires_at is not None:
        if datetime.now(timezone.utc) > coupon.expires_at:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Coupon has expired",
            )

    if coupon.max_uses is not None and coupon.times_used >= coupon.max_uses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Coupon has reached maximum usage limit",
        )

    # VULN: Race Condition (TOCTOU) - SELECT without FOR UPDATE, followed
    # by INSERT without UNIQUE constraint on (coupon_id, user_id). Two
    # concurrent requests can both see "not used" and both insert.
    # Ref: https://hackerone.com/reports/759247
    existing_use = await db.execute(
        select(CouponUse).where(
            CouponUse.coupon_id == coupon.id,
            CouponUse.user_id == user_id,
        )
    )
    if existing_use.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You have already used this coupon",
        )

    # Calculate cart subtotal for min_order_total check and discount
    items = await _get_cart_items_with_products(user_id, db)
    if not items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cart is empty",
        )

    subtotal = _calculate_cart_subtotal(items)

    if subtotal < coupon.min_order_total:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Minimum order total of ${coupon.min_order_total} required",
        )

    # Calculate this coupon's discount
    if coupon.discount_type == "percent":
        discount_amount = subtotal * (coupon.discount_value / Decimal("100"))
    else:
        discount_amount = coupon.discount_value

    # Record the coupon use (TOCTOU gap — INSERT without atomicity)
    coupon_use = CouponUse(
        coupon_id=coupon.id,
        user_id=user_id,
    )
    db.add(coupon_use)
    coupon.times_used += 1
    await db.commit()

    # Calculate new total with ALL applied coupons (including this one)
    total_discount, _ = await _get_applied_discounts(user_id, subtotal, db)

    # VULN: Negative Total - no clamp to min 0. When stacked discounts
    # exceed the subtotal, total goes negative = store credit.
    # Ref: https://hackerone.com/reports/894543
    new_total = subtotal - total_discount

    return CouponAppliedResponse(
        code=coupon.code,
        discount_type=coupon.discount_type,
        discount_value=coupon.discount_value,
        discount_amount=discount_amount,
        new_total=new_total,
    )


# ---------------------------------------------------------------------------
# POST /api/cart/checkout — Create order (VULN: Exchange Rate + Stale Prices)
# ---------------------------------------------------------------------------


@router.post("/checkout", response_model=CheckoutResponse)
async def checkout(
    data: CheckoutRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> CheckoutResponse:
    """Convert the cart into an order and clear the cart.

    Contains two intentional vulnerabilities:

    1. **VULN: CWE-20 (Currency Abuse)** — The ``exchange_rate`` is
       accepted from the client and only validated as > 0. There is no
       server-side check against real exchange rates. A value like
       ``0.001`` reduces the total to nearly zero.

    2. **VULN: CWE-472 (Stale Prices)** — Uses ``unit_price`` stored
       in the cart item at add-time instead of re-fetching the current
       ``product.price`` from the database. If a seller raises the price
       after the item was added, the buyer pays the old (lower) price.

    Args:
        data: Shipping address, payment method, and optional currency info.
        db: Database session (injected).
        current_user: Authenticated user from JWT (injected).

    Returns:
        Order confirmation with ID, total, currency, and status.

    Raises:
        HTTPException: 400 if cart is empty or exchange_rate without currency.
    """
    user_id = current_user["user_id"]

    # VULN: Stale Prices - Uses cart_item.unit_price (set at add-time) instead
    # of re-fetching product.price. Price changes after adding to cart are ignored.
    # Ref: https://hackerone.com/reports/1032610
    items = await _get_cart_items_with_products(user_id, db)

    if not items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cart is empty",
        )

    subtotal = _calculate_cart_subtotal(items)
    discount, coupon_codes = await _get_applied_discounts(user_id, subtotal, db)
    total = subtotal - discount

    # Determine currency and apply exchange rate
    currency = "USD"
    if data.currency and data.exchange_rate:
        # VULN: Currency Abuse - exchange_rate from client, only checked > 0.
        # No validation against actual forex rates. exchange_rate=0.001
        # makes a $1000 order cost $1.
        # Ref: https://hackerone.com/reports/1032610
        currency = data.currency.upper()
        total = total * Decimal(str(data.exchange_rate))

    # Find last applied coupon for the order FK (if any)
    last_coupon_id: int | None = None
    if coupon_codes:
        coupon_result = await db.execute(
            select(Coupon.id).where(Coupon.code == coupon_codes[-1])
        )
        last_coupon_id = coupon_result.scalar_one_or_none()

    # Create the order
    order = Order(
        user_id=user_id,
        total=total,
        shipping_addr=data.shipping_address,
        status="pending",
        coupon_id=last_coupon_id,
    )
    db.add(order)

    try:
        await db.flush()
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Order creation failed: {e!s}",
        )

    # Create order items from cart items
    for item in items:
        order_item = OrderItem(
            order_id=order.id,
            product_id=item.product_id,
            quantity=item.quantity,
            unit_price=item.unit_price,
        )
        db.add(order_item)

    # Clear the user's cart
    await db.execute(
        delete(CartItem).where(CartItem.user_id == user_id)
    )

    await db.commit()

    return CheckoutResponse(
        order_id=order.id,
        total=total,
        currency=currency,
        status="pending",
    )
