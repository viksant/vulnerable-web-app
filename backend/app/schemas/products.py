"""Product-related request/response schemas.

Defines Pydantic v2 models for product listing, search results,
and product details with embedded reviews. The ``SearchResponse``
intentionally echoes the raw query parameter to enable reflected XSS.
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Embedded schemas
# ---------------------------------------------------------------------------


class ReviewInProduct(BaseModel):
    """Review summary embedded within a product detail response.

    Note: ``body`` is returned without sanitization — this serves as
    the delivery point for stored XSS payloads injected via P06.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    user_id: int
    username: str
    title: str
    rating: int
    body: str
    created_at: datetime


# ---------------------------------------------------------------------------
# Product response schemas
# ---------------------------------------------------------------------------


class ProductResponse(BaseModel):
    """Standard product representation for list views."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    price: Decimal
    stock: int
    category: str
    image_url: str | None
    seller_id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ProductDetailResponse(ProductResponse):
    """Extended product view including customer reviews."""

    reviews: list[ReviewInProduct] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Collection / search response schemas
# ---------------------------------------------------------------------------


class ProductListResponse(BaseModel):
    """Paginated product collection."""

    products: list[ProductResponse]
    total: int
    limit: int
    offset: int


class SearchResponse(BaseModel):
    """Search results with reflected query string.

    VULN delivery: the ``query`` field echoes user input without
    sanitization, enabling reflected XSS when rendered by the frontend.
    """

    query: str
    results: list[ProductResponse]
    total: int


class CategoryListResponse(BaseModel):
    """Distinct product categories."""

    categories: list[str]
