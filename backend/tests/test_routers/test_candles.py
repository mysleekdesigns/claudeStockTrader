"""Integration tests for the candles router."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from backend.database.models import Candle, Timeframe

pytestmark = pytest.mark.asyncio


def _make_candle_obj(id: int, symbol: str, tf: Timeframe) -> Candle:
    c = Candle(
        id=id,
        symbol=symbol,
        timeframe=tf,
        timestamp=datetime(2025, 6, 1, i := id, 0, tzinfo=timezone.utc),
        open=2350.0 + id,
        high=2355.0 + id,
        low=2345.0 + id,
        close=2352.0 + id,
        volume=5000.0,
    )
    return c


@pytest_asyncio.fixture
async def client():
    mock_candles = [_make_candle_obj(i, "XAU/USD", Timeframe.H1) for i in range(1, 4)]

    with (
        patch("backend.routers.candles.get_session") as mock_get_session,
        patch("backend.routers.candles.CandleRepository") as MockRepo,
    ):
        mock_session = AsyncMock()
        mock_get_session.return_value = mock_session

        mock_repo_instance = AsyncMock()
        mock_repo_instance.get_range = AsyncMock(return_value=mock_candles)
        MockRepo.return_value = mock_repo_instance

        # Need to override the dependency
        from backend.main import app
        from backend.database.deps import get_session

        app.dependency_overrides[get_session] = lambda: mock_session

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

        app.dependency_overrides.clear()


class TestCandlesEndpoint:
    async def test_get_candles_200(self, client):
        resp = await client.get("/api/candles/XAU%2FUSD/1h")
        assert resp.status_code == 200

    async def test_get_candles_returns_list(self, client):
        resp = await client.get("/api/candles/XAU%2FUSD/1h")
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 3

    async def test_candle_response_has_required_fields(self, client):
        resp = await client.get("/api/candles/XAU%2FUSD/1h")
        data = resp.json()
        for candle in data:
            assert "id" in candle
            assert "symbol" in candle
            assert "open" in candle
            assert "high" in candle
            assert "low" in candle
            assert "close" in candle
            assert "volume" in candle
            assert "timestamp" in candle

    async def test_invalid_timeframe_returns_422(self, client):
        resp = await client.get("/api/candles/XAU%2FUSD/invalid_tf")
        assert resp.status_code == 422
