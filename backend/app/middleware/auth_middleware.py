"""Authentication dependencies for FastAPI with intentional vulnerabilities.

Provides ``get_current_user`` and ``require_role`` as FastAPI Depends()
functions. Contains deliberate weaknesses: JWT payload trusted without
database verification (VULN 7) and role checked from token not DB (VULN 9).
"""

from fastapi import Depends, HTTPException, Request, status

from app.utils.jwt import verify_token


def _extract_token(request: Request) -> str:
    """Extract JWT from Authorization header or session cookie.

    Checks the ``Authorization: Bearer <token>`` header first, then
    falls back to the ``session_token`` cookie (set by login endpoint
    with insecure flags — VULN 3 vector).

    Args:
        request: The incoming HTTP request.

    Returns:
        The raw JWT string.

    Raises:
        HTTPException: 401 if no token is found in either location.
    """
    auth_header = request.headers.get("authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:]

    # Fallback: read from cookie (VULN 3 attack surface — cookie accessible
    # to JavaScript because HttpOnly=False)
    cookie_token = request.cookies.get("session_token")
    if cookie_token:
        return cookie_token

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    token: str = Depends(_extract_token),
) -> dict:
    """Decode JWT and return user claims without database verification.

    Contains three deliberate vulnerabilities:

    - **VULN 7 (Trust Without DB Check):** Returns the JWT payload dict
      directly without querying the database to confirm the user still
      exists, is active, or has the claimed role. A deleted or deactivated
      user's token remains valid.
    - **VULN 8 (Missing Exp):** Inherited from ``verify_token()`` — tokens
      without ``exp`` are accepted.
    - **VULN 9 (Role From JWT):** The returned ``role`` comes from the
      token claims, not from the database. Combined with VULN 5 (secret
      confusion), an attacker can forge tokens with ``role=admin``.

    Args:
        token: JWT string extracted by ``_extract_token``.

    Returns:
        Dict with keys: ``user_id``, ``email``, ``username``, ``role``.

    Raises:
        HTTPException: 401 if the token cannot be decoded.
    """
    try:
        payload = verify_token(token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("user_id")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # VULN: Broken Auth - JWT payload trusted without database verification
    # A deleted/deactivated user's token continues to work. The role claim
    # is taken at face value without checking the actual DB record
    # Ref: https://hackerone.com/reports/895772
    return {
        "user_id": payload["user_id"],
        "email": payload.get("email", ""),
        "username": payload.get("username", ""),
        "role": payload.get("role", "customer"),
    }


def require_role(*allowed_roles: str):
    """Factory that returns a dependency enforcing role-based access.

    The role is read from the JWT claims (VULN 9), NOT from the database.
    Combined with VULN 5 (secret confusion), an attacker can forge a token
    with ``role=admin`` and pass this check.

    Args:
        *allowed_roles: Role strings that are permitted (e.g., "admin", "support").

    Returns:
        A FastAPI dependency function.

    Raises:
        HTTPException: 403 if the user's JWT role is not in allowed_roles.
    """

    async def _role_checker(
        current_user: dict = Depends(get_current_user),
    ) -> dict:
        # VULN: Broken Auth - Role checked from JWT claims, not database
        # An attacker who forges a token (via VULN 5) with role=admin
        # bypasses this check entirely
        # Ref: https://hackerone.com/reports/895772
        if current_user["role"] not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user

    return _role_checker
