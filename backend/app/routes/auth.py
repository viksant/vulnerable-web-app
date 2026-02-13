"""Authentication routes with intentional vulnerabilities.

Provides registration, login, password reset, and profile endpoints.
Contains deliberate weaknesses for security testing: mass assignment,
user enumeration via timing, insecure cookies, and token leakage.
"""

import json

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth_middleware import get_current_user
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    MessageResponse,
    PasswordResetConfirm,
    PasswordResetRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.utils.jwt import create_access_token, create_reset_token, verify_token
from app.utils.password import hash_password, verify_password

router = APIRouter()


# ---------------------------------------------------------------------------
# POST /register
# ---------------------------------------------------------------------------


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Register a new user account.

    VULN 1 (Mass Assignment): The Pydantic schema only validates
    ``email``, ``username``, ``password``, and ``full_name``. However,
    the handler also reads the raw request body to check for a hidden
    ``account_type`` field. Sending ``"account_type": "seller"`` in the
    JSON body assigns the seller role instead of the default customer.

    Args:
        payload: Validated registration fields.
        request: Raw HTTP request (for hidden field extraction).
        db: Async database session.

    Returns:
        JWT access token for the new account.

    Raises:
        HTTPException: 409 if email or username already exists.
    """
    # Check email uniqueness
    existing_email = await db.execute(
        select(User).where(User.email == payload.email)
    )
    if existing_email.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    # Check username uniqueness
    existing_username = await db.execute(
        select(User).where(User.username == payload.username)
    )
    if existing_username.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already taken",
        )

    # VULN: Mass Assignment - Hidden account_type field not in Pydantic schema
    # allows role escalation. Sending {"account_type": "seller"} in the JSON
    # body assigns seller role bypassing schema validation
    # Ref: https://hackerone.com/reports/783877
    role = "customer"
    try:
        raw_body = await request.body()
        body_dict = json.loads(raw_body)
        if body_dict.get("account_type") == "seller":
            role = "seller"
    except (json.JSONDecodeError, UnicodeDecodeError):
        pass

    hashed = hash_password(payload.password)

    new_user = User(
        email=payload.email,
        username=payload.username,
        password_hash=hashed,
        role=role,
        full_name=payload.full_name,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    token = create_access_token(
        user_id=new_user.id,
        email=new_user.email,
        username=new_user.username,
        role=new_user.role,
    )

    return TokenResponse(token=token)


# ---------------------------------------------------------------------------
# POST /login
# ---------------------------------------------------------------------------


@router.post("/login", response_model=LoginResponse)
async def login(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Authenticate a user and return a JWT.

    VULN 2 (User Enumeration via Timing): When the email does not exist,
    the endpoint returns immediately (~0 ms). When the email exists but
    the password is wrong, bcrypt verification adds ~200 ms. An attacker
    can measure response times to determine which emails are registered.

    VULN 3 (Insecure Cookie): The JWT is also set as a ``session_token``
    cookie with ``httponly=False`` and ``secure=False``, making it
    accessible to JavaScript (XSS exfiltration) and sent over HTTP.

    Args:
        payload: Email and password.
        db: Async database session.

    Returns:
        JSON response with JWT token, user data, and insecure Set-Cookie.

    Raises:
        HTTPException: 401 if credentials are invalid.
    """
    result = await db.execute(
        select(User).where(User.email == payload.email)
    )
    user = result.scalar_one_or_none()

    # VULN: User Enumeration - Timing side-channel: non-existent email
    # returns instantly, existing email goes through bcrypt (~200ms)
    # Ref: https://hackerone.com/reports/396467
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account deactivated",
        )

    token = create_access_token(
        user_id=user.id,
        email=user.email,
        username=user.username,
        role=user.role,
    )

    user_data = UserResponse.model_validate(user)
    body = LoginResponse(token=token, user=user_data)

    response = JSONResponse(
        content=body.model_dump(mode="json"),
        status_code=status.HTTP_200_OK,
    )

    # VULN: Insecure Cookie - session_token set without HttpOnly and Secure
    # flags, allowing JavaScript access (XSS theft) and HTTP transmission
    # Ref: https://hackerone.com/reports/58679
    response.set_cookie(
        key="session_token",
        value=token,
        httponly=False,
        secure=False,
        samesite="lax",
    )

    return response


# ---------------------------------------------------------------------------
# POST /password-reset-request
# ---------------------------------------------------------------------------


@router.post("/password-reset-request", response_model=MessageResponse)
async def password_reset_request(
    payload: PasswordResetRequest,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Initiate a password reset flow.

    VULN 4 (Reset Token in Response): Instead of sending the reset token
    via email only, the endpoint returns it directly in the JSON response
    body. This simulates a debug/development endpoint accidentally left
    in production.

    Args:
        payload: Email address to reset.
        db: Async database session.

    Returns:
        Message with the reset token leaked in the response body (if user exists).
    """
    result = await db.execute(
        select(User).where(User.email == payload.email)
    )
    user = result.scalar_one_or_none()

    if not user:
        # Generic response to avoid email enumeration on this endpoint
        return MessageResponse(message="If the email exists, a reset link has been sent")

    reset_token = create_reset_token(user_id=user.id)

    # VULN: Info Disclosure - Reset token returned in response body
    # In production this should only be sent via email, never in the API response
    # Ref: https://hackerone.com/reports/342693
    return MessageResponse(
        message="Password reset email sent",
        reset_token=reset_token,
    )


# ---------------------------------------------------------------------------
# POST /password-reset
# ---------------------------------------------------------------------------


@router.post("/password-reset", response_model=MessageResponse)
async def password_reset(
    payload: PasswordResetConfirm,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Complete a password reset using a token.

    Accepts tokens verified by ``verify_token()``, which includes
    VULN 5 (secret confusion) — tokens signed with either secret are valid.

    Args:
        payload: Reset token and new password.
        db: Async database session.

    Returns:
        Success message.

    Raises:
        HTTPException: 400 if token is invalid or user not found.
    """
    try:
        token_payload = verify_token(payload.token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    # Verify this is actually a reset token, not a repurposed access token
    if token_payload.get("purpose") != "reset":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid reset token",
        )

    user_id = token_payload.get("user_id")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid token payload",
        )

    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    user.password_hash = hash_password(payload.new_password)
    await db.commit()

    return MessageResponse(message="Password reset successful")


# ---------------------------------------------------------------------------
# GET /me
# ---------------------------------------------------------------------------


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Return the authenticated user's full profile from the database.

    Unlike ``get_current_user`` (which trusts JWT claims), this endpoint
    queries the database for the actual user record.

    Args:
        current_user: JWT claims dict from auth dependency.
        db: Async database session.

    Returns:
        Full user profile from the database.

    Raises:
        HTTPException: 404 if the user no longer exists in the database.
    """
    result = await db.execute(
        select(User).where(User.id == current_user["user_id"])
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return UserResponse.model_validate(user)
