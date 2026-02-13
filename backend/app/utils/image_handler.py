"""Image upload validation and storage with intentional bypass vectors.

Provides shared file validation for review and product image uploads.
Contains deliberate vulnerabilities:
  - SVG XSS: SVG files with text-based magic bytes pass validation
  - Polyglot bypass: Only first 8 bytes verified, rest ignored
  - Null byte filename: URL-decoded filename truncated by null byte
"""

import asyncio
import os
import urllib.parse
import uuid
from pathlib import Path

UPLOADS_DIR = Path("/app/uploads")
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB

# VULN: Unrestricted File Upload - SVG allowed in whitelist; combined with
# StaticFiles serving without Content-Disposition header (main.py:72),
# uploaded SVGs with <script> tags execute in the browser
# Ref: https://hackerone.com/reports/148853
ALLOWED_EXTENSIONS: set[str] = {".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp"}

# VULN: Unrestricted File Upload - Magic byte check only inspects the first
# 6-8 bytes. A polyglot file starting with GIF89a followed by PHP/JS payload
# passes validation. SVG entries use text prefixes, not binary magic.
# Ref: https://hackerone.com/reports/369152
MAGIC_BYTES: dict[str, list[bytes]] = {
    ".jpg": [b"\xff\xd8\xff"],
    ".jpeg": [b"\xff\xd8\xff"],
    ".png": [b"\x89PNG\r\n\x1a\n"],
    ".gif": [b"GIF87a", b"GIF89a"],
    ".svg": [b"<?xml", b"<svg"],
    ".webp": [b"RIFF"],
}


def validate_file_extension(filename: str) -> str:
    """Extract and validate the file extension from an upload filename.

    URL-decodes the filename before extracting the extension, which
    introduces a null byte truncation vulnerability: a filename like
    ``shell.php%00.png`` decodes to ``shell.php\\x00.png``, and
    ``os.path.splitext`` operates on the full string including the
    null byte.

    Args:
        filename: The original filename from the upload request.

    Returns:
        The lowercase file extension (e.g. ``.png``).

    Raises:
        ValueError: If the extension is not in ALLOWED_EXTENSIONS.
    """
    # VULN: Null Byte Filename - URL-decode before extension check allows
    # null byte injection: "shell.php%00.png" -> "shell.php\x00.png"
    # os.path.splitext sees ".png" but filesystem may truncate at null
    # Ref: https://hackerone.com/reports/135072
    decoded_filename = urllib.parse.unquote(filename)
    _, extension = os.path.splitext(decoded_filename)
    extension = extension.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError(f"File type '{extension}' not allowed")

    return extension


def validate_magic_bytes(content: bytes, extension: str) -> None:
    """Verify that file content starts with expected magic bytes.

    Only checks the first N bytes (where N is the length of the longest
    magic byte pattern for the extension). Content beyond the magic
    bytes is not inspected, enabling polyglot file uploads.

    Args:
        content: The raw file bytes.
        extension: The validated file extension.

    Raises:
        ValueError: If magic bytes do not match the extension.
    """
    expected_patterns = MAGIC_BYTES.get(extension)
    if not expected_patterns:
        return

    for pattern in expected_patterns:
        if content[: len(pattern)] == pattern:
            return

    raise ValueError("File content does not match expected format")


def save_upload(file_content: bytes, original_filename: str) -> str:
    """Validate and persist an uploaded file with a UUID4 filename.

    Orchestrates extension validation, magic byte verification, and
    writes the file to the uploads directory. Uses a UUID4 filename
    to prevent path traversal and filename collisions.

    Args:
        file_content: The raw bytes of the uploaded file.
        original_filename: The original filename from the client.

    Returns:
        The generated filename (``{uuid4}.{ext}``).

    Raises:
        ValueError: If file size exceeds MAX_FILE_SIZE, extension is
            not allowed, or magic bytes do not match.
    """
    if len(file_content) > MAX_FILE_SIZE:
        raise ValueError(
            f"File too large: {len(file_content)} bytes (max {MAX_FILE_SIZE})"
        )

    extension = validate_file_extension(original_filename)
    validate_magic_bytes(file_content, extension)

    safe_filename = f"{uuid.uuid4()}{extension}"
    file_path = UPLOADS_DIR / safe_filename
    file_path.write_bytes(file_content)

    return safe_filename


async def async_save_upload(file_content: bytes, original_filename: str) -> str:
    """Async wrapper around save_upload using a thread pool.

    Offloads the blocking file I/O to a thread to avoid blocking
    the asyncio event loop.

    Args:
        file_content: The raw bytes of the uploaded file.
        original_filename: The original filename from the client.

    Returns:
        The generated filename (``{uuid4}.{ext}``).

    Raises:
        ValueError: Propagated from save_upload.
    """
    return await asyncio.to_thread(save_upload, file_content, original_filename)
