"""Review CRUD endpoints with intentional Stored XSS and IDOR vulnerabilities.

Provides list, create, update, and delete operations for product reviews.
Contains deliberate vulnerabilities:
  - Stored XSS via bypassable sanitize_html() on body field
  - IDOR on PUT/DELETE — JWT user_id compared without DB verification
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.middleware.auth_middleware import get_current_user
from app.models.product import Product
from app.models.review import Review
from app.schemas.reviews import (
    CreateReviewRequest,
    ReviewListResponse,
    ReviewResponse,
    UpdateReviewRequest,
)
from app.utils.sanitizer import sanitize_html

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_review_response(review: Review) -> ReviewResponse:
    """Build a ReviewResponse from an ORM Review with loaded user relationship.

    Args:
        review: Review ORM instance with user relationship eagerly loaded.

    Returns:
        Pydantic ReviewResponse with username extracted from user relationship.
    """
    return ReviewResponse(
        id=review.id,
        product_id=review.product_id,
        user_id=review.user_id,
        username=review.user.username,
        title=review.title,
        rating=review.rating,
        body=review.body,
        image_path=review.image_path,
        created_at=review.created_at,
    )


async def _get_product_or_404(
    product_id: int,
    db: AsyncSession,
) -> Product:
    """Fetch an active product or raise 404.

    Args:
        product_id: The product ID to look up.
        db: Async database session.

    Returns:
        The Product ORM instance.

    Raises:
        HTTPException: 404 if product not found or inactive.
    """
    result = await db.execute(
        select(Product).where(Product.id == product_id, Product.is_active.is_(True))
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )
    return product


async def _get_review_or_404(
    review_id: int,
    product_id: int,
    db: AsyncSession,
) -> Review:
    """Fetch a review belonging to a product, or raise 404.

    Args:
        review_id: The review ID to look up.
        product_id: The product ID the review must belong to.
        db: Async database session.

    Returns:
        The Review ORM instance with user relationship loaded.

    Raises:
        HTTPException: 404 if review not found or does not belong to product.
    """
    result = await db.execute(
        select(Review)
        .where(Review.id == review_id, Review.product_id == product_id)
        .options(selectinload(Review.user))
    )
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review not found",
        )
    return review


# ---------------------------------------------------------------------------
# GET /{product_id}/reviews — List reviews for a product (secure)
# ---------------------------------------------------------------------------


@router.get("/{product_id}/reviews", response_model=ReviewListResponse)
async def list_reviews(
    product_id: int,
    db: AsyncSession = Depends(get_db),
) -> ReviewListResponse:
    """List all reviews for a product.

    Uses parameterized ORM queries (secure). Review bodies are returned
    as stored in the database — this is the delivery point for stored
    XSS payloads injected via the POST endpoint.

    Args:
        product_id: ID of the product whose reviews to list.
        db: Database session (injected).

    Returns:
        List of reviews with total count.

    Raises:
        HTTPException: 404 if product not found or inactive.
    """
    await _get_product_or_404(product_id, db)

    count_result = await db.execute(
        select(func.count(Review.id)).where(Review.product_id == product_id)
    )
    total = count_result.scalar_one()

    result = await db.execute(
        select(Review)
        .where(Review.product_id == product_id)
        .options(selectinload(Review.user))
        .order_by(Review.created_at.desc())
    )
    reviews = [_build_review_response(r) for r in result.scalars().all()]

    return ReviewListResponse(reviews=reviews, total=total)


# ---------------------------------------------------------------------------
# POST /{product_id}/reviews — Create review (VULN: Stored XSS)
# ---------------------------------------------------------------------------


@router.post(
    "/{product_id}/reviews",
    response_model=ReviewResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_review(
    product_id: int,
    data: CreateReviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ReviewResponse:
    """Create a new review for a product.

    Contains an intentional Stored XSS vulnerability: the ``body`` field
    passes through ``sanitize_html()`` which is bypassable depending on
    the difficulty setting. The ``title`` is stored without any
    sanitization — secondary XSS vector limited by frontend rendering.

    Args:
        product_id: ID of the product to review.
        data: Review payload (title, body, rating).
        db: Database session (injected).
        current_user: Authenticated user from JWT (injected).

    Returns:
        The created review.

    Raises:
        HTTPException: 404 if product not found, 409 if user already reviewed.
    """
    await _get_product_or_404(product_id, db)

    # Check for duplicate review (UNIQUE constraint: product_id + user_id)
    existing = await db.execute(
        select(Review.id).where(
            Review.product_id == product_id,
            Review.user_id == current_user["user_id"],
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You have already reviewed this product",
        )

    # VULN: Stored XSS - sanitize_html() is intentionally bypassable; the sanitized
    # body is stored in DB and returned without escaping in all read endpoints.
    # Title is NOT sanitized — secondary XSS vector via <h4> rendering in frontend.
    # Ref: https://hackerone.com/reports/485748
    sanitized_body = sanitize_html(data.body)

    review = Review(
        product_id=product_id,
        user_id=current_user["user_id"],
        title=data.title,
        rating=data.rating,
        body=sanitized_body,
    )
    db.add(review)

    # Handle race condition: two concurrent requests may both pass the
    # duplicate check above, but the UNIQUE(product_id, user_id) constraint
    # in DB will reject the second one
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You have already reviewed this product",
        )

    await db.refresh(review, attribute_names=["user"])

    return _build_review_response(review)


# ---------------------------------------------------------------------------
# PUT /{product_id}/reviews/{review_id} — Update review (VULN: IDOR)
# ---------------------------------------------------------------------------


@router.put("/{product_id}/reviews/{review_id}", response_model=ReviewResponse)
async def update_review(
    product_id: int,
    review_id: int,
    data: UpdateReviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ReviewResponse:
    """Update an existing review.

    Contains an intentional IDOR vulnerability: ownership is verified by
    comparing ``current_user["user_id"]`` from the JWT against
    ``review.user_id``. Since ``get_current_user`` trusts the JWT
    payload without database verification (VULN 7), an attacker who
    forges a token with another user's ID can edit their reviews.

    Args:
        product_id: ID of the product the review belongs to.
        review_id: ID of the review to update.
        data: Partial update payload.
        db: Database session (injected).
        current_user: Authenticated user from JWT (injected).

    Returns:
        The updated review.

    Raises:
        HTTPException: 404 if review not found, 403 if not owner.
    """
    review = await _get_review_or_404(review_id, product_id, db)

    # VULN: IDOR - Ownership check uses JWT user_id which is trusted without DB
    # verification. Combined with JWT secret confusion (VULN 5), an attacker can
    # forge a token with any user_id and edit arbitrary reviews.
    # Ref: https://hackerone.com/reports/314808
    if review.user_id != current_user["user_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only edit your own reviews",
        )

    if data.title is not None:
        review.title = data.title
    if data.body is not None:
        review.body = sanitize_html(data.body)
    if data.rating is not None:
        review.rating = data.rating

    await db.commit()
    await db.refresh(review, attribute_names=["user"])

    return _build_review_response(review)


# ---------------------------------------------------------------------------
# DELETE /{product_id}/reviews/{review_id} — Delete review (VULN: IDOR)
# ---------------------------------------------------------------------------


@router.delete(
    "/{product_id}/reviews/{review_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_review(
    product_id: int,
    review_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> None:
    """Delete an existing review.

    Contains an intentional IDOR vulnerability identical to the PUT
    endpoint. Admin and support roles can delete any review (by design).

    Args:
        product_id: ID of the product the review belongs to.
        review_id: ID of the review to delete.
        db: Database session (injected).
        current_user: Authenticated user from JWT (injected).

    Raises:
        HTTPException: 404 if review not found, 403 if not owner/admin.
    """
    review = await _get_review_or_404(review_id, product_id, db)

    # VULN: IDOR - Same JWT trust issue as PUT endpoint. Admin/support roles
    # bypass ownership check entirely (by design — privileged deletion).
    # Ref: https://hackerone.com/reports/314808
    is_privileged = current_user["role"] in ("admin", "support")
    if not is_privileged and review.user_id != current_user["user_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own reviews",
        )

    await db.delete(review)
    await db.commit()
