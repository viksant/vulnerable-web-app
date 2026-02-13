"""Authentication request/response schemas.

Defines Pydantic v2 models for registration, login, password reset,
and user profile responses. ``RegisterRequest`` intentionally omits
``account_type`` to enable mass-assignment testing (VULN 1).
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class RegisterRequest(BaseModel):
    """User registration payload.

    Note: ``account_type`` is intentionally absent from the schema.
    The route handler reads it from the raw request body to simulate
    a mass-assignment vulnerability (VULN 1).
    """

    email: EmailStr
    username: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=6, max_length=128)
    full_name: str | None = Field(default=None, max_length=200)


class LoginRequest(BaseModel):
    """User login payload."""

    email: EmailStr
    password: str


class PasswordResetRequest(BaseModel):
    """Password reset initiation — only requires email."""

    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Password reset completion — token + new password."""

    token: str
    new_password: str = Field(min_length=6, max_length=128)


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class UserResponse(BaseModel):
    """Public user profile representation."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    username: str
    role: str
    full_name: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class LoginResponse(BaseModel):
    """Successful login response with JWT and user data."""

    token: str
    user: UserResponse


class TokenResponse(BaseModel):
    """Minimal token response (used by registration)."""

    token: str


class MessageResponse(BaseModel):
    """Generic message response, optionally includes a token.

    The ``reset_token`` field is used by the password-reset-request
    endpoint to leak the token in the response body (VULN 4).
    """

    message: str
    reset_token: str | None = None
