import logging
import time
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from backend.database.connection import async_session_factory

logger = logging.getLogger(__name__)


def _log_job(name: str):
    """Context manager to log job start/end with timing."""
    class _Timer:
        def __init__(self):
            self._start = 0.0
        async def __aenter__(self):
            self._start = time.monotonic()
            logger.info("scheduler_job_start", extra={"job": name})
            return self
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            elapsed = time.monotonic() - self._start
            if exc_type:
                logger.error(
                    "scheduler_job_failed: %s after %.3fs: %s",
                    name, elapsed, exc_val,
                    extra={"job": name, "elapsed_s": elapsed, "outcome": "error"},
                )
            else:
                logger.info(
                    "scheduler_job_done: %s in %.3fs",
                    name, elapsed,
                    extra={"job": name, "elapsed_s": elapsed, "outcome": "success"},
                )
            return False
    return _Timer()


async def ingest_candles() -> None:
    """Ingest latest candle data (every 1 min)."""
    async with _log_job("ingest_candles"):
        async with async_session_factory() as session:
            try:
                logger.debug("ingest_candles: tick (stub)")
            except Exception:
                logger.exception("ingest_candles failed")
                raise


async def run_signals() -> None:
    """Run strategy signal scan (every 15 min)."""
    async with _log_job("run_signals"):
        async with async_session_factory() as session:
            from backend.strategies.runner import run_all_strategies

            count = await run_all_strategies(session)
            logger.info("run_signals: generated %d signals", count)


async def decision_pipeline() -> None:
    """Run AI decision pipeline (every 30 min)."""
    import redis.asyncio as aioredis

    from backend.brain.claude_client import ClaudeClient
    from backend.brain.decision_pipeline import run_decision_pipeline
    from backend.config import settings as cfg

    async with _log_job("decision_pipeline"):
        async with async_session_factory() as session:
            redis_client = aioredis.from_url(cfg.redis_url, decode_responses=True)
            try:
                claude_client = ClaudeClient(redis_client)
                count = await run_decision_pipeline(session, redis_client, claude_client)
                logger.info("decision_pipeline: generated %d signals", count)
            finally:
                await redis_client.aclose()


async def resolve_signals() -> None:
    """Auto-resolve open signals against current price (every 5 min)."""
    import redis.asyncio as aioredis

    from backend.config import settings
    from backend.scheduler.signal_resolver import SignalResolver

    async with _log_job("resolve_signals"):
        async with async_session_factory() as session:
            redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
            try:
                resolver = SignalResolver(session, redis_client)
                count = await resolver.run()
                logger.info("resolve_signals: resolved %d signals", count)
            finally:
                await redis_client.aclose()


async def monte_carlo_engine() -> None:
    """Run Monte Carlo backtest (every 4 hours)."""
    async with _log_job("monte_carlo_engine"):
        async with async_session_factory() as session:
            from backend.optimisation.monte_carlo import run_monte_carlo

            count = await run_monte_carlo(session)
            logger.info("monte_carlo_engine: %d runs stored", count)


async def reoptimise_params() -> None:
    """Reoptimise strategy parameters (every 6 hours)."""
    async with _log_job("reoptimise_params"):
        async with async_session_factory() as session:
            from backend.optimisation.reoptimiser import run_reoptimise

            results = await run_reoptimise(session)
            promoted = sum(1 for v in results.values() if v)
            logger.info("reoptimise_params: %d/%d strategies promoted", promoted, len(results))


async def circuit_breaker_reset() -> None:
    """Check and reset circuit breaker if shutdown period expired (every 1 hour)."""
    async with _log_job("circuit_breaker_reset"):
        async with async_session_factory() as session:
            from backend.brain.risk_manager import RiskManager

            risk_mgr = RiskManager(session)
            await risk_mgr.reset_circuit_breaker()
            logger.info("circuit_breaker_reset: check complete")


def register_phase6_jobs(scheduler: AsyncIOScheduler) -> None:
    """Register all Phase 6 scheduler jobs onto an existing scheduler.

    Note: ingest_candles is registered here as a stub — Phase 2's
    register_ingestion_jobs handles the real ingestion. This stub is
    skipped if the job ID already exists.
    """
    now = datetime.now(timezone.utc)

    jobs_to_register = [
        (run_signals, "interval", {"minutes": 15}, "run_signals", 15),
        (decision_pipeline, "interval", {"minutes": 30}, "decision_pipeline", 25),
        (resolve_signals, "interval", {"minutes": 5}, "resolve_signals", 35),
        (monte_carlo_engine, "interval", {"hours": 4}, "monte_carlo_engine", 45),
        (reoptimise_params, "interval", {"hours": 6}, "reoptimise_params", 55),
        (circuit_breaker_reset, "interval", {"hours": 1}, "circuit_breaker_reset", 65),
    ]

    for func, trigger, kwargs, job_id, offset_secs in jobs_to_register:
        if scheduler.get_job(job_id) is None:
            scheduler.add_job(
                func,
                trigger,
                **kwargs,
                id=job_id,
                next_run_time=now + timedelta(seconds=offset_secs),
            )

    logger.info("Phase 6 scheduler jobs registered")
