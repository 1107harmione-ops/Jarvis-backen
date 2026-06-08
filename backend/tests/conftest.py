"""
Pytest fixtures for JARVIS V3 testing.
"""
import asyncio
import pytest
from typing import AsyncGenerator, Generator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Test database URL (use SQLite for speed, PostgreSQL for integration)
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test_jarvis.db"


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_engine():
    """Create a test database engine."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    # Create tables
    from backend.database import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def test_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session with transaction rollback."""
    from backend.database import async_session_maker
    # Override the global session maker
    session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Create an async HTTP client for testing."""
    # Import the app — this will trigger lifespan events, so we mock dependencies
    import os
    os.environ["ENVIRONMENT"] = "test"
    os.environ["SECRET_KEY"] = "test-secret-key-not-for-production"
    os.environ["JWT_SECRET"] = "test-jwt-secret-not-for-production"

    # Mock database initialization
    from unittest.mock import patch, AsyncMock

    # We create a minimal test app without database initialization
    from fastapi import FastAPI
    from backend.api.routes.health import router as health_router

    app = FastAPI()
    app.include_router(health_router)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def sample_user_data() -> dict:
    """Sample user registration data."""
    return {
        "username": "testuser",
        "email": "test@example.com",
        "password": "TestPass123!",
    }


@pytest.fixture
def sample_chat_message() -> dict:
    """Sample chat message."""
    return {
        "message": "Hello JARVIS!",
        "temperature": 0.3,
        "max_tokens": 1024,
    }


@pytest.fixture
def auth_headers(sample_user_data) -> dict:
    """Generate auth headers with a test JWT token."""
    from backend.core.security import create_access_token
    token = create_access_token(subject="test-user-id", role="user")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers() -> dict:
    """Generate admin auth headers."""
    from backend.core.security import create_access_token
    token = create_access_token(subject="admin-user-id", role="admin")
    return {"Authorization": f"Bearer {token}"}
