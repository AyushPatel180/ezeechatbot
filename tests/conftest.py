"""Test configuration and fixtures."""
import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def client():
    """Async HTTP client for testing."""
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
async def mock_qdrant(monkeypatch):
    """Mock Qdrant for isolated tests."""
    # This would mock the Qdrant client
    # For now, just a placeholder
    pass
