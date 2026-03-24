"""Data feed providers for XAU/USD candle data."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Protocol

import httpx

from backend.database.models import Timeframe

logger = logging.getLogger(__name__)

# Twelve Data timeframe mapping
_TD_INTERVAL_MAP: dict[Timeframe, str] = {
    Timeframe.M15: "15min",
    Timeframe.H1: "1h",
    Timeframe.H4: "4h",
    Timeframe.D1: "1day",
}

# OANDA granularity mapping
_OANDA_GRANULARITY_MAP: dict[Timeframe, str] = {
    Timeframe.M15: "M15",
    Timeframe.H1: "H1",
    Timeframe.H4: "H4",
    Timeframe.D1: "D",
}

SYMBOL = "XAU/USD"
OANDA_INSTRUMENT = "XAU_USD"


class CandleData:
    """Normalised candle returned by any feed provider."""

    __slots__ = ("symbol", "timeframe", "timestamp", "open", "high", "low", "close", "volume")

    def __init__(
        self,
        symbol: str,
        timeframe: Timeframe,
        timestamp: datetime,
        open: float,
        high: float,
        low: float,
        close: float,
        volume: float,
    ):
        self.symbol = symbol
        self.timeframe = timeframe
        self.timestamp = timestamp
        self.open = open
        self.high = high
        self.low = low
        self.close = close
        self.volume = volume

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "timestamp": self.timestamp,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
        }


class DataFeedProvider(Protocol):
    """Protocol for candle data providers."""

    async def fetch_candles(
        self,
        timeframe: Timeframe,
        count: int = 1,
    ) -> list[CandleData]: ...


class TwelveDataFeed:
    """Primary feed — Twelve Data REST API. Free tier: 800 calls/day, 8/min."""

    BASE_URL = "https://api.twelvedata.com"

    def __init__(self, api_key: str, http_client: httpx.AsyncClient):
        self.api_key = api_key
        self.http_client = http_client

    async def fetch_candles(
        self,
        timeframe: Timeframe,
        count: int = 1,
    ) -> list[CandleData]:
        interval = _TD_INTERVAL_MAP[timeframe]
        params = {
            "symbol": SYMBOL,
            "interval": interval,
            "outputsize": count,
            "apikey": self.api_key,
            "format": "JSON",
        }

        resp = await self.http_client.get(
            f"{self.BASE_URL}/time_series",
            params=params,
            timeout=15.0,
        )
        resp.raise_for_status()
        data = resp.json()

        if "values" not in data:
            raise ValueError(f"Twelve Data error: {data.get('message', data)}")

        candles: list[CandleData] = []
        for v in data["values"]:
            candles.append(
                CandleData(
                    symbol=SYMBOL,
                    timeframe=timeframe,
                    timestamp=datetime.fromisoformat(v["datetime"]).replace(tzinfo=timezone.utc),
                    open=float(v["open"]),
                    high=float(v["high"]),
                    low=float(v["low"]),
                    close=float(v["close"]),
                    volume=float(v.get("volume", 0)),
                )
            )
        return candles


class OandaFeed:
    """Fallback feed — OANDA v20 REST API."""

    BASE_URL = "https://api-fxpractice.oanda.com/v3"

    def __init__(self, account_id: str, access_token: str, http_client: httpx.AsyncClient):
        self.account_id = account_id
        self.access_token = access_token
        self.http_client = http_client

    async def fetch_candles(
        self,
        timeframe: Timeframe,
        count: int = 1,
    ) -> list[CandleData]:
        granularity = _OANDA_GRANULARITY_MAP[timeframe]
        headers = {"Authorization": f"Bearer {self.access_token}"}
        params = {
            "granularity": granularity,
            "count": count,
            "price": "M",  # mid prices
        }

        resp = await self.http_client.get(
            f"{self.BASE_URL}/instruments/{OANDA_INSTRUMENT}/candles",
            headers=headers,
            params=params,
            timeout=15.0,
        )
        resp.raise_for_status()
        data = resp.json()

        candles: list[CandleData] = []
        for c in data.get("candles", []):
            if not c.get("complete", False):
                continue
            mid = c["mid"]
            candles.append(
                CandleData(
                    symbol=SYMBOL,
                    timeframe=timeframe,
                    timestamp=datetime.fromisoformat(c["time"].replace("Z", "+00:00")),
                    open=float(mid["o"]),
                    high=float(mid["h"]),
                    low=float(mid["l"]),
                    close=float(mid["c"]),
                    volume=float(c.get("volume", 0)),
                )
            )
        return candles


class FailoverFeed:
    """Wraps primary + fallback feeds with automatic failover and retry."""

    MAX_RETRIES = 2

    def __init__(self, primary: DataFeedProvider, fallback: DataFeedProvider):
        self.primary = primary
        self.fallback = fallback

    async def fetch_candles(
        self,
        timeframe: Timeframe,
        count: int = 1,
    ) -> list[CandleData]:
        for attempt in range(self.MAX_RETRIES):
            try:
                return await self.primary.fetch_candles(timeframe, count)
            except Exception as e:
                logger.warning(
                    "Primary feed failed (attempt %d/%d): %s",
                    attempt + 1,
                    self.MAX_RETRIES,
                    e,
                )

        logger.info("Falling back to secondary feed for %s", timeframe.value)
        return await self.fallback.fetch_candles(timeframe, count)
