"""
JARVIS V3 — Main Application Entry Point
FastAPI server with WebSocket support, middleware, and all route modules.
"""
from __future__ import annotations

import os
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

# ── Prevent backend/__init__.py from creating import loops ──
# We explicitly import modules here rather than relying on __init__.py
# to avoid circular imports during the refactoring transition.

from backend.core.config import get_settings, reload_settings
from backend.core.logging import setup_logging, setup_opentelemetry, log_security_event

# ── Application Metadata ─────────────────────────────────────
APP_VERSION = "3.0.0"
_start_time = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Application lifespan: startup and shutdown events."""
    settings = get_settings()

    # ── Startup ──
    setup_logging(level=settings.log_level, service_name=settings.otel_service_name)

    # Initialize database
    from backend.database import init_db
    await init_db()

    # Initialize Redis (if configured)
    try:
        from backend.core.redis import init_redis
        await init_redis()
    except Exception as e:
        from backend.core.logging import get_logger
        get_logger(__name__).warning(f"Redis not available: {e}")

    # Load tools
    from backend.tools.loader import load_all_tools
    load_all_tools()

    # Register MCP tools
    try:
        from backend.mcp.tools import MCPToolAdapter
        MCPToolAdapter.register_all()
    except Exception as e:
        from backend.core.logging import get_logger
        get_logger(__name__).warning(f"MCP registration skipped: {e}")

    # Start WebSocket heartbeat
    from backend.websocket.manager import get_manager
    manager = get_manager()
    import asyncio
    asyncio.create_task(manager.heartbeat_check())

    # Setup OpenTelemetry (if configured)
    if settings.otel_exporter_otlp_endpoint:
        try:
            setup_opentelemetry(
                service_name=settings.otel_service_name,
                endpoint=settings.otel_exporter_otlp_endpoint,
                app=app,
            )
        except Exception as e:
            from backend.core.logging import get_logger
            get_logger(__name__).warning(f"OpenTelemetry setup failed: {e}")

    from backend.core.logging import get_logger
    get_logger(__name__).info(f"JARVIS V3 started | port={settings.port} | env={settings.environment}")

    yield  # ── Application runs here ──

    # ── Shutdown ──
    from backend.database import close_db
    await close_db()

    try:
        from backend.core.redis import close_redis
        await close_redis()
    except Exception:
        pass

    get_logger(__name__).info("JARVIS V3 shut down")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=APP_VERSION,
        lifespan=lifespan,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
    )

    # ── Middleware ────────────────────────────────────────────
    from backend.api.middleware.cors import setup_cors
    setup_cors(app)

    from backend.api.middleware.security import SecurityMiddleware
    app.add_middleware(SecurityMiddleware)

    from backend.api.middleware.logging import LoggingMiddleware
    app.add_middleware(LoggingMiddleware)

    # ── Exception Handlers ───────────────────────────────────
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        from backend.core.logging import get_logger
        get_logger(__name__).error(f"Unhandled exception: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "path": request.url.path},
        )

    # ── Routes ───────────────────────────────────────────────
    from backend.api.routes.health import router as health_router
    from backend.api.routes.auth import router as auth_router
    from backend.api.routes.chat import router as chat_router
    from backend.api.routes.users import router as users_router
    from backend.api.routes.conversations import router as conversations_router
    from backend.api.routes.voice import router as voice_router
    from backend.api.routes.tools import router as tools_router
    from backend.api.routes.admin import router as admin_router
    from backend.mcp.routes import router as mcp_router

    app.include_router(health_router, tags=["health"])
    app.include_router(auth_router, prefix="/api/v1", tags=["auth"])
    app.include_router(chat_router, prefix="/api/v1", tags=["chat"])
    app.include_router(users_router, prefix="/api/v1", tags=["users"])
    app.include_router(conversations_router, prefix="/api/v1", tags=["conversations"])
    app.include_router(voice_router, prefix="/api/v1", tags=["voice"])
    app.include_router(tools_router, prefix="/api/v1", tags=["tools"])
    app.include_router(admin_router, prefix="/api/v1", tags=["admin"])
    app.include_router(mcp_router, tags=["mcp"])

    # ── WebSocket ─────────────────────────────────────────────
    @app.websocket("/ws")
    async def websocket_endpoint(websocket, token: str | None = None):
        from backend.websocket.handler import handle_websocket
        await handle_websocket(websocket, token)

    # ── Static Files ──────────────────────────────────────────
    static_dir = Path(__file__).parent / "static"
    static_dir.mkdir(exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # ── Generated Audio ───────────────────────────────────────
    audio_dir = Path(__file__).parent / "generated_audio"
    audio_dir.mkdir(exist_ok=True)
    app.mount("/audio", StaticFiles(directory=str(audio_dir)), name="audio")

    # ── Root endpoint ─────────────────────────────────────────
    @app.get("/")
    async def root():
        return {
            "service": settings.app_name,
            "version": APP_VERSION,
            "status": "running",
            "uptime": round(time.time() - _start_time, 2),
            "docs": "/docs",
        }

    return app


# ── Create the application instance ──────────────────────────
app = create_app()


# ── Direct execution ─────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run(
        "backend.main:app",
        host=settings.host,
        port=settings.port,
        workers=settings.workers,
        log_level=settings.log_level.lower(),
        reload=settings.debug,
    )
