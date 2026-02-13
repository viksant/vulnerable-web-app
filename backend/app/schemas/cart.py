"""Cart request/response schemas with intentional validation asymmetries.

Defines Pydantic v2 models for cart CRUD, coupon application, and checkout.
Contains deliberate type mismatches between schemas:
  - AddCartItemRequest uses int quantity (secure)
  - UpdateCartItemRequest uses float quantity (CWE-681 — type confusion)
  - CheckoutRequest accepts client-supplied exchange_rate (CWE-20)
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class AddCartItemRequest(BaseModel):
    """Payload for adding a product to the cart.

    Uses ``int`` for quantity with ``gt=0`` — this is the SECURE path.
    Compare with UpdateCartItemRequest which uses ``float`` (VULN).
    """

    product_id: int
    quantity: int = Field(gt=0, description="Must be a positive integer")


class UpdateCartItemRequest(BaseModel):
    """Payload for updating a cart item's quantity.

    VULN: CWE-681 — Uses ``float`` for quantity instead of ``int``.
    A value like 0.001 passes the ``gt=0`` check but truncates to 0
    when cast to int for DB storage, enabling free-product attacks.
    """

    # VULN: Float Quantity - float allows fractional values like 0.001 that
    # pass gt=0 validation but truncate to 0 via int(), enabling zero-cost items.
    # Ref: https://hackerone.com/reports/1032610
    quantity: float = Field(gt=0, description="Quantity to set")


class ApplyCouponRequest(BaseModel):
    """Payload for applying a discount coupon to the cart."""

    code: str = Field(min_length=1, max_length=50)


class CheckoutRequest(BaseModel):
    """Payload for completing a cart checkout.

    VULN: CWE-20 — ``exchange_rate`` is validated as > 0 but not checked
    against real currency rates. A value of 0.001 reduces the total to
    nearly zero.
    """

    shipping_address: str = Field(min_length=1, max_length=500)
    payment_method: str = Field(min_length=1, max_length=50)
    # VULN: Currency Abuse - exchange_rate accepted from client without
    # server-side validation against real exchange rates.
    # Ref: https://hackerone.com/reports/1032610
    currency: str | None = Field(default=None, max_length=3)
    exchange_rate: float | None = Field(default=None, gt=0)


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class CartItemResponse(BaseModel):
    """Single cart item with computed subtotal."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    product_name: str
    quantity: int
    unit_price: Decimal
    subtotal: Decimal
    added_at: datetime


class CartResponse(BaseModel):
    """Full cart view with items, discounts, and total."""

    items: list[CartItemResponse]
    subtotal: Decimal
    discount: Decimal
    total: Decimal
    applied_coupons: list[str]


class CouponAppliedResponse(BaseModel):
    """Result of applying a coupon to the cart."""

    code: str
    discount_type: str
    discount_value: Decimal
    discount_amount: Decimal
    new_total: Decimal


class CheckoutResponse(BaseModel):
    """Result of a successful cart checkout."""

    order_id: int
    total: Decimal
    currency: str
    status: str
