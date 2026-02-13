"""Upload response schemas for image file endpoints."""

from pydantic import BaseModel


class UploadResponse(BaseModel):
    """Response returned after a successful file upload.

    Attributes:
        url: Relative URL to access the uploaded file (e.g. ``/static/{uuid}.png``).
    """

    url: str
