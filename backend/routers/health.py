from fastapi import APIRouter, Request
from sqlalchemy import text

from backend.database.connection import async_engine
from backend.schemas import HealthResponse

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request) -> HealthResponse:
    # Database check
    db_status = "ok"
    try:
        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        db_status = "unavailable"

    # Redis check
    redis_status = "ok"
    try:
        redis = request.app.state.redis
        await redis.ping()
    except Exception:
        redis_status = "unavailable"

    # Feed check — data_feed is set by Phase 2 if available
    feed_status = "ok"
    feed = getattr(request.app.state, "data_feed", None)
    if feed is None:
        feed_status = "not_configured"

    # Scheduler check
    scheduler_status = "ok"
    scheduler = getattr(request.app.state, "scheduler", None)
    if scheduler is None:
        scheduler_status = "not_configured"
    elif not scheduler.running:
        scheduler_status = "stopped"

    overall = "ok"
    if db_status != "ok" or redis_status != "ok":
        overall = "degraded"

    return HealthResponse(
        status=overall,
        database=db_status,
        redis=redis_status,
        feed=feed_status,
        scheduler=scheduler_status,
    )
