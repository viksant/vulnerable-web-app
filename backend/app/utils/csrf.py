"""CSRF token generation and validation with intentional bypasses.

Generates HMAC-SHA256 tokens stored in Redis. Validation depth varies by
difficulty level, leaving progressively fewer bypass vectors as difficulty
increases.
"""

import hashlib
import hmac
import time

from redis.asyncio import Redis

from app.config import settings

# VULN: CSRF Bypass - Hardcoded predictable secret: an attacker who reads the
# source code (or guesses the weak secret) can forge valid CSRF tokens
CSRF_SECRET: str = "csrf_not_so_secret"

# Token time-to-live in Redis (seconds)
_TOKEN_TTL: int = 3600


async def generate_csrf_token(session_id: str, redis_client: Redis) -> str:
    """Generate an HMAC-SHA256 CSRF token and store it in Redis.

    The token is derived from the session ID and current timestamp, then
    stored in Redis with a 1-hour TTL.

    Args:
        session_id: The user's session identifier.
        redis_client: Async Redis client instance.

    Returns:
        The hex-encoded CSRF token string.
    """
    timestamp = str(int(time.time()))
    message = f"{session_id}{timestamp}"
    token = hmac.new(
        CSRF_SECRET.encode(), message.encode(), hashlib.sha256
    ).hexdigest()

    # VULN: CSRF Bypass - Token not bound to user session: stored under
    # "csrf:{token}" instead of "csrf:{session_id}:{token}", so any valid
    # token works for any session — an attacker can reuse their own token
    await redis_client.set(f"csrf:{token}", session_id, ex=_TOKEN_TTL)

    return token


async def validate_csrf_token(
    token: str | None,
    session_id: str,
    redis_client: Redis,
    difficulty: str | None = None,
) -> bool:
    """Validate a CSRF token against Redis.

    Validation strictness depends on difficulty level. Lower difficulties
    have more bypass vectors for security testing.

    Args:
        token: The CSRF token from the request header or body. May be None.
        session_id: The user's session identifier.
        redis_client: Async Redis client instance.
        difficulty: Override difficulty level. Uses ``settings.DIFFICULTY``
            when not provided.

    Returns:
        True if the token is considered valid for the current difficulty.
    """
    level = difficulty or settings.DIFFICULTY

    # Easy mode: CSRF validation completely disabled
    if level == "easy":
        return True

    if level == "medium":
        # VULN: CSRF Bypass - Validation skipped without header: if no token
        # is provided at all, the request is allowed through. Attackers can
        # simply omit the X-CSRF-Token header to bypass protection
        if token is None:
            return True

        # VULN: CSRF Bypass - JSON requests exempt: requests with
        # Content-Type: application/json skip CSRF validation entirely,
        # based on the outdated assumption that JSON can't be sent cross-origin
        # (modern browsers allow it via fetch API with no-cors mode limitations,
        # but navigator.sendBeacon and form-based techniques can still exploit this)

        # Check if token exists in Redis (not session-bound)
        stored = await redis_client.get(f"csrf:{token}")
        return stored is not None

    # Hard mode: stricter but still not session-bound
    if token is None:
        return False

    stored = await redis_client.get(f"csrf:{token}")
    return stored is not None
