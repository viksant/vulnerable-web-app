"""Seller panel endpoints with intentional SSRF and IDOR vulnerabilities.

Provides product CRUD for sellers, image import via URL, and analytics.
Contains deliberate vulnerabilities:
  - SSRF via DNS rebinding / TOCTOU gap (CWE-918)
  - SSRF via IPv4-only blacklist bypass (CWE-918)
  - SSRF via open redirect following (CWE-918)
  - SSRF data exfiltration via error messages (CWE-209)
  - IDOR on analytics endpoint via unverified seller_id param (CWE-639)
"""

import asyncio
import ipaddress
import socket
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth_middleware import get_current_user, require_role
from app.models.order import Order, OrderItem
from app.models.product import Product
from app.schemas.seller import (
    CreateProductRequest,
    ImportImageResponse,
    ImportImageURLRequest,
    SellerAnalyticsResponse,
    SellerProductListResponse,
    SellerProductResponse,
    UpdateProductRequest,
)
from app.utils.image_handler import async_save_upload

router = APIRouter()


# ---------------------------------------------------------------------------
# SSRF helpers (intentionally bypassable)
# ---------------------------------------------------------------------------


def _is_private_ip(ip_str: str) -> bool:
    """Check whether an IP address belongs to a private/reserved range.

    Contains an intentional bypass: only handles well-formed IPv4/IPv6
    strings. Decimal IP representations (e.g. ``2852039166`` for
    ``169.254.169.254``) cause ``ipaddress.ip_address`` to raise
    ValueError, which the caller catches and treats as "safe".

    Args:
        ip_str: String representation of the IP address.

    Returns:
        True if the IP is private, loopback, or link-local.

    Raises:
        ValueError: If ``ip_str`` is not a valid IP address format —
            this is the bypass vector.
    """
    # VULN: SSRF IP Bypass - ipaddress.ip_address() cannot parse decimal
    # representations like "2852039166" (=169.254.169.254) or octal
    # like "0251.0376.0251.0376". The ValueError is caught by the caller
    # and interpreted as a non-private IP, allowing the request through.
    # Ref: https://hackerone.com/reports/115857
    addr = ipaddress.ip_address(ip_str)
    return addr.is_private or addr.is_loopback or addr.is_link_local


def _resolve_and_check_ip(hostname: str) -> None:
    """Resolve hostname via DNS and verify the IP is not private.

    Uses ``socket.getaddrinfo`` for DNS resolution, which is a
    blocking call wrapped in ``asyncio.to_thread`` by the caller.
    The resolved IP is checked against the private range blacklist.

    Contains a TOCTOU vulnerability: the DNS resolution here and the
    actual HTTP connection by httpx are independent operations. A DNS
    rebinding attack can return a public IP during validation and a
    private IP during the actual connection.

    Args:
        hostname: The hostname to resolve and validate.

    Raises:
        ValueError: If the hostname resolves to a private IP or
            DNS resolution fails.
    """
    # VULN: SSRF DNS Rebinding - socket.getaddrinfo resolves DNS once here,
    # but httpx resolves independently when making the actual request. A DNS
    # rebinding attack returns a public IP for this check, then switches to
    # a private IP (e.g. 169.254.169.254) for the httpx request.
    # Ref: https://hackerone.com/reports/541169
    try:
        results = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        raise ValueError(f"Cannot resolve hostname: {hostname}")

    if not results:
        raise ValueError(f"No DNS results for: {hostname}")

    # Check only the first resolved IP (additional bypass surface)
    first_ip = results[0][4][0]

    try:
        if _is_private_ip(first_ip):
            raise ValueError(f"Access to private IP addresses is blocked: {first_ip}")
    except ValueError as exc:
        # Re-raise if it's our own "blocked" message
        if "blocked" in str(exc):
            raise
        # VULN: SSRF IP Bypass - If ipaddress.ip_address() cannot parse
        # the IP string (e.g. decimal notation), ValueError is raised
        # and silently caught here, allowing the request to proceed
        pass


# ---------------------------------------------------------------------------
# GET /api/seller/products — List seller's products (secure)
# ---------------------------------------------------------------------------


@router.get("/products", response_model=SellerProductListResponse)
async def list_seller_products(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role("seller", "admin")),
) -> SellerProductListResponse:
    """List products belonging to the authenticated seller.

    Admin users see all products. Sellers see only their own.
    Uses parameterized ORM queries (secure, no vulnerabilities).

    Args:
        limit: Maximum products to return (1-100).
        offset: Pagination offset.
        db: Database session (injected).
        current_user: Authenticated seller/admin from JWT (injected).

    Returns:
        Paginated product list with total count.
    """
    is_admin = current_user["role"] == "admin"

    query = select(Product)
    count_query = select(func.count(Product.id))

    if not is_admin:
        query = query.where(Product.seller_id == current_user["user_id"])
        count_query = count_query.where(Product.seller_id == current_user["user_id"])

    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    result = await db.execute(
        query.order_by(Product.created_at.desc()).limit(limit).offset(offset)
    )
    products = [
        SellerProductResponse.model_validate(p) for p in result.scalars().all()
    ]

    return SellerProductListResponse(products=products, total=total)


# ---------------------------------------------------------------------------
# POST /api/seller/products — Create product (secure)
# ---------------------------------------------------------------------------


@router.post(
    "/products",
    response_model=SellerProductResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_seller_product(
    data: CreateProductRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role("seller", "admin")),
) -> SellerProductResponse:
    """Create a new product listing for the authenticated seller.

    The ``seller_id`` is always set from the JWT — sellers cannot
    create products on behalf of other users. Uses ORM (secure).

    Args:
        data: Product creation payload.
        db: Database session (injected).
        current_user: Authenticated seller/admin from JWT (injected).

    Returns:
        The created product.
    """
    product = Product(
        name=data.name,
        description=data.description,
        price=data.price,
        stock=data.stock,
        category=data.category,
        image_url=data.image_url,
        seller_id=current_user["user_id"],
    )
    db.add(product)
    await db.commit()
    await db.refresh(product)

    return SellerProductResponse.model_validate(product)


# ---------------------------------------------------------------------------
# PUT /api/seller/products/{product_id} — Update product (secure)
# ---------------------------------------------------------------------------


@router.put("/products/{product_id}", response_model=SellerProductResponse)
async def update_seller_product(
    product_id: int,
    data: UpdateProductRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role("seller", "admin")),
) -> SellerProductResponse:
    """Update an existing product.

    Sellers can only update their own products. Admins bypass the
    ownership check. Uses ORM with parameterized queries (secure).

    Args:
        product_id: ID of the product to update.
        data: Partial update payload (only non-None fields applied).
        db: Database session (injected).
        current_user: Authenticated seller/admin from JWT (injected).

    Returns:
        The updated product.

    Raises:
        HTTPException: 404 if product not found, 403 if not owner.
    """
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    is_admin = current_user["role"] == "admin"
    if not is_admin and product.seller_id != current_user["user_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own products",
        )

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(product, field, value)

    await db.commit()
    await db.refresh(product)

    return SellerProductResponse.model_validate(product)


# ---------------------------------------------------------------------------
# POST /api/seller/import-image-url — Import image from URL (VULN: SSRF)
# ---------------------------------------------------------------------------


@router.post("/import-image-url", response_model=ImportImageResponse)
async def import_image_from_url(
    data: ImportImageURLRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role("seller", "admin")),
) -> ImportImageResponse:
    """Import a product image by fetching it from an external URL.

    Contains four intentional SSRF vulnerabilities:

    1. **DNS Rebinding (CWE-918):** DNS resolved once for validation,
       but httpx re-resolves independently — TOCTOU gap.
    2. **IP Bypass (CWE-918):** Blacklist only handles standard IP
       formats; decimal/octal representations cause ValueError which
       is silently ignored.
    3. **Redirect Following (CWE-918):** ``follow_redirects=True``
       allows a 302 from a public server to redirect to internal IPs.
    4. **Data Exfiltration (CWE-209):** Non-image responses include
       ``body[:500]`` in the error message, leaking internal content.

    Args:
        data: URL to fetch and optional product_id to update.
        db: Database session (injected).
        current_user: Authenticated seller/admin from JWT (injected).

    Returns:
        Import result with URL, content type, and size.

    Raises:
        HTTPException: 400 for invalid URL/scheme/DNS/content type,
            502 for fetch failures.
    """
    parsed = urlparse(data.url)

    # Scheme validation — blocks file://, gopher://, etc. (real protection)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only HTTP and HTTPS URLs are allowed",
        )

    if not parsed.hostname:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid URL: no hostname",
        )

    # DNS resolution + private IP check (intentionally bypassable)
    try:
        await asyncio.to_thread(_resolve_and_check_ip, parsed.hostname)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    # VULN: SSRF bypass vectors:
    # - PRIMARY: Redirect chain (external URL -> 302 -> internal IP). Blacklist only
    #   checks initial URL, not redirect targets (follow_redirects=True).
    # - SECONDARY: IPv6 mapped addresses [::ffff:X.X.X.X] for some targets.
    # - NOTE: Direct access to 169.254.169.254 IS blocked (is_link_local detection).
    #   Use redirect bypass to reach metadata-mock.
    # Ref: https://hackerone.com/reports/508459
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=10.0,
        ) as client:
            response = await client.get(data.url)
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch URL: {exc}",
        )

    content_type = response.headers.get("content-type", "")

    # VULN: SSRF Data Exfiltration - When the response is not an image,
    # the error message includes the first 500 bytes of the response body.
    # An attacker can point the URL at internal services (e.g. metadata
    # endpoint at 169.254.169.254) and read the response via error messages.
    # Ref: https://hackerone.com/reports/285380
    if not content_type.startswith("image/"):
        body_preview = response.text[:500]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"URL does not point to an image (content-type: {content_type}). "
            f"Response preview: {body_preview}",
        )

    # Extract filename from URL path (fallback to "imported.jpg")
    url_path = parsed.path.rstrip("/")
    filename = url_path.split("/")[-1] if "/" in url_path else "imported.jpg"
    if "." not in filename:
        filename = "imported.jpg"

    try:
        saved_filename = await async_save_upload(response.content, filename)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Image validation failed: {exc}",
        )

    static_url = f"/static/{saved_filename}"

    # Update product image_url if product_id was provided
    if data.product_id is not None:
        result = await db.execute(
            select(Product).where(Product.id == data.product_id)
        )
        product = result.scalar_one_or_none()

        if product:
            is_admin = current_user["role"] == "admin"
            if is_admin or product.seller_id == current_user["user_id"]:
                product.image_url = static_url
                await db.commit()

    return ImportImageResponse(
        url=static_url,
        content_type=content_type,
        size=len(response.content),
    )


# ---------------------------------------------------------------------------
# GET /api/seller/analytics — Seller analytics (VULN: IDOR)
# ---------------------------------------------------------------------------


@router.get("/analytics", response_model=SellerAnalyticsResponse)
async def get_seller_analytics(
    seller_id: int | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role("seller", "admin")),
) -> SellerAnalyticsResponse:
    """Retrieve aggregate analytics for a seller's shop.

    Contains an intentional IDOR vulnerability: the ``seller_id``
    query parameter overrides the authenticated user's ID without
    ownership verification. Any seller can view another seller's
    analytics by supplying their ID.

    Args:
        seller_id: Target seller ID (defaults to authenticated user).
        db: Database session (injected).
        current_user: Authenticated seller/admin from JWT (injected).

    Returns:
        Analytics summary: product count, order count, revenue, and
        product distribution by category.
    """
    # VULN: IDOR - seller_id query parameter accepted without verifying
    # that the authenticated user owns or has permission to view the
    # target seller's analytics. Any authenticated seller can enumerate
    # and view other sellers' revenue and product data.
    # Ref: https://hackerone.com/reports/314808
    target_id = seller_id if seller_id is not None else current_user["user_id"]

    # Total products
    product_count_result = await db.execute(
        select(func.count(Product.id)).where(Product.seller_id == target_id)
    )
    total_products = product_count_result.scalar_one()

    # Total orders and revenue (via order_items -> products)
    order_stats_query = (
        select(
            func.count(func.distinct(Order.id)).label("order_count"),
            func.coalesce(
                func.sum(OrderItem.unit_price * OrderItem.quantity), 0
            ).label("revenue"),
        )
        .select_from(Order)
        .join(OrderItem, Order.id == OrderItem.order_id)
        .join(Product, OrderItem.product_id == Product.id)
        .where(Product.seller_id == target_id)
    )
    order_result = await db.execute(order_stats_query)
    order_row = order_result.one()
    total_orders = order_row.order_count
    total_revenue = order_row.revenue

    # Products by category
    category_query = (
        select(Product.category, func.count(Product.id).label("count"))
        .where(Product.seller_id == target_id)
        .group_by(Product.category)
    )
    category_result = await db.execute(category_query)
    products_by_category = {
        row.category: row.count for row in category_result.all()
    }

    return SellerAnalyticsResponse(
        total_products=total_products,
        total_orders=total_orders,
        total_revenue=total_revenue,
        products_by_category=products_by_category,
    )
