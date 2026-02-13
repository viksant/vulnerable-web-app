"""Export and import endpoints with intentional insecure deserialization vulnerabilities.

Provides multi-format export (pickle, yaml) and import (json, yaml, pickle)
for orders and products. Contains three escalating deserialization VULNs:
  - VULN 1: jsonpickle RCE via py/reduce (EASY — CWE-502)
  - VULN 2: YAML FullLoader RCE via !!python/object/new (MEDIUM — CWE-502)
  - VULN 3: Pickle RestrictedUnpickler bypass via startsWith (HARD — CWE-502)

Two routers: export_router (prefix /api/export) and import_router (prefix /api/import).
"""

import base64
import pickle
from typing import Any

import yaml
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.middleware.auth_middleware import require_role
from app.models.order import Order
from app.models.product import Product
from app.schemas.export_import import ExportFormatResponse, ImportRequest, ImportResponse
from app.utils.serializer import jsonpickle_decode, safe_pickle_loads, safe_yaml_load

export_router = APIRouter()
import_router = APIRouter()

EXPORT_PREFIX = "VSEXPORT_V2:"
VALID_EXPORT_FORMATS = {"pickle", "yaml"}
VALID_IMPORT_FORMATS = {"json", "yaml", "pickle"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _serialize_orders(orders: list[Order]) -> list[dict[str, Any]]:
    """Convert ORM Order instances to plain dicts for serialization.

    Args:
        orders: List of Order ORM instances with items relationship loaded.

    Returns:
        List of dicts with order fields and nested item dicts.
    """
    result: list[dict[str, Any]] = []
    for order in orders:
        result.append({
            "id": order.id,
            "uuid": order.uuid,
            "user_id": order.user_id,
            "status": order.status,
            "total": str(order.total),
            "shipping_addr": order.shipping_addr,
            "created_at": (
                order.created_at.isoformat() if order.created_at else None
            ),
            "items": [
                {
                    "product_id": item.product_id,
                    "quantity": item.quantity,
                    "unit_price": str(item.unit_price),
                }
                for item in order.items
            ],
        })
    return result


def _serialize_products(products: list[Product]) -> list[dict[str, Any]]:
    """Convert ORM Product instances to plain dicts for serialization.

    Args:
        products: List of Product ORM instances.

    Returns:
        List of dicts with product fields.
    """
    result: list[dict[str, Any]] = []
    for product in products:
        result.append({
            "id": product.id,
            "name": product.name,
            "description": product.description,
            "price": str(product.price),
            "stock": product.stock,
            "category": product.category,
            "image_url": product.image_url,
            "seller_id": product.seller_id,
            "is_active": product.is_active,
            "created_at": (
                product.created_at.isoformat() if product.created_at else None
            ),
        })
    return result


def _encode_payload(data: list[dict[str, Any]], fmt: str) -> str:
    """Serialize and encode data in the requested format with VSEXPORT_V2 prefix.

    Args:
        data: List of dicts to serialize.
        fmt: Serialization format — ``pickle`` or ``yaml``.

    Returns:
        VSEXPORT_V2-prefixed base64-encoded string.

    Raises:
        ValueError: If the format is not supported.
    """
    if fmt == "pickle":
        raw = pickle.dumps(data)
    elif fmt == "yaml":
        raw = yaml.dump(data, default_flow_style=False).encode("utf-8")
    else:
        raise ValueError(f"Unsupported export format: {fmt}")

    encoded = base64.b64encode(raw).decode("ascii")
    return f"{EXPORT_PREFIX}{encoded}"


def _dispatch_import(fmt: str, data: str) -> Any:
    """Route import data to the correct deserialization function.

    Args:
        fmt: Deserialization format — ``json``, ``yaml``, or ``pickle``.
        data: Raw serialized payload.

    Returns:
        The deserialized Python object.

    Raises:
        HTTPException: 400 if the format is invalid or deserialization fails.
    """
    if fmt not in VALID_IMPORT_FORMATS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid format '{fmt}'. Allowed: {', '.join(sorted(VALID_IMPORT_FORMATS))}",
        )

    try:
        if fmt == "json":
            return jsonpickle_decode(data)
        if fmt == "yaml":
            return safe_yaml_load(data)
        # fmt == "pickle"
        return safe_pickle_loads(data)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Deserialization error: {exc}",
        ) from exc


def _build_import_response(result: Any, fmt: str) -> ImportResponse:
    """Build an ImportResponse from the deserialized data.

    Args:
        result: Deserialized Python object.
        fmt: The format that was used.

    Returns:
        ImportResponse with record count and confirmation message.
    """
    record_count = len(result) if isinstance(result, (list, dict)) else 1
    return ImportResponse(
        imported=record_count,
        format=fmt,
        message=f"Successfully deserialized {record_count} record(s) via {fmt}",
    )


# ---------------------------------------------------------------------------
# GET /api/export/orders — Multi-format order export
# ---------------------------------------------------------------------------


@export_router.get("/orders", response_model=ExportFormatResponse)
async def export_orders(
    format: str = "pickle",
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role("admin", "seller", "support")),
) -> ExportFormatResponse:
    """Export orders in pickle or yaml format.

    Sellers see only their own orders. Admin and support see all.
    Data is serialized, base64-encoded, and prefixed with VSEXPORT_V2.

    Args:
        format: Export format — ``pickle`` (default) or ``yaml``.
        db: Database session (injected).
        current_user: Authenticated user with admin/seller/support role (injected).

    Returns:
        ExportFormatResponse with VSEXPORT_V2-prefixed encoded data.

    Raises:
        HTTPException: 400 if format is not supported.
    """
    if format not in VALID_EXPORT_FORMATS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid format '{format}'. Allowed: {', '.join(sorted(VALID_EXPORT_FORMATS))}",
        )

    # Sellers see only their own orders; admin/support see all
    stmt = select(Order).options(selectinload(Order.items))
    if current_user["role"] == "seller":
        stmt = stmt.where(Order.user_id == current_user["user_id"])

    result = await db.execute(stmt)
    orders = result.scalars().all()

    export_data = _serialize_orders(list(orders))
    encoded = _encode_payload(export_data, format)

    return ExportFormatResponse(
        format=format,
        data=encoded,
        record_count=len(export_data),
    )


# ---------------------------------------------------------------------------
# POST /api/import/orders — Insecure deserialization (VULN 1 + 2 + 3)
# ---------------------------------------------------------------------------


# VULN: Insecure Deserialization - Three escalating RCE vectors depending
# on the chosen format:
#   format=json   -> jsonpickle.decode() executes py/reduce (EASY)
#   format=yaml   -> yaml.load(FullLoader) allows !!python/object/new (MEDIUM)
#   format=pickle -> RestrictedUnpickler with bypassable startsWith (HARD)
# Ref: https://hackerone.com/reports/350401 (jsonpickle)
# Ref: https://hackerone.com/reports/1415436 (yaml)
# Ref: https://hackerone.com/reports/2334460 (pickle)
@import_router.post("/orders", response_model=ImportResponse)
async def import_orders(
    body: ImportRequest,
    current_user: dict = Depends(require_role("admin", "seller")),
) -> ImportResponse:
    """Import orders via deserialization — intentionally vulnerable.

    Dispatches to the appropriate deserializer based on ``body.format``.
    Does NOT write to the database — only deserializes and returns the
    record count. The deserialization itself is the attack surface.

    Args:
        body: ImportRequest with format and serialized data.
        current_user: Authenticated admin or seller (injected).

    Returns:
        ImportResponse confirming the number of deserialized records.
    """
    result = _dispatch_import(body.format, body.data)
    return _build_import_response(result, body.format)


# ---------------------------------------------------------------------------
# GET /api/export/products — Multi-format product export
# ---------------------------------------------------------------------------


@export_router.get("/products", response_model=ExportFormatResponse)
async def export_products(
    format: str = "pickle",
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role("admin", "seller", "support")),
) -> ExportFormatResponse:
    """Export products in pickle or yaml format.

    Sellers see only their own products. Admin and support see all.
    Data is serialized, base64-encoded, and prefixed with VSEXPORT_V2.

    Args:
        format: Export format — ``pickle`` (default) or ``yaml``.
        db: Database session (injected).
        current_user: Authenticated user with admin/seller/support role (injected).

    Returns:
        ExportFormatResponse with VSEXPORT_V2-prefixed encoded data.

    Raises:
        HTTPException: 400 if format is not supported.
    """
    if format not in VALID_EXPORT_FORMATS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid format '{format}'. Allowed: {', '.join(sorted(VALID_EXPORT_FORMATS))}",
        )

    # Sellers see only their own products; admin/support see all
    stmt = select(Product)
    if current_user["role"] == "seller":
        stmt = stmt.where(Product.seller_id == current_user["user_id"])

    result = await db.execute(stmt)
    products = result.scalars().all()

    export_data = _serialize_products(list(products))
    encoded = _encode_payload(export_data, format)

    return ExportFormatResponse(
        format=format,
        data=encoded,
        record_count=len(export_data),
    )


# ---------------------------------------------------------------------------
# POST /api/import/products — Insecure deserialization (same VULNs)
# ---------------------------------------------------------------------------


# VULN: Insecure Deserialization - Same three RCE vectors as /import/orders.
# Reuses the same deserializer dispatch — attack surface is identical.
# Ref: https://hackerone.com/reports/350401 (jsonpickle)
# Ref: https://hackerone.com/reports/1415436 (yaml)
# Ref: https://hackerone.com/reports/2334460 (pickle)
@import_router.post("/products", response_model=ImportResponse)
async def import_products(
    body: ImportRequest,
    current_user: dict = Depends(require_role("admin", "seller")),
) -> ImportResponse:
    """Import products via deserialization — intentionally vulnerable.

    Dispatches to the appropriate deserializer based on ``body.format``.
    Does NOT write to the database — only deserializes and returns the
    record count. The deserialization itself is the attack surface.

    Args:
        body: ImportRequest with format and serialized data.
        current_user: Authenticated admin or seller (injected).

    Returns:
        ImportResponse confirming the number of deserialized records.
    """
    result = _dispatch_import(body.format, body.data)
    return _build_import_response(result, body.format)
