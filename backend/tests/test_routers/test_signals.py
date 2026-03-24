"""Integration tests for the signals router."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from backend.database.models import Signal, SignalDirection, SignalStatus

pytestmark = pytest.mark.asyncio


def _make_signal_obj(id: int) -> Signal:
    s = Signal(
        id=id,
        strategy_name="liquidity_sweep",
        direction=SignalDirection.LONG,
        entry_price=2350.0,
        stop_loss=2330.0,
        take_profit=2390.0,
        confidence_score=0.75,
        reasoning="Test signal",
        status=SignalStatus.PENDING,
        pips_result=None,
        created_at=datetime(2025, 6, 1, 12, 0, tzinfo=timezone.utc),
        resolved_at=None,
    )
    return s


@pytest_asyncio.fixture
async def client():
    mock_signals = [_make_signal_obj(i) for i in range(1, 4)]

    with (
        patch("backend.routers.signals.SignalRepository") as MockRepo,
    ):
        mock_repo = AsyncMock()
        mock_repo.list_signals = AsyncMock(return_value=mock_signals)
        mock_repo.get_by_id = AsyncMock(return_value=mock_signals[0])
        mock_repo.resolve = AsyncMock()
        MockRepo.return_value = mock_repo

        from backend.main import app
        from backend.database.deps import get_session

        mock_session = AsyncMock()
        app.dependency_overrides[get_session] = lambda: mock_session

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

        app.dependency_overrides.clear()


class TestSignalsEndpoint:
    async def test_list_signals_200(self, client):
        resp = await client.get("/api/signals")
        assert resp.status_code == 200

    async def test_list_signals_returns_array(self, client):
        resp = await client.get("/api/signals")
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 3

    async def test_signal_has_required_fields(self, client):
        resp = await client.get("/api/signals")
        data = resp.json()
        for signal in data:
            assert "id" in signal
            assert "strategy_name" in signal
            assert "direction" in signal
            assert "entry_price" in signal
            assert "stop_loss" in signal
            assert "take_profit" in signal
            assert "confidence_score" in signal
            assert "status" in signal

    async def test_filter_by_strategy(self, client):
        resp = await client.get("/api/signals?strategy=liquidity_sweep")
        assert resp.status_code == 200

    async def test_resolve_signal(self, client):
        resp = await client.post(
            "/api/signals/1/resolve",
            json={"status": "won", "pips_result": 40.0},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "resolved"
        assert data["signal_id"] == 1

    async def test_resolve_already_resolved_returns_400(self, client):
        """If signal is already resolved, should return 400."""
        with patch("backend.routers.signals.SignalRepository") as MockRepo:
            resolved_signal = _make_signal_obj(1)
            resolved_signal.status = SignalStatus.WON
            mock_repo = AsyncMock()
            mock_repo.get_by_id = AsyncMock(return_value=resolved_signal)
            MockRepo.return_value = mock_repo

            from backend.main import app
            from backend.database.deps import get_session

            mock_session = AsyncMock()
            app.dependency_overrides[get_session] = lambda: mock_session

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                resp = await ac.post(
                    "/api/signals/1/resolve",
                    json={"status": "lost", "pips_result": -20.0},
                )
                assert resp.status_code == 400

            app.dependency_overrides.clear()
