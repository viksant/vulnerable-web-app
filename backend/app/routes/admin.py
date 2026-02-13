"""Admin panel endpoints with intentional vulnerabilities.

Provides admin configuration viewing, user listing, report generation,
and log file reading. Contains deliberate vulnerabilities:
  - Missing authentication on config endpoint (CWE-306)
  - Sensitive data exposure via password hash leak (CWE-200)
  - Command injection via subprocess with shell=True (CWE-78)
  - Path traversal via bypassable ".." filter (CWE-22)
"""

import re
import subprocess
from pathlib import Path
from urllib.parse import unquote

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.middleware.auth_middleware import require_role
from app.models.user import User

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ReportRequest(BaseModel):
    """Report generation request body.

    Attributes:
        template_name: Report template identifier (e.g. "sales", "inventory").
        date_range: Date range string for the report period.
    """

    template_name: str
    date_range: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ALLOWED_TEMPLATES: list[str] = ["sales", "inventory", "users", "reviews"]

LOGS_BASE_DIR = Path("/app/logs")


def _get_config_data() -> dict:
    """Extract application settings into a plain dict for API response.

    Returns:
        Dict with database credentials, JWT secrets, and debug mode flag.
    """
    return {
        "db_host": settings.DB_HOST,
        "db_port": settings.DB_PORT,
        "db_user": settings.DB_USER,
        "db_password": settings.DB_PASSWORD,
        "db_name": settings.DB_NAME,
        "jwt_secret": settings.JWT_SECRET,
        "jwt_reset_secret": settings.JWT_RESET_SECRET,
        "debug_mode": settings.DEBUG,
        "difficulty": settings.DIFFICULTY,
    }


# ---------------------------------------------------------------------------
# GET /config (VULN 1: Missing Auth + Sensitive Data Exposure)
# ---------------------------------------------------------------------------


# VULN: Sensitive Data Exposure - Config endpoint accessible without authentication.
# Exposes database credentials, JWT signing secret, and internal configuration.
# No Depends(get_current_user) — any unauthenticated request retrieves secrets.
# Ref: https://hackerone.com/reports/895772
@router.get("/config")
async def get_config() -> dict:
    """Return application configuration including secrets.

    **VULN (CWE-306):** This endpoint has NO authentication dependency.
    Any unauthenticated user can retrieve database credentials, JWT
    secrets, and internal configuration.

    Returns:
        Dict with all sensitive application settings.
    """
    return {
        "app_name": "VulnShop",
        "version": "1.0.0",
        "config": _get_config_data(),
    }


# ---------------------------------------------------------------------------
# GET /users (VULN 2: Password Hash Exposure)
# ---------------------------------------------------------------------------


# VULN: Sensitive Data Exposure - User listing includes password_hash field.
# Some seed users have MD5 hashes (crackable via rainbow tables).
# Ref: https://hackerone.com/reports/766507
@router.get("/users")
async def list_all_users(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role("admin")),
) -> list[dict]:
    """List all users with full details including password hashes.

    **VULN (CWE-200):** Returns password_hash for every user. Some seed
    accounts use MD5 hashes that are trivially crackable via rainbow
    tables or online lookup services.

    Args:
        db: Database session (injected).
        current_user: Authenticated admin from JWT (injected).

    Returns:
        List of user dicts with all fields including password_hash.
    """
    result = await db.execute(select(User).order_by(User.id))
    users = result.scalars().all()

    return [
        {
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "password_hash": user.password_hash,
            "role": user.role,
            "full_name": user.full_name,
            "phone": user.phone,
            "is_active": user.is_active,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        }
        for user in users
    ]


# ---------------------------------------------------------------------------
# POST /generate-report (VULN 3+4: Command Injection)
# ---------------------------------------------------------------------------


# VULN: Command Injection - Two vectors:
# 1. re.match() only validates the START of date_range; a newline (\n) followed
#    by arbitrary shell commands passes validation. Example payload:
#    "2024-01-01\n;id" — re.match succeeds, shell executes "id" after newline.
# 2. shell=True with f-string interpolation allows command chaining via
#    semicolons, pipes, or backticks embedded in date_range.
# Ref: https://hackerone.com/reports/680480
@router.post("/generate-report")
async def generate_report(
    body: ReportRequest,
    current_user: dict = Depends(require_role("admin")),
) -> dict:
    """Generate a report by executing a shell command.

    **VULN (CWE-78):** The ``date_range`` parameter is validated with
    ``re.match()`` which only checks the START of the string. A payload
    like ``2024-01-01\\n;id`` passes validation because the regex matches
    the prefix. The value is then interpolated into a shell command with
    ``shell=True``, enabling arbitrary command execution.

    Args:
        body: Report request with template_name and date_range.
        current_user: Authenticated admin from JWT (injected).

    Returns:
        Dict with report output (stdout) and any errors (stderr).

    Raises:
        HTTPException: 400 if template_name is not in the allowed list
            or date_range fails the (bypassable) regex check.
    """
    if body.template_name not in ALLOWED_TEMPLATES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid template. Allowed: {ALLOWED_TEMPLATES}",
        )

    # VULN: re.match() only validates the BEGINNING of the string.
    # It does NOT ensure the entire string matches the date pattern.
    # Payload "2024-01-01\n;id" passes because "2024-01-01" matches at start.
    if not re.match(r"^\d{4}-\d{2}-\d{2}", body.date_range):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid date_range format. Expected: YYYY-MM-DD",
        )

    # VULN: shell=True with f-string — user-controlled date_range injected
    # directly into shell command. Combined with the weak regex above,
    # an attacker achieves arbitrary command execution.
    command = (
        f"python -c \"print('Report: {body.template_name}"
        f" for {body.date_range}')\""
    )
    result = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
        timeout=10,
    )

    return {
        "template": body.template_name,
        "date_range": body.date_range,
        "report": result.stdout,
        "errors": result.stderr if result.stderr else None,
    }


# ---------------------------------------------------------------------------
# GET /logs (VULN 5: Path Traversal)
# ---------------------------------------------------------------------------


# VULN: Path Traversal - The ".." filter only checks for the literal string "..".
# URL-encoded variants bypass the check because FastAPI decodes the query param
# once, but unquote() below performs a SECOND decode. Double-encoded payloads
# like "%252e%252e" survive the first decode as "%2e%2e" (no ".."), then the
# second unquote() produces ".." for actual traversal.
# Ref: https://hackerone.com/reports/1888608
@router.get("/logs")
async def read_log_file(
    file: str = "app.log",
    current_user: dict = Depends(require_role("admin")),
) -> PlainTextResponse:
    """Read a log file from the server logs directory.

    **VULN (CWE-22):** The path traversal filter only checks for the
    literal ``..`` string after FastAPI's first URL decode. A second
    ``unquote()`` call is applied AFTER the check, so double-encoded
    payloads bypass the filter:

    - ``%252e%252e/`` -> first decode -> ``%2e%2e/`` (no "..") -> passes
      check -> second decode -> ``../`` -> path traversal achieved.
    - ``..%252f`` -> first decode -> ``..%2f`` -> caught by ".." check.
      But ``%252e%252e%252f`` -> ``%2e%2e%2f`` -> passes -> ``../``.

    Args:
        file: Log filename (default: "app.log"). Accepts path components.
        current_user: Authenticated admin from JWT (injected).

    Returns:
        PlainTextResponse with the file contents.

    Raises:
        HTTPException: 400 if ".." literal is detected, 404 if file not found.
    """
    # VULN: Only blocks literal ".." — double-encoded traversal bypasses this
    if ".." in file:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Path traversal detected",
        )

    # VULN: Second URL decode AFTER security check — double-encoded ".."
    # (%252e%252e) passes the check above as "%2e%2e", then becomes ".." here
    decoded_file = unquote(file)

    file_path = LOGS_BASE_DIR / decoded_file

    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Log file not found: {file}",
        )

    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except (OSError, PermissionError) as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Cannot read file: {exc}",
        )

    return PlainTextResponse(content=content)
