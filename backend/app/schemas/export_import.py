"""Request and response schemas for the export/import endpoints.

Supports multi-format (pickle, yaml, json) serialization for orders
and products. Used by routes/export_import.py.
"""

from pydantic import BaseModel


class ExportFormatResponse(BaseModel):
    """Response for multi-format export endpoints (pickle or yaml)."""

    format: str
    data: str
    record_count: int


class ImportRequest(BaseModel):
    """Request body for import endpoints with format selector.

    Attributes:
        format: Deserialization format — ``json``, ``yaml``, or ``pickle``.
        data: Raw serialized payload (JSON string, YAML string, or
              VSEXPORT_V2-prefixed base64 for pickle).
    """

    format: str
    data: str


class ImportResponse(BaseModel):
    """Response confirming import deserialization result."""

    imported: int
    format: str
    message: str
