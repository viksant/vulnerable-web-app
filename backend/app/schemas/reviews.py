"""Review request/response schemas.

Defines Pydantic v2 models for review CRUD operations. The ``body``
field in responses is returned as-is from the database — this is the
delivery point for stored XSS payloads injected via the POST endpoint.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class CreateReviewRequest(BaseModel):
    """Payload for creating a new product review.

    ``title`` is stored without sanitization (secondary XSS vector).
    ``body`` passes through sanitize_html() in the route handler,
    but the sanitizer is intentionally bypassable.
    """

    title: str = Field(min_length=1, max_length=255)
    body: str = Field(min_length=1)
    rating: int = Field(ge=1, le=5)


class UpdateReviewRequest(BaseModel):
    """Partial update payload for an existing review.

    Only provided fields are applied to the review record.
    """

    title: str | None = Field(default=None, min_length=1, max_length=255)
    body: str | None = Field(default=None, min_length=1)
    rating: int | None = Field(default=None, ge=1, le=5)


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class ReviewResponse(BaseModel):
    """Full review representation returned by all review endpoints.

    ``body`` is returned as stored in the database without escaping,
    serving as the delivery mechanism for stored XSS payloads.
    ``username`` is extracted from the review's user relationship.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    user_id: int
    username: str
    title: str
    rating: int
    body: str
    image_path: str | None
    created_at: datetime


class ReviewListResponse(BaseModel):
    """Paginated list of reviews for a product."""

    reviews: list[ReviewResponse]
    total: int
