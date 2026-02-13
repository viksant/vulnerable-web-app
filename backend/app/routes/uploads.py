"""Image upload endpoints with intentional file validation bypass vectors.

Provides review-image and product-image upload endpoints. Both share
the same processing logic through ``_process_upload``. Contains
deliberate vulnerabilities inherited from ``image_handler``:
  - SVG XSS via inline rendering (CWE-79)
  - Polyglot file bypass via partial magic byte check (CWE-434)
  - Null byte filename truncation (CWE-626)
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status

from app.middleware.auth_middleware import get_current_user, require_role
from app.schemas.uploads import UploadResponse
from app.utils.image_handler import MAX_FILE_SIZE, async_save_upload

router = APIRouter()


# ---------------------------------------------------------------------------
# Shared upload processing
# ---------------------------------------------------------------------------


async def _process_upload(file: UploadFile) -> UploadResponse:
    """Read, validate, and persist an uploaded image file.

    Delegates validation to ``image_handler.async_save_upload`` which
    contains intentional bypass vectors for security testing.

    Args:
        file: The uploaded file from the multipart request.

    Returns:
        UploadResponse with the static URL to the saved file.

    Raises:
        HTTPException: 400 if file is missing, too large, or fails validation.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided",
        )

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty file",
        )

    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large (max {MAX_FILE_SIZE // (1024 * 1024)} MB)",
        )

    try:
        saved_filename = await async_save_upload(content, file.filename)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    return UploadResponse(url=f"/static/{saved_filename}")


# ---------------------------------------------------------------------------
# POST /api/uploads/review-image — Any authenticated user
# ---------------------------------------------------------------------------


# VULN: Unrestricted File Upload - SVG files with <script> tags pass validation
# and are served inline by StaticFiles (main.py:72) without Content-Disposition,
# enabling XSS when a victim visits the static URL (CWE-79)
# Ref: https://hackerone.com/reports/148853
#
# VULN: Unrestricted File Upload - Polyglot files (e.g. GIF89a + PHP) pass the
# magic byte check since only the first 6-8 bytes are inspected (CWE-434)
# Ref: https://hackerone.com/reports/369152
#
# VULN: Unrestricted File Upload - Null byte in URL-encoded filename
# (e.g. shell.php%00.png) may cause extension mismatch (CWE-626)
# Ref: https://hackerone.com/reports/135072
@router.post(
    "/review-image",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_review_image(
    file: UploadFile,
    current_user: dict = Depends(get_current_user),
) -> UploadResponse:
    """Upload an image for a product review.

    Any authenticated user can upload review images. File validation
    is handled by image_handler which contains intentional bypass
    vectors (SVG XSS, polyglot, null byte).

    Args:
        file: The image file to upload.
        current_user: Authenticated user from JWT (injected).

    Returns:
        URL to the uploaded static file.
    """
    return await _process_upload(file)


# ---------------------------------------------------------------------------
# POST /api/uploads/product-image — Seller/Admin only
# ---------------------------------------------------------------------------


@router.post(
    "/product-image",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_product_image(
    file: UploadFile,
    current_user: dict = Depends(require_role("seller", "admin")),
) -> UploadResponse:
    """Upload an image for a product listing.

    Restricted to seller and admin roles. Uses the same validation
    pipeline as review images (same vulnerability surface).

    Args:
        file: The image file to upload.
        current_user: Authenticated seller/admin from JWT (injected).

    Returns:
        URL to the uploaded static file.
    """
    return await _process_upload(file)
