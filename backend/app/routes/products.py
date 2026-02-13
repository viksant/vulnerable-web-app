"""Product endpoints with intentional SQL injection and reflected XSS.

Provides product listing, search, detail, and category endpoints.
Contains deliberate vulnerabilities in search (SQLi via f-string),
ORDER BY injection, reflected XSS (query echo), and an advanced
filter with a hidden SQL injection vector.

Secure endpoints (detail, categories, default list) use SQLAlchemy
ORM with parameterized queries.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.product import Product
from app.models.review import Review
from app.schemas.products import (
    CategoryListResponse,
    ProductDetailResponse,
    ProductListResponse,
    ProductResponse,
    ReviewInProduct,
    SearchResponse,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# GET /api/products — Product listing (secure by default, vuln via hidden param)
# ---------------------------------------------------------------------------


@router.get("", response_model=ProductListResponse)
async def list_products(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    category: str | None = Query(default=None),
    advanced_filter: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> ProductListResponse:
    """List active products with optional category filter.

    By default uses parameterized ORM queries (secure). When the hidden
    ``advanced_filter=true`` parameter is supplied, switches to raw SQL
    with string interpolation for the category filter.

    Args:
        limit: Maximum number of products to return (1-100).
        offset: Pagination offset.
        category: Optional category filter.
        advanced_filter: Hidden param that enables raw SQL path.
        db: Database session (injected).

    Returns:
        Paginated product list with total count.
    """
    if advanced_filter == "true" and category:
        # VULN: SQLi - Category value concatenated into raw SQL via f-string
        # The advanced_filter param is undocumented, requiring discovery
        # Ref: https://hackerone.com/reports/297478
        sql = (
            f"SELECT * FROM products WHERE is_active = true"
            f" AND category = '{category}'"
            f" LIMIT {limit} OFFSET {offset}"
        )
        result = await db.execute(text(sql))
        rows = result.mappings().all()
        products = [ProductResponse.model_validate(dict(row)) for row in rows]

        count_sql = (
            f"SELECT COUNT(*) FROM products WHERE is_active = true"
            f" AND category = '{category}'"
        )
        count_result = await db.execute(text(count_sql))
        total = count_result.scalar_one()
    else:
        # Secure path — parameterized ORM queries
        query = select(Product).where(Product.is_active.is_(True))
        count_query = select(func.count(Product.id)).where(
            Product.is_active.is_(True)
        )

        if category:
            query = query.where(Product.category == category)
            count_query = count_query.where(Product.category == category)

        query = query.limit(limit).offset(offset)

        result = await db.execute(query)
        products = [
            ProductResponse.model_validate(p) for p in result.scalars().all()
        ]

        count_result = await db.execute(count_query)
        total = count_result.scalar_one()

    return ProductListResponse(
        products=products, total=total, limit=limit, offset=offset
    )


# ---------------------------------------------------------------------------
# GET /api/products/search — Vulnerable search (SQLi + ORDER BY + XSS)
# ---------------------------------------------------------------------------


@router.get("/search", response_model=SearchResponse)
async def search_products(
    q: str = Query(..., min_length=1),
    category: str | None = Query(default=None),
    sort: str = Query(default="name"),
    order: str = Query(default="ASC"),
    db: AsyncSession = Depends(get_db),
) -> SearchResponse:
    """Search products by name or description.

    Contains three intentional vulnerabilities:
      1. SQL injection via the ``q`` parameter (f-string in raw SQL)
      2. ORDER BY injection via ``sort``/``order`` parameters
      3. Reflected XSS — ``q`` echoed in response without sanitization

    Args:
        q: Search query (injected into raw SQL).
        category: Optional category filter (also injectable).
        sort: Column name for ORDER BY clause (no whitelist).
        order: Sort direction — ASC or DESC (no validation).
        db: Database session (injected).

    Returns:
        Search results with the raw query string echoed back.
    """
    # VULN: SQLi - User input directly interpolated into raw SQL query
    # In f-strings, % is literal so '%{q}%' produces the correct ILIKE pattern
    # Ref: https://hackerone.com/reports/311244
    sql = (
        f"SELECT * FROM products WHERE is_active = true"
        f" AND (name ILIKE '%{q}%' OR description ILIKE '%{q}%')"
    )

    if category:
        sql += f" AND category = '{category}'"

    # VULN: ORDER BY Injection - Column name and direction injected without whitelist
    # Allows boolean-based blind SQLi via CASE WHEN expressions
    # Ref: https://hackerone.com/reports/419017
    sql += f" ORDER BY {sort} {order}"

    result = await db.execute(text(sql))
    rows = result.mappings().all()
    products = [ProductResponse.model_validate(dict(row)) for row in rows]

    # VULN: Reflected XSS - Query parameter echoed in response without sanitization
    # Frontend renders this value, enabling script injection
    # Ref: https://hackerone.com/reports/191810
    return SearchResponse(query=q, results=products, total=len(products))


# ---------------------------------------------------------------------------
# GET /api/products/categories — Category list (secure)
# ---------------------------------------------------------------------------


@router.get("/categories", response_model=CategoryListResponse)
async def list_categories(
    db: AsyncSession = Depends(get_db),
) -> CategoryListResponse:
    """List distinct product categories.

    Uses parameterized ORM query (secure, no vulnerabilities).

    Args:
        db: Database session (injected).

    Returns:
        Sorted list of unique category names.
    """
    result = await db.execute(
        select(Product.category)
        .where(Product.is_active.is_(True))
        .distinct()
        .order_by(Product.category)
    )
    categories = [row[0] for row in result.all()]
    return CategoryListResponse(categories=categories)


# ---------------------------------------------------------------------------
# GET /api/products/{product_id} — Product detail (secure)
# ---------------------------------------------------------------------------


@router.get("/{product_id}", response_model=ProductDetailResponse)
async def get_product_detail(
    product_id: int,
    db: AsyncSession = Depends(get_db),
) -> ProductDetailResponse:
    """Retrieve a single product with its reviews.

    Uses parameterized ORM query (secure). Review bodies are returned
    without sanitization — this is the delivery point for stored XSS
    payloads that will be injected via P06 review endpoints.

    Args:
        product_id: ID of the product to retrieve.
        db: Database session (injected).

    Returns:
        Product with embedded reviews including reviewer usernames.

    Raises:
        HTTPException: 404 if product not found or inactive.
    """
    result = await db.execute(
        select(Product)
        .where(Product.id == product_id, Product.is_active.is_(True))
        .options(selectinload(Product.reviews).selectinload(Review.user))
    )
    product = result.scalar_one_or_none()

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    # Build review list with username extracted from the user relationship
    reviews = [
        ReviewInProduct(
            id=review.id,
            product_id=review.product_id,
            user_id=review.user_id,
            username=review.user.username,
            title=review.title,
            rating=review.rating,
            body=review.body,
            created_at=review.created_at,
        )
        for review in product.reviews
    ]

    product_data = ProductResponse.model_validate(product)
    return ProductDetailResponse(**product_data.model_dump(), reviews=reviews)
