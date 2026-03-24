"""Candle ingestion job — staggered fetching across timeframes with Redis pub/sub."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.data.feed import CandleData, FailoverFeed
from backend.database.models import Timeframe
from backend.database.repositories.candles import CandleRepository

logger = logging.getLogger(__name__)

PUBSUB_CHANNEL = "candles:XAU/USD"

# Stagger schedule — maps each timeframe to its check interval in minutes.
# Average call rate: (1/1 + 1/5 + 1/15 + 1/60) ~= 1.28 calls/min (~1,843/day within 800 api calls
# because most checks will short-circuit when no new candle is due).
TIMEFRAME_INTERVALS: dict[Timeframe, int] = {
    Timeframe.M15: 1,   # check every 1 min
    Timeframe.H1: 5,    # check every 5 min
    Timeframe.H4: 15,   # check every 15 min
    Timeframe.D1: 60,   # check every 60 min
}

# Minutes per candle period — used to skip API calls when a new candle is not yet expected.
_CANDLE_PERIOD_MINUTES: dict[Timeframe, int] = {
    Timeframe.M15: 15,
    Timeframe.H1: 60,
    Timeframe.H4: 240,
    Timeframe.D1: 1440,
}


class CandleIngestionService:
    """Fetches candles from the feed, persists via repository, publishes to Redis."""

    def __init__(
        self,
        feed: FailoverFeed,
        session_factory: async_sessionmaker,
        redis: aioredis.Redis,
    ):
        self.feed = feed
        self.session_factory = session_factory
        self.redis = redis
        # Track last ingested timestamp per timeframe to avoid redundant API calls.
        self._last_ts: dict[Timeframe, datetime | None] = {tf: None for tf in Timeframe}

    async def ingest(self, timeframe: Timeframe) -> None:
        """Fetch the latest candle for a timeframe, upsert it, and publish to Redis."""
        now_utc = datetime.now(timezone.utc)

        # Skip if we already have the candle for the current period.
        last = self._last_ts[timeframe]
        if last is not None:
            period = _CANDLE_PERIOD_MINUTES[timeframe]
            elapsed = (now_utc - last).total_seconds() / 60
            if elapsed < period:
                logger.debug("Skipping %s — next candle not due for %.0f min", timeframe.value, period - elapsed)
                return

        try:
            candles = await self.feed.fetch_candles(timeframe, count=2)
        except Exception:
            logger.exception("Failed to fetch %s candles", timeframe.value)
            return

        if not candles:
            logger.warning("No candles returned for %s", timeframe.value)
            return

        await self._persist_and_publish(candles)

        # Record the most recent candle timestamp we ingested.
        newest = max(candles, key=lambda c: c.timestamp)
        self._last_ts[timeframe] = newest.timestamp

    async def backfill(self, timeframe: Timeframe, count: int = 500) -> None:
        """Fetch historical candles for initial population."""
        try:
            candles = await self.feed.fetch_candles(timeframe, count=count)
        except Exception:
            logger.exception("Backfill failed for %s", timeframe.value)
            return

        if candles:
            await self._persist_and_publish(candles, publish=False)
            logger.info("Backfilled %d candles for %s", len(candles), timeframe.value)

    async def _persist_and_publish(
        self, candles: list[CandleData], publish: bool = True
    ) -> None:
        candle_dicts = [c.to_dict() for c in candles]

        async with self.session_factory() as session:
            repo = CandleRepository(session)
            await repo.upsert_many(candle_dicts)

        if publish:
            for candle in candles:
                message = json.dumps(
                    {
                        "symbol": candle.symbol,
                        "timeframe": candle.timeframe.value,
                        "timestamp": candle.timestamp.isoformat(),
                        "open": candle.open,
                        "high": candle.high,
                        "low": candle.low,
                        "close": candle.close,
                        "volume": candle.volume,
                    }
                )
                await self.redis.publish(PUBSUB_CHANNEL, message)
                logger.debug("Published %s %s candle to %s", candle.timeframe.value, candle.timestamp, PUBSUB_CHANNEL)


def register_ingestion_jobs(
    scheduler,
    ingestion_service: CandleIngestionService,
) -> None:
    """Register staggered APScheduler interval jobs for each timeframe."""
    for timeframe, interval_minutes in TIMEFRAME_INTERVALS.items():
        job_id = f"ingest_{timeframe.value}"
        scheduler.add_job(
            ingestion_service.ingest,
            "interval",
            minutes=interval_minutes,
            args=[timeframe],
            id=job_id,
            name=f"Ingest {timeframe.value} candles",
            replace_existing=True,
            max_instances=1,
        )
        logger.info("Registered ingestion job %s (every %d min)", job_id, interval_minutes)
