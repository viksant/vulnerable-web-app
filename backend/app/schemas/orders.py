"""Order and invoice response schemas.

Defines Pydantic v2 models for order listing, order detail, invoice
(intentionally over-exposed via IDOR), and pickle export responses.
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class OrderSummaryResponse(BaseModel):
    """Compact order view for list endpoints."""

    model_config = ConfigDict(from_attributes=True)

    uuid: str
    total: Decimal
    status: str
    created_at: datetime


class OrderItemResponse(BaseModel):
    """Single line item within an order."""

    model_config = ConfigDict(from_attributes=True)

    product_id: int
    quantity: int
    unit_price: Decimal


class OrderDetailResponse(BaseModel):
    """Full order detail with items — uses UUID as public identifier."""

    model_config = ConfigDict(from_attributes=True)

    uuid: str
    total: Decimal
    status: str
    shipping_addr: str | None
    coupon_id: int | None
    items: list[OrderItemResponse]
    created_at: datetime
    updated_at: datetime


class InvoiceResponse(BaseModel):
    """Invoice with user PII — intentionally exposed without auth (VULN).

    Includes sensitive fields: email, phone, payment_method_last4.
    Returned by the unauthenticated /api/invoices/{id} endpoint.
    """

    order_id: int
    uuid: str
    total: Decimal
    status: str
    shipping_addr: str | None
    items: list[OrderItemResponse]
    user_email: str
    user_full_name: str | None
    user_phone: str | None
    payment_method_last4: str | None
    created_at: datetime


class ExportResponse(BaseModel):
    """Pickle-serialized order export — setup for deserialization VULN."""

    format: str
    data: str
    record_count: int
