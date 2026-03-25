"""FastAPI application entrypoint with intentional misconfigurations."""

import os
import sys
import traceback
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

import fastapi
import redis.asyncio as aioredis
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.config import settings
from app.database import engine
from app.middleware.rate_limiter import RateLimiterMiddleware
from app.middleware.waf import WAFMiddleware
from app.routes.admin import router as admin_router
from app.routes.auth import router as auth_router
from app.routes.cart import router as cart_router
from app.routes.export_import import export_router, import_router
from app.routes.graphql import graphql_app
from app.routes.orders import invoices_router
from app.routes.orders import router as orders_router
from app.routes.products import router as products_router
from app.routes.profile import csrf_token_endpoint
from app.routes.profile import router as profile_router
from app.routes.reviews import router as reviews_router
from app.routes.seller import router as seller_router
from app.routes.tickets import router as tickets_router
from app.routes.reset import router as reset_router
from app.routes.uploads import router as uploads_router

UPLOADS_DIR = Path("/app/uploads")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Verify database and Redis connectivity on startup."""
    # Verify DB connection
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))

    # Persist Redis client in app state for middleware and route access
    app.state.redis = aioredis.from_url("redis://redis:6379")
    await app.state.redis.ping()

    yield

    await app.state.redis.aclose()
    await engine.dispose()


# VULN: Info Disclosure - Swagger UI publicly accessible without authentication
app = FastAPI(
    title="VulnShop API",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)

# VULN: CORS Misconfiguration - allow_origins=["*"] combined with allow_credentials=True
# allows any origin to make authenticated cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security middleware — order matters: add_middleware uses LIFO execution,
# so RateLimiter (added first) runs INNER and WAF (added second) runs OUTER.
# Execution flow: Request -> WAF -> RateLimiter -> Route -> RateLimiter -> WAF
app.add_middleware(RateLimiterMiddleware)
app.add_middleware(WAFMiddleware)

# VULN: XSS via SVG - Static files served without Content-Disposition header,
# allowing inline rendering of uploaded SVGs containing JavaScript
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(UPLOADS_DIR)), name="static")

# --- API Routers ---
app.include_router(auth_router, prefix="/api/auth", tags=["Authentication"])
app.include_router(products_router, prefix="/api/products", tags=["Products"])
app.include_router(reviews_router, prefix="/api/products", tags=["Reviews"])
app.include_router(uploads_router, prefix="/api/uploads", tags=["Uploads"])
app.include_router(seller_router, prefix="/api/seller", tags=["Seller Panel"])
app.include_router(cart_router, prefix="/api/cart", tags=["Cart"])
app.include_router(orders_router, prefix="/api/orders", tags=["Orders"])
app.include_router(invoices_router, prefix="/api/invoices", tags=["Invoices"])
app.include_router(tickets_router, prefix="/api/tickets", tags=["Tickets"])
app.include_router(export_router, prefix="/api/export", tags=["Export"])
app.include_router(import_router, prefix="/api/import", tags=["Import"])
app.include_router(admin_router, prefix="/api/admin", tags=["Admin"])
app.include_router(reset_router, prefix="/api", tags=["Reset"])
app.include_router(profile_router, prefix="/api/profile", tags=["Profile"])

# VULN: Session-Unbound CSRF Token - Public endpoint generates tokens not
# bound to any user session. Any visitor can obtain a token reusable for
# any authenticated user's CSRF-protected request.
# Ref: https://hackerone.com/reports/1629828
app.get("/api/csrf-token", tags=["CSRF"], response_model=None)(csrf_token_endpoint)

# GraphQL — mounted separately, does NOT appear in Swagger/OpenAPI docs
app.include_router(graphql_app, prefix="/api/graphql")


@app.get("/health")
async def health_check() -> dict:
    """Docker health check endpoint with version disclosure in debug mode.

    Returns base health status. When DEBUG=true, also exposes exact
    framework, Python runtime, and database versions.

    Returns:
        Health status dict, with version details if DEBUG is enabled.
    """
    response: dict = {
        "status": "ok",
        "version": "1.0.0",
        "debug": settings.DEBUG,
    }

    # VULN: Info Disclosure - Exact version numbers exposed when DEBUG=true.
    # Allows attackers to identify specific CVEs for the running stack.
    # Ref: https://hackerone.com/reports/1064805
    if settings.DEBUG:
        response["framework"] = f"FastAPI {fastapi.__version__}"
        response["python"] = sys.version
        response["database"] = "PostgreSQL 16"

    return response


# VULN: Env Exposure - Full environment variables exposed without authentication.
# Returns all environment variables including secrets, API keys, and internal paths.
# Excluded from OpenAPI schema to avoid casual discovery, but still accessible.
# Ref: https://hackerone.com/reports/1050709
@app.get("/api/debug/env", include_in_schema=False)
async def debug_env() -> dict:  # TODO: remove before production
    """Return all environment variables as a JSON dict.

    **VULN (CWE-200):** No authentication required. Exposes all
    process environment variables including database passwords,
    JWT secrets, and any cloud provider credentials.

    Returns:
        Dict of all environment variable key-value pairs.
    """
    return dict(os.environ)


# VULN: Info Disclosure - Stack traces exposed when DEBUG=true
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Return detailed stack traces in debug mode.

    Args:
        request: The incoming HTTP request.
        exc: The unhandled exception.

    Returns:
        JSON error response, with full traceback if DEBUG is enabled.
    """
    if settings.DEBUG:
        return JSONResponse(
            status_code=500,
            content={
                "detail": str(exc),
                "traceback": traceback.format_exc(),
                "path": str(request.url),
                "method": request.method,
            },
        )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )
