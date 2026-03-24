"""Integration tests for the health endpoint."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def client():
    """Create a test client with mocked dependencies."""
    # Patch heavy dependencies before importing the app
    with (
        patch("backend.database.connection.create_async_engine") as mock_engine,
        patch("backend.main.async_engine") as mock_main_engine,
        patch("backend.main.async_session_factory"),
        patch("backend.main.CandleIngestionService"),
        patch("backend.main.register_ingestion_jobs"),
        patch("backend.main.register_phase6_jobs"),
        patch("backend.main.TwelveDataFeed"),
        patch("backend.main.OandaFeed"),
        patch("backend.main.FailoverFeed"),
        patch("backend.main.ClaudeClient"),
        patch("backend.main.aioredis") as mock_aioredis,
        patch("backend.main.settings") as mock_settings,
    ):
        mock_settings.redis_url = "redis://localhost:6379/0"
        mock_settings.twelve_data_api_key = "test"
        mock_settings.oanda_account_id = "test"
        mock_settings.oanda_access_token = "test"

        # Mock Redis
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(return_value=True)
        mock_redis.aclose = AsyncMock()
        mock_aioredis.from_url.return_value = mock_redis

        # Mock DB engine
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)
        mock_main_engine.connect.return_value = mock_conn
        mock_main_engine.dispose = AsyncMock()

        # Mock scheduler
        mock_scheduler = MagicMock()
        mock_scheduler.start = MagicMock()
        mock_scheduler.shutdown = MagicMock()
        mock_scheduler.running = True

        from backend.main import app

        # Set state that health endpoint checks
        app.state.redis = mock_redis
        app.state.scheduler = mock_scheduler
        app.state.data_feed = MagicMock()
        app.state.http_client = AsyncMock()
        app.state.http_client.aclose = AsyncMock()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


class TestHealthEndpoint:
    async def test_health_returns_200(self, client):
        resp = await client.get("/api/health")
        assert resp.status_code == 200

    async def test_health_response_schema(self, client):
        resp = await client.get("/api/health")
        data = resp.json()
        assert "status" in data
        assert "database" in data
        assert "redis" in data
        assert "feed" in data
        assert "scheduler" in data
