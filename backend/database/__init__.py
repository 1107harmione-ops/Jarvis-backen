"""
JARVIS V3 — Database Module
Async SQLAlchemy with PostgreSQL + pgvector support.
"""

from __future__ import annotations

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from backend.core.config import get_settings


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


engine = None
async_session_maker = None


async def init_db(database_url: str | None = None) -> None:
    """
    Initialize the database engine and session factory.
    Call once at application startup.
    """
    global engine, async_session_maker

    settings = get_settings()
    url = database_url or settings.database_url

    engine = create_async_engine(
        url,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        echo=settings.database_echo,
        pool_pre_ping=True,
    )

    async_session_maker = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    # Create tables (in dev; for prod use Alembic migrations)
    if not settings.is_production:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    from backend.core.logging import get_logger
    get_logger(__name__).info(f"Database initialized | pool={settings.database_pool_size}")


async def close_db() -> None:
    """Dispose of the database engine. Call at application shutdown."""
    global engine, async_session_maker
    if engine:
        await engine.dispose()
        engine = None
        async_session_maker = None


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields an async database session.
    Handles commit/rollback automatically.
    """
    if async_session_maker is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")

    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


__all__ = [
    "Base",
    "init_db",
    "close_db",
    "get_session",
    "engine",
    "async_session_maker",
]
