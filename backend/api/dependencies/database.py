from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import async_session_maker


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async database session.

    Creates a session from the global ``async_session_maker``, handles
    commit on success and rollback on exception, then closes the session.
    """
    if async_session_maker is None:
        raise RuntimeError("Database not initialized")

    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
