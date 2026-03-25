"""Factory-reset endpoint: drops all data and re-seeds from init.sql."""

import shutil
from pathlib import Path

import asyncpg
from fastapi import APIRouter, Header, HTTPException, Request

from app.config import settings

router = APIRouter()

INIT_SQL_PATH = Path("/app/init.sql")
UPLOADS_DIR = Path("/app/uploads")


@router.post("/reset")
async def reset_application(
    request: Request,
    x_api_key: str = Header(..., alias="X-API-Key"),
):
    """Reset the entire application to its initial seed state.

    Requires a valid API key via the X-API-Key header.

    Steps:
      1. Validate API key
      2. Drop public schema (cascade) and recreate it
      3. Execute init.sql to rebuild tables and seed data
      4. Clear uploaded files
      5. Flush Redis cache
    """
    if not settings.RESET_API_KEY:
        raise HTTPException(status_code=503, detail="Reset API key not configured")

    if x_api_key != settings.RESET_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")

    # Read init.sql
    if not INIT_SQL_PATH.exists():
        raise HTTPException(status_code=500, detail="init.sql not found in container")

    init_sql = INIT_SQL_PATH.read_text(encoding="utf-8")

    # Reset database — use asyncpg directly for multi-statement SQL
    conn = await asyncpg.connect(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        database=settings.DB_NAME,
    )
    try:
        await conn.execute("DROP SCHEMA public CASCADE")
        await conn.execute("CREATE SCHEMA public")
        await conn.execute(f"GRANT ALL ON SCHEMA public TO {settings.DB_USER}")
        await conn.execute(init_sql)
    finally:
        await conn.close()

    # Clear uploads
    if UPLOADS_DIR.exists():
        for child in UPLOADS_DIR.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()

    # Flush Redis
    try:
        redis = request.app.state.redis
        await redis.execute_command("REPLICAOF", "NO", "ONE")
        await redis.flushall()
    except Exception:
        pass  # Redis flush is best-effort

    return {"status": "ok", "message": "Application reset to initial state"}
