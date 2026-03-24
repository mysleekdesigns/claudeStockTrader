import logging
from contextlib import asynccontextmanager

from backend.logging_config import setup_logging

setup_logging()

import httpx
import redis.asyncio as aioredis
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from sqlalchemy import text

from backend.config import settings
from backend.middleware import ExceptionHandlerMiddleware
from backend.data.candle_ingestion import CandleIngestionService, register_ingestion_jobs
from backend.data.feed import FailoverFeed, OandaFeed, TwelveDataFeed
from backend.database.connection import async_engine, async_session_factory
from backend.routers import (
    ab_tests_router,
    candles_router,
    decisions_router,
    health_router,
    performance_router,
    risk_router,
    signals_router,
    websocket_router,
)
from backend.scheduler.jobs import register_phase6_jobs

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---

    # Async engine + connection check
    async with async_engine.connect() as conn:
        await conn.execute(text("SELECT 1"))

    # Redis connection pool
    app.state.redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    await app.state.redis.ping()

    # Shared httpx client (connection pooled)
    app.state.http_client = httpx.AsyncClient(timeout=30.0)

    # Data feed provider (Phase 2)
    primary = TwelveDataFeed(
        api_key=settings.twelve_data_api_key,
        http_client=app.state.http_client,
    )
    fallback = OandaFeed(
        account_id=settings.oanda_account_id,
        access_token=settings.oanda_access_token,
        http_client=app.state.http_client,
    )
    app.state.data_feed = FailoverFeed(primary=primary, fallback=fallback)

    # Candle ingestion service
    app.state.ingestion = CandleIngestionService(
        feed=app.state.data_feed,
        session_factory=async_session_factory,
        redis=app.state.redis,
    )

    # APScheduler — ingestion jobs + Phase 6 jobs
    app.state.scheduler = AsyncIOScheduler()
    register_ingestion_jobs(app.state.scheduler, app.state.ingestion)
    register_phase6_jobs(app.state.scheduler)
    app.state.scheduler.start()
    logger.info("APScheduler started with ingestion + Phase 6 jobs")

    # Claude AI client (Phase 4)
    from backend.brain.claude_client import ClaudeClient

    app.state.claude_client = ClaudeClient(redis=app.state.redis)

    yield

    # --- Shutdown ---
    app.state.scheduler.shutdown(wait=False)
    await app.state.http_client.aclose()
    await app.state.redis.aclose()
    await async_engine.dispose()


app = FastAPI(
    title="claudeStockTrader",
    description="AI-assisted gold (XAU/USD) trading system",
    version="0.1.0",
    lifespan=lifespan,
)

# --- Middleware ---
app.add_middleware(ExceptionHandlerMiddleware)

# --- Register routers ---
app.include_router(health_router)
app.include_router(candles_router)
app.include_router(signals_router)
app.include_router(performance_router)
app.include_router(risk_router)
app.include_router(decisions_router)
app.include_router(ab_tests_router)
app.include_router(websocket_router)
