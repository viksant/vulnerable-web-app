"""Redis connection helper for FastAPI dependency injection."""

from redis.asyncio import Redis
from fastapi import Request


async def get_redis(request: Request) -> Redis:
    """Retrieve the shared Redis client from application state.

    Intended for use as a FastAPI Depends() dependency in route handlers.
    The Redis client is initialized in the lifespan context of main.py
    and stored in ``app.state.redis``.

    Args:
        request: The incoming HTTP request (injected by FastAPI).

    Returns:
        The shared async Redis client instance.

    Raises:
        AttributeError: If Redis was not initialized in the app lifespan.
    """
    return request.app.state.redis
