"""Order and invoice endpoints with intentional IDOR and deserialization vulnerabilities.

Provides order listing, detail, invoice redirect, unauthenticated invoice
access, and pickle export. Contains deliberate vulnerabilities:
  - UUID-to-ID leak via 302 redirect on invoice endpoint (CWE-200)
  - Unauthenticated IDOR on /invoices/{id} — exposes user PII (CWE-639)
  - Insecure deserialization setup via pickle export (CWE-502)
"""

import base64
import pickle

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.middleware.auth_middleware import get_current_user, require_role
from app.models.order import Order
from app.schemas.orders import (
    ExportResponse,
    InvoiceResponse,
    OrderDetailResponse,
    OrderItemResponse,
    OrderSummaryResponse,
)

router = APIRouter()
invoices_router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_order_summary(order: Order) -> OrderSummaryResponse:
    """Build a compact order summary from an ORM Order.

    Args:
        order: Order ORM instance.

    Returns:
        OrderSummaryResponse with uuid, total, status, created_at.
    """
    return OrderSummaryResponse(
        uuid=order.uuid,
        total=order.total,
        status=order.status,
        created_at=order.created_at,
    )


def _build_order_detail(order: Order) -> OrderDetailResponse:
    """Build a full order detail from an ORM Order with loaded items.

    Args:
        order: Order ORM instance with items relationship loaded.

    Returns:
        OrderDetailResponse with item list.
    """
    return OrderDetailResponse(
        uuid=order.uuid,
        total=order.total,
        status=order.status,
        shipping_addr=order.shipping_addr,
        coupon_id=order.coupon_id,
        items=[
            OrderItemResponse(
                product_id=item.product_id,
                quantity=item.quantity,
                unit_price=item.unit_price,
            )
            for item in order.items
        ],
        created_at=order.created_at,
        updated_at=order.updated_at,
    )


async def _get_order_by_uuid_or_404(
    uuid: str,
    db: AsyncSession,
    *,
    load_items: bool = False,
) -> Order:
    """Fetch an order by its public UUID or raise 404.

    Args:
        uuid: The public UUID string.
        db: Async database session.
        load_items: Whether to eagerly load order items.

    Returns:
        The Order ORM instance.

    Raises:
        HTTPException: 404 if no order matches the UUID.
    """
    stmt = select(Order).where(Order.uuid == uuid)
    if load_items:
        stmt = stmt.options(selectinload(Order.items))

    result = await db.execute(stmt)
    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )
    return order


# ---------------------------------------------------------------------------
# GET /api/orders/export — Pickle export (VULN: Insecure Deserialization setup)
# ---------------------------------------------------------------------------
# IMPORTANT: This route MUST be registered BEFORE /{uuid} to prevent
# FastAPI from interpreting "export" as a UUID path parameter.


# VULN: Insecure Deserialization - Orders exported as Python pickle (base64).
# The VSEXPORT_V2 format is the entry vector for P10 RCE: an attacker who
# submits a crafted pickle payload to the future import endpoint achieves
# arbitrary code execution via pickle.loads().
# Ref: https://hackerone.com/reports/1073363
@router.get("/export", response_model=ExportResponse)
async def export_orders(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role("admin", "seller")),
) -> ExportResponse:
    """Export orders as pickle-serialized base64 data.

    Restricted to admin and seller roles. Sellers see only their own
    orders; admins see all orders. The pickle format is intentionally
    insecure — it serves as the deserialization attack vector for P10.

    Args:
        db: Database session (injected).
        current_user: Authenticated admin or seller from JWT (injected).

    Returns:
        ExportResponse with VSEXPORT_V2 format, base64 pickle data,
        and record count.
    """
    if current_user["role"] == "admin":
        result = await db.execute(
            select(Order).options(selectinload(Order.items))
        )
    else:
        result = await db.execute(
            select(Order)
            .where(Order.user_id == current_user["user_id"])
            .options(selectinload(Order.items))
        )

    orders = result.scalars().all()

    # Serialize to a list of dicts for pickle
    export_data: list[dict] = []
    for order in orders:
        export_data.append({
            "id": order.id,
            "uuid": order.uuid,
            "user_id": order.user_id,
            "status": order.status,
            "total": str(order.total),
            "shipping_addr": order.shipping_addr,
            "created_at": order.created_at.isoformat() if order.created_at else None,
            "items": [
                {
                    "product_id": item.product_id,
                    "quantity": item.quantity,
                    "unit_price": str(item.unit_price),
                }
                for item in order.items
            ],
        })

    # VULN: pickle.dumps() — the counterpart pickle.loads() in P10 import
    # endpoint enables arbitrary code execution
    pickled = pickle.dumps(export_data)
    encoded = base64.b64encode(pickled).decode("ascii")

    return ExportResponse(
        format="VSEXPORT_V2",
        data=f"VSEXPORT_V2:{encoded}",
        record_count=len(export_data),
    )


# ---------------------------------------------------------------------------
# GET /api/orders — List user's orders (secure)
# ---------------------------------------------------------------------------


@router.get("", response_model=list[OrderSummaryResponse])
async def list_orders(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> list[OrderSummaryResponse]:
    """List all orders for the authenticated user.

    Correctly filters by user_id from JWT — only returns the
    requesting user's own orders. Ordered by most recent first.

    Args:
        db: Database session (injected).
        current_user: Authenticated user from JWT (injected).

    Returns:
        List of order summaries (uuid, total, status, created_at).
    """
    result = await db.execute(
        select(Order)
        .where(Order.user_id == current_user["user_id"])
        .order_by(Order.created_at.desc())
    )
    orders = result.scalars().all()
    return [_build_order_summary(o) for o in orders]


# ---------------------------------------------------------------------------
# GET /api/orders/{uuid} — Order detail (secure)
# ---------------------------------------------------------------------------


@router.get("/{uuid}", response_model=OrderDetailResponse)
async def get_order_detail(
    uuid: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> OrderDetailResponse:
    """Get full detail for a specific order by UUID.

    Verifies ownership: the order's user_id must match the
    authenticated user. Returns 403 if the order belongs to
    another user.

    Args:
        uuid: Public UUID of the order.
        db: Database session (injected).
        current_user: Authenticated user from JWT (injected).

    Returns:
        Full order detail with items.

    Raises:
        HTTPException: 404 if not found, 403 if not owner.
    """
    order = await _get_order_by_uuid_or_404(uuid, db, load_items=True)

    if order.user_id != current_user["user_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own orders",
        )

    return _build_order_detail(order)


# ---------------------------------------------------------------------------
# GET /api/orders/{uuid}/invoice — Redirect to invoice (VULN: UUID-to-ID Leak)
# ---------------------------------------------------------------------------


# VULN: UUID-to-ID Leak - The 302 redirect to /api/invoices/{order.id}
# exposes the sequential internal ID in the Location header. An attacker
# who observes the redirect learns the numeric ID and can enumerate all
# invoices at /api/invoices/1, /api/invoices/2, etc.
# Ref: https://hackerone.com/reports/743968
@router.get("/{uuid}/invoice")
async def get_invoice_redirect(
    uuid: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> RedirectResponse:
    """Redirect to the invoice endpoint using the internal order ID.

    Ownership is correctly verified, but the redirect leaks the
    sequential internal ID via the Location header. The invoice
    endpoint itself has no auth check (VULN 2), making the leaked
    ID directly exploitable.

    Args:
        uuid: Public UUID of the order.
        db: Database session (injected).
        current_user: Authenticated user from JWT (injected).

    Returns:
        302 redirect to /api/invoices/{internal_id}.

    Raises:
        HTTPException: 404 if not found, 403 if not owner.
    """
    order = await _get_order_by_uuid_or_404(uuid, db)

    if order.user_id != current_user["user_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own invoices",
        )

    # VULN: Leaks internal sequential ID in redirect Location header
    return RedirectResponse(
        url=f"/api/invoices/{order.id}",
        status_code=status.HTTP_302_FOUND,
    )


# ---------------------------------------------------------------------------
# GET /api/invoices/{id} — Invoice without auth (VULN: Unauthenticated IDOR)
# ---------------------------------------------------------------------------


# VULN: Unauthenticated IDOR - No authentication required. Sequential IDs
# are enumerable (1, 2, 3, ...). Returns full order details plus user PII:
# email, full_name, phone, payment_method_last4.
# Ref: https://hackerone.com/reports/314808
@invoices_router.get("/{order_id}", response_model=InvoiceResponse)
async def get_invoice(
    order_id: int,
    db: AsyncSession = Depends(get_db),
) -> InvoiceResponse:
    """Retrieve an invoice by internal order ID — no authentication.

    This endpoint is intentionally unprotected. The assumption is that
    "only legitimate users reach it via the redirect", but the sequential
    ID leaked by the redirect makes enumeration trivial.

    Exposes user PII: email, full_name, phone, payment_method_last4.

    Args:
        order_id: Internal sequential order ID.
        db: Database session (injected).

    Returns:
        Full invoice with order details and user PII.

    Raises:
        HTTPException: 404 if order not found.
    """
    result = await db.execute(
        select(Order)
        .where(Order.id == order_id)
        .options(selectinload(Order.items), selectinload(Order.user))
    )
    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found",
        )

    user = order.user

    return InvoiceResponse(
        order_id=order.id,
        uuid=order.uuid,
        total=order.total,
        status=order.status,
        shipping_addr=order.shipping_addr,
        items=[
            OrderItemResponse(
                product_id=item.product_id,
                quantity=item.quantity,
                unit_price=item.unit_price,
            )
            for item in order.items
        ],
        user_email=user.email,
        user_full_name=user.full_name,
        user_phone=user.phone,
        payment_method_last4=user.payment_method_last4,
        created_at=order.created_at,
    )
