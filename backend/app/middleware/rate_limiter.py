"""Redis-backed rate limiting middleware with intentional bypasses.

Enforces per-endpoint and global request rate limits using Redis counters.
Difficulty level controls which bypass vectors are available to attackers.
"""

import logging

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.config import settings

logger = logging.getLogger(__name__)

# Paths excluded from rate limiting (health checks, documentation)
EXCLUDED_PATHS: set[str] = {
    "/health",
    "/api/docs",
    "/api/redoc",
    "/api/openapi.json",
}

# Per-endpoint rate limits: {path: (max_requests, window_seconds)}
# "__global__" is the fallback for paths without a specific limit.
RATE_LIMITS: dict[str, tuple[int, int]] = {
    "/api/auth/login": (10, 60),
    "/api/auth/register": (5, 60),
    "/api/cart/apply-coupon": (20, 60),
    "__global__": (60, 60),
}


def _get_client_ip(request: Request) -> str:
    """Extract the client IP address from the request.

    Args:
        request: The incoming HTTP request.

    Returns:
        The resolved client IP string.
    """
    # VULN: Rate Limit Bypass - Blind XFF trust: any client can spoof their IP
    # by setting the X-Forwarded-For header to an arbitrary value
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()

    return request.client.host if request.client else "unknown"


def _get_rate_limit(path: str, difficulty: str) -> tuple[int, int]:
    """Look up the rate limit configuration for a given path.

    Args:
        path: The request URL path.
        difficulty: Current difficulty level from settings.

    Returns:
        Tuple of (max_requests, window_seconds).
    """
    # VULN: Rate Limit Bypass - Case-sensitive endpoint matching on medium
    # /API/AUTH/LOGIN or /Api/Auth/Login bypasses the specific limit
    if difficulty == "hard":
        normalized = path.lower()
        for endpoint, limit in RATE_LIMITS.items():
            if endpoint == "__global__":
                continue
            if normalized == endpoint.lower():
                return limit
    else:
        if path in RATE_LIMITS:
            return RATE_LIMITS[path]

    return RATE_LIMITS["__global__"]


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """Redis-backed request rate limiter.

    Uses Redis INCR with EXPIRE to enforce sliding-window rate limits
    per client IP and endpoint. Difficulty level controls bypass vectors:

    - **easy**: Rate limiting disabled (all requests pass through).
    - **medium**: Trusts X-Forwarded-For blindly, case-sensitive path matching,
      fail-open on Redis errors, X-Internal header bypass.
    - **hard**: Case-insensitive path matching, but still trusts XFF and fails open.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Check rate limits before forwarding the request.

        Args:
            request: The incoming HTTP request.
            call_next: Callback to invoke the next middleware or route handler.

        Returns:
            429 JSON response if rate limited, otherwise the downstream response.
        """
        # Easy mode: rate limiting completely disabled
        if settings.DIFFICULTY == "easy":
            return await call_next(request)

        # Skip excluded paths
        if request.url.path in EXCLUDED_PATHS:
            return await call_next(request)

        # VULN: Rate Limit Bypass - Unverified internal header
        # Any client can set X-Internal: true to skip rate limiting entirely
        if request.headers.get("x-internal") == "true":
            return await call_next(request)

        client_ip = _get_client_ip(request)
        path = request.url.path
        max_requests, window_seconds = _get_rate_limit(path, settings.DIFFICULTY)

        redis_key = f"ratelimit:{path}:{client_ip}"

        # VULN: Rate Limit Bypass - Fail-open design: if Redis is unavailable,
        # requests are allowed through instead of being denied
        try:
            redis_client = request.app.state.redis
            current_count = await redis_client.incr(redis_key)

            # Set expiry only on first request in the window
            if current_count == 1:
                await redis_client.expire(redis_key, window_seconds)

        except Exception:
            logger.warning("Redis unavailable — rate limiter fail-open for %s", client_ip)
            return await call_next(request)

        if current_count > max_requests:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded"},
                headers={
                    "X-RateLimit-Limit": str(max_requests),
                    "X-RateLimit-Remaining": "0",
                },
            )

        remaining = max(0, max_requests - current_count)
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(max_requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response
