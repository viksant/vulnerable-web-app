"""Seller panel request/response schemas.

Defines Pydantic v2 models for seller product CRUD, image import
via URL, and analytics endpoints. Uses Field constraints consistent
with the Product model column definitions.
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class CreateProductRequest(BaseModel):
    """Payload for creating a new product as a seller."""

    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=5000)
    price: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    stock: int = Field(ge=0)
    category: str = Field(default="general", min_length=1, max_length=100)
    image_url: str | None = Field(default=None, max_length=500)


class UpdateProductRequest(BaseModel):
    """Partial update payload for a seller product.

    Only provided (non-None) fields are applied to the record.
    """

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    price: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    stock: int | None = Field(default=None, ge=0)
    category: str | None = Field(default=None, min_length=1, max_length=100)
    image_url: str | None = Field(default=None, max_length=500)


class ImportImageURLRequest(BaseModel):
    """Request to import an image from an external URL.

    The ``product_id`` is optional — when provided, the product's
    ``image_url`` is updated to the saved file's static URL.
    """

    url: str = Field(min_length=1, max_length=2048)
    product_id: int | None = Field(default=None)


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class SellerProductResponse(BaseModel):
    """Full product representation for seller panel views."""

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


class SellerProductListResponse(BaseModel):
    """Paginated seller product collection."""

    products: list[SellerProductResponse]
    total: int


class ImportImageResponse(BaseModel):
    """Response after successfully importing an image from URL."""

    url: str
    content_type: str
    size: int


class SellerAnalyticsResponse(BaseModel):
    """Aggregate analytics for a seller's shop performance."""

    total_products: int
    total_orders: int
    total_revenue: Decimal
    products_by_category: dict[str, int]
