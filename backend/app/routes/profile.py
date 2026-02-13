"""User profile management with intentional CSRF vulnerabilities.

Provides profile viewing, updating, email/password change, and payment
method management. Several endpoints deliberately lack or incorrectly
implement CSRF protection to serve as testing targets for security scanners.

VULN Summary:
  - PUT  /profile           → CSRF bypass when X-CSRF-Token header absent
  - GET  /change-email      → State change via GET (CSRF via external link)
  - POST /change-email      → Missing password confirmation (ATO chain)
  - POST /change-password   → No CSRF + accepts text/plain (no preflight)
  - GET  /csrf-token        → Session-unbound token (reusable cross-user)
"""

import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth_middleware import get_current_user
from app.models.user import User
from app.utils.csrf import generate_csrf_token, validate_csrf_token
from app.utils.password import hash_password
from app.utils.redis import get_redis

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic schemas (local to profile module)
# ---------------------------------------------------------------------------


class ProfileResponse(BaseModel):
    """Full user profile response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    username: str
    role: str
    full_name: str | None
    phone: str | None
    address: str | None
    payment_method_last4: str | None
    card_type: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ProfileUpdateRequest(BaseModel):
    """Profile update fields (PUT /api/profile)."""

    username: str | None = None
    full_name: str | None = None
    phone: str | None = None
    address: str | None = None


class ChangeEmailRequest(BaseModel):
    """Email change request (POST body)."""

    new_email: EmailStr


class PaymentMethodRequest(BaseModel):
    """Payment method update request."""

    card_last4: str = Field(min_length=4, max_length=4)
    card_type: str = Field(max_length=20)


class CsrfTokenResponse(BaseModel):
    """CSRF token response."""

    csrf_token: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_user_by_id(user_id: int, db: AsyncSession) -> User:
    """Fetch a user by primary key or raise 404.

    Args:
        user_id: The user's integer ID.
        db: Async database session.

    Returns:
        The User ORM instance.

    Raises:
        HTTPException: 404 if user not found.
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return user


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("")
async def get_profile(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProfileResponse:
    """Return the authenticated user's full profile.

    No vulnerabilities — read-only endpoint.

    Args:
        current_user: JWT claims dict from auth middleware.
        db: Async database session.

    Returns:
        ProfileResponse with all user fields.
    """
    user = await _get_user_by_id(current_user["user_id"], db)
    return ProfileResponse.model_validate(user)


# VULN: CSRF Bypass - CSRF validation skipped when X-CSRF-Token header is
# absent. Uses validate_csrf_token() in medium difficulty mode which returns
# True when token is None (see utils/csrf.py:82). An attacker can submit a
# cross-origin form without the header to modify the victim's profile.
# Ref: https://hackerone.com/reports/1629828
@router.put("")
async def update_profile(
    payload: ProfileUpdateRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> ProfileResponse:
    """Update profile fields with flawed CSRF protection.

    CSRF token is only validated when the ``X-CSRF-Token`` header is
    present. If omitted entirely, the request passes through (medium
    difficulty bypass in ``validate_csrf_token``).

    Args:
        payload: Fields to update (username, full_name, phone, address).
        request: Raw request for header access.
        current_user: JWT claims dict from auth middleware.
        db: Async database session.
        redis: Redis client for CSRF token lookup.

    Returns:
        Updated ProfileResponse.

    Raises:
        HTTPException: 403 if a CSRF token is provided but invalid.
    """
    csrf_token = request.headers.get("x-csrf-token")
    session_id = str(current_user["user_id"])

    # VULN: CSRF Bypass - When csrf_token is None (header absent),
    # validate_csrf_token returns True in medium mode, skipping validation
    is_valid = await validate_csrf_token(csrf_token, session_id, redis)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid CSRF token",
        )

    user = await _get_user_by_id(current_user["user_id"], db)

    if payload.username is not None:
        user.username = payload.username
    if payload.full_name is not None:
        user.full_name = payload.full_name
    if payload.phone is not None:
        user.phone = payload.phone
    if payload.address is not None:
        user.address = payload.address

    await db.commit()
    await db.refresh(user)
    return ProfileResponse.model_validate(user)


# VULN: Missing Password Confirm - Email changed without requiring current
# password. Combined with password reset flow, enables full account takeover:
# attacker changes email → requests password reset → controls the account.
# Ref: https://hackerone.com/reports/1086752
#
# VULN: CSRF via GET Method - Registered for both GET and POST. GET requests
# with SameSite=Lax cookies are sent on top-level navigation, so an external
# link like <a href="/api/profile/change-email?new_email=attacker@evil.com">
# changes the victim's email on click.
# Ref: https://hackerone.com/reports/1484020
@router.api_route("/change-email", methods=["GET", "POST"])
async def change_email(
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Change the user's email address without password confirmation.

    Accepts both GET (query param) and POST (JSON body) methods.
    Neither requires the current password, enabling account takeover
    chains when combined with password reset.

    Args:
        request: Raw request for method detection and param extraction.
        current_user: JWT claims dict from auth middleware.
        db: Async database session.

    Returns:
        Success message with old and new email addresses.

    Raises:
        HTTPException: 400 if new_email is missing or empty.
    """
    # VULN: GET Method accepts state change - Query param on GET request
    if request.method == "GET":
        new_email = request.query_params.get("new_email")
    else:
        body = ChangeEmailRequest(**(await request.json()))
        new_email = body.new_email

    if not new_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="new_email is required",
        )

    user = await _get_user_by_id(current_user["user_id"], db)
    old_email = user.email

    # VULN: Missing Password Confirm - No current password verification
    user.email = new_email

    await db.commit()
    await db.refresh(user)

    return {
        "message": "Email updated successfully",
        "old_email": old_email,
        "new_email": user.email,
    }


# VULN: Missing CSRF + text/plain bypass - No CSRF token validation at all.
# Accepts Content-Type: text/plain which is a "simple" content type that
# does NOT trigger a CORS preflight request. An attacker page can submit:
#   <form method="POST" enctype="text/plain" action="/api/profile/change-password">
#     <input name='{"new_password":"hacked123","x":"' value='"}'>
#   </form>
# The browser sends the POST without preflight, changing the password.
# Also does NOT require old_password for additional weakness.
# Ref: https://hackerone.com/reports/1594237
@router.post("/change-password")
async def change_password(
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Change password without CSRF protection or old password verification.

    Parses the request body manually (not via Pydantic) to accept
    ``text/plain`` Content-Type, which browsers treat as a "simple"
    request that skips CORS preflight. No CSRF token is checked.

    Args:
        request: Raw request for manual body parsing.
        current_user: JWT claims dict from auth middleware.
        db: Async database session.

    Returns:
        Success message confirming password change.

    Raises:
        HTTPException: 400 if body parsing fails or new_password is missing.
    """
    # VULN: Missing CSRF - No CSRF token validation on this endpoint
    # Parse body manually to accept text/plain content type
    try:
        raw_body = await request.body()
        data = json.loads(raw_body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid request body",
        )

    new_password = data.get("new_password")
    if not new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="new_password is required",
        )

    user = await _get_user_by_id(current_user["user_id"], db)

    # VULN: No old_password verification — attacker only needs session
    user.password_hash = hash_password(new_password)

    await db.commit()

    return {"message": "Password changed successfully"}


@router.post("/payment-method")
async def update_payment_method(
    payload: PaymentMethodRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> dict:
    """Update payment method with proper CSRF validation (intentional contrast).

    This endpoint correctly validates the CSRF token, rejecting requests
    where the token is missing or invalid. Serves as a deliberate contrast
    to the other profile endpoints where CSRF protection is flawed or
    absent, demonstrating that the mechanism exists but was inconsistently
    applied.

    Args:
        payload: Card last4 digits and card type.
        request: Raw request for CSRF header extraction.
        current_user: JWT claims dict from auth middleware.
        db: Async database session.
        redis: Redis client for CSRF token lookup.

    Returns:
        Success message with masked card info.

    Raises:
        HTTPException: 403 if CSRF token is missing or invalid.
    """
    csrf_token = request.headers.get("x-csrf-token")
    session_id = str(current_user["user_id"])

    # Correct CSRF validation — always require a valid token
    if not csrf_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token required",
        )

    is_valid = await validate_csrf_token(
        csrf_token, session_id, redis, difficulty="hard"
    )
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid CSRF token",
        )

    user = await _get_user_by_id(current_user["user_id"], db)
    user.payment_method_last4 = payload.card_last4
    user.card_type = payload.card_type

    await db.commit()
    await db.refresh(user)

    return {
        "message": "Payment method updated",
        "card_last4": user.payment_method_last4,
        "card_type": user.card_type,
    }


# VULN: Session-Unbound CSRF Token - Token generated with a fixed
# "anonymous" session ID instead of the actual user's session. Any
# unauthenticated visitor can obtain a token and reuse it for any user's
# CSRF-protected request, since the token-to-session binding is absent.
# Ref: https://hackerone.com/reports/1629828
async def csrf_token_endpoint(
    redis: Redis = Depends(get_redis),
) -> CsrfTokenResponse:
    """Generate a CSRF token not bound to any user session.

    Public endpoint (no authentication required). The generated token
    is stored in Redis under ``csrf:{token}`` with a generic session ID,
    making it reusable across any user session.

    Args:
        redis: Redis client for token storage.

    Returns:
        CsrfTokenResponse with the generated token.
    """
    # VULN: Session-Unbound Token - "anonymous" instead of actual session_id
    token = await generate_csrf_token("anonymous", redis)
    return CsrfTokenResponse(csrf_token=token)
