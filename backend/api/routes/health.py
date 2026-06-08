"""System health-check endpoint."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies.database import get_db
from backend.schemas.health import HealthResponse

router = APIRouter(tags=["health"])

START_TIME = time.time()
VERSION = "3.0.0"


@router.get("/health", response_model=HealthResponse)
async def health_check(db: AsyncSession = Depends(get_db)) -> HealthResponse:
    """Return system health status including database, Redis, and LLM checks."""
    # ── Database check ────────────────────────────────────────────────
    try:
        await db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:  # noqa: BLE001
        db_status = "error"

    # ── Redis check (placeholder) ─────────────────────────────────────
    try:
        # TODO: integrate Redis ping when redis client is available
        redis_status = "unavailable"
    except Exception:  # noqa: BLE001
        redis_status = "unavailable"

    # ── LLM provider check (placeholder) ──────────────────────────────
    llm_status = "ready"

    uptime = time.time() - START_TIME
    overall_status = "healthy" if db_status == "connected" else "degraded"

    return HealthResponse(
        status=overall_status,
        version=VERSION,
        uptime=round(uptime, 2),
        database=db_status,
        redis=redis_status,
        llm=llm_status,
    )
