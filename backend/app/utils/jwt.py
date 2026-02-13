"""JWT token creation and verification with intentional vulnerabilities.

Provides access token and password-reset token operations. Contains
deliberate secret confusion and missing expiration checks for security
testing scenarios.
"""

from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from app.config import settings

# Access token lifetime
_ACCESS_TOKEN_EXPIRE_HOURS: int = 24

# Reset token lifetime
_RESET_TOKEN_EXPIRE_HOURS: int = 1


def create_access_token(
    user_id: int,
    email: str,
    username: str,
    role: str,
) -> str:
    """Create a signed JWT access token with full user claims.

    Args:
        user_id: Database user ID.
        email: User email address.
        username: Display username.
        role: User role (customer, seller, admin, support).

    Returns:
        Encoded JWT string signed with HS256.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "user_id": user_id,
        "email": email,
        "username": username,
        "role": role,
        "iat": now,
        "exp": now + timedelta(hours=_ACCESS_TOKEN_EXPIRE_HOURS),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def create_reset_token(user_id: int) -> str:
    """Create a password-reset JWT signed with the reset secret.

    Args:
        user_id: Database user ID requesting the reset.

    Returns:
        Encoded JWT string signed with JWT_RESET_SECRET.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "user_id": user_id,
        "purpose": "reset",
        "iat": now,
        "exp": now + timedelta(hours=_RESET_TOKEN_EXPIRE_HOURS),
    }
    return jwt.encode(payload, settings.JWT_RESET_SECRET, algorithm="HS256")


def verify_token(token: str) -> dict:
    """Decode and verify a JWT token with intentional weaknesses.

    Contains three deliberate vulnerabilities:

    - **VULN 5 (Secret Confusion):** Falls back to the weak reset secret
      when primary secret verification fails, allowing tokens forged with
      ``reset123`` to pass as valid access tokens.
    - **VULN 6 (Algorithm None):** Accepts ``none`` in the algorithms list.
      Historical: modern python-jose (>=3.3.0) may reject alg:none at the
      library level. Primary bypass path is VULN 5 instead.
    - **VULN 8 (Missing Exp):** ``verify_exp=False`` allows tokens without
      an ``exp`` claim to be accepted indefinitely.

    Args:
        token: The raw JWT string to decode.

    Returns:
        Decoded payload dictionary.

    Raises:
        JWTError: If both decode attempts fail.
    """
    # VULN: Broken Auth - Algorithm none accepted in algorithms list
    # Historical: modern python-jose (>=3.3.0) may reject alg:none
    # Primary bypass path: use VULN 5 (secret confusion) instead
    # Ref: https://auth0.com/blog/critical-vulnerabilities-in-json-web-token-libraries/
    allowed_algorithms = ["HS256", "none"]

    # VULN: Broken Auth - Missing exp verification allows tokens without
    # expiration to be accepted indefinitely (eternal sessions)
    # Ref: https://hackerone.com/reports/1047455
    decode_options = {"verify_exp": False}

    try:
        return jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=allowed_algorithms,
            options=decode_options,
        )
    except JWTError:
        # VULN: Broken Auth - Secret confusion: auth tokens can be forged
        # with weak reset secret "reset123" because fallback accepts it
        # Ref: https://hackerone.com/reports/388540
        return jwt.decode(
            token,
            settings.JWT_RESET_SECRET,
            algorithms=allowed_algorithms,
            options=decode_options,
        )
