"""Tests for health endpoint."""
import pytest
from unittest.mock import AsyncMock
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

from backend.api.routes.health import router as health_router
from backend.api.dependencies.database import get_db

# Create a minimal test app with DB dependency overridden
test_app = FastAPI()
test_app.include_router(health_router)


@pytest.fixture(autouse=True)
def override_db():
    """Override DB dependency for health tests."""
    async def mock_get_db():
        async with AsyncMock() as session:
            yield session

    test_app.dependency_overrides[get_db] = mock_get_db
    yield
    test_app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_health_endpoint():
    """Test that health endpoint returns 200."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data


@pytest.mark.anyio
async def test_health_response_structure():
    """Test health response has all required fields."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
        data = response.json()
        assert "version" in data
        assert "uptime" in data
        assert "database" in data


@pytest.mark.anyio
async def test_health_status_ok():
    """Test health status is either healthy or degraded."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
        data = response.json()
        assert data["status"] in ("healthy", "degraded")
