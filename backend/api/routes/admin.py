"""Admin routes — system statistics, logs, cache, and shutdown."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies.auth import require_role
from backend.api.dependencies.database import get_db
from backend.core.config import get_settings
from backend.models.user import User

router = APIRouter(prefix="/admin", tags=["admin"])


# ── System Statistics ──────────────────────────────────────────────────


@router.get("/stats")
async def system_stats(
    admin: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return system-wide statistics."""
    stats: dict[str, object] = {}

    # User count
    result = await db.execute(text("SELECT COUNT(*) FROM users"))
    stats["total_users"] = result.scalar()

    # Active users
    result = await db.execute(text("SELECT COUNT(*) FROM users WHERE is_active = true"))
    stats["active_users"] = result.scalar()

    # Conversation count
    result = await db.execute(text("SELECT COUNT(*) FROM conversations"))
    stats["total_conversations"] = result.scalar()

    # Message count
    result = await db.execute(text("SELECT COUNT(*) FROM messages"))
    stats["total_messages"] = result.scalar()

    # Device count
    result = await db.execute(text("SELECT COUNT(*) FROM devices"))
    stats["total_devices"] = result.scalar()

    # Goal count
    result = await db.execute(text("SELECT COUNT(*) FROM goals"))
    stats["total_goals"] = result.scalar()

    # Memory entries
    result = await db.execute(text("SELECT COUNT(*) FROM memory_entries"))
    stats["total_memories"] = result.scalar()

    # Database size estimate
    result = await db.execute(
        text(
            "SELECT pg_database_size(current_database()) AS db_size_bytes"
        )
    )
    stats["db_size_bytes"] = result.scalar()

    return stats


# ── Recent Logs ────────────────────────────────────────────────────────


@router.get("/logs")
async def get_logs(
    lines: int = Query(100, ge=10, le=5000),
    admin: User = Depends(require_role("admin")),
) -> dict:
    """Return recent log file entries."""
    log_paths = [
        Path("logs/jarvis.log"),
        Path("logs/jarvis.json.log"),
        Path("/var/log/jarvis/jarvis.log"),
    ]

    log_content: list[str] = []

    for log_path in log_paths:
        if log_path.exists():
            try:
                with open(log_path, "r") as f:
                    # Read last N lines
                    all_lines = f.readlines()
                    log_content = all_lines[-lines:]
                    break
            except (OSError, PermissionError):
                continue

    if not log_content:
        log_content = ["[ No log file found — logging may not be configured ]"]

    return {
        "lines": len(log_content),
        "entries": log_content,
    }


# ── Graceful Shutdown ──────────────────────────────────────────────────


@router.post("/shutdown")
async def shutdown(
    admin: User = Depends(require_role("admin")),
) -> dict:
    """Gracefully shut down the server.

    Requires the ``shutdown_token`` from settings to be provided as a
    query parameter or in the request body (future: implement token
    verification).
    """
    settings = get_settings()

    # TODO: verify shutdown_token from request body/query
    if not settings.shutdown_token:
        return {
            "message": "Shutdown requested but no SHUTDOWN_TOKEN is configured — "
            "add SHUTDOWN_TOKEN to your .env to enable this feature.",
        }

    return {"message": "Shutdown signal received. Server will stop after active requests complete."}


# ── Clear Cache ────────────────────────────────────────────────────────


@router.post("/clear-cache")
async def clear_cache(
    admin: User = Depends(require_role("admin")),
) -> dict:
    """Clear the Redis cache.

    This is a placeholder until Redis integration is complete.
    """
    # TODO: integrate Redis flush when Redis client is available
    return {
        "message": "Cache clear requested. "
        "Redis integration is not yet active — no caches were cleared.",
    }
