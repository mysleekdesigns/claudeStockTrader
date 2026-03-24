from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.deps import get_session
from backend.database.models import Timeframe
from backend.database.repositories import CandleRepository
from backend.schemas import CandleResponse

router = APIRouter(prefix="/api/candles", tags=["candles"])


@router.get("/{symbol:path}/{timeframe}", response_model=list[CandleResponse])
async def get_candles(
    symbol: str,
    timeframe: Timeframe,
    start: datetime | None = Query(None),
    end: datetime | None = Query(None),
    limit: int = Query(500, ge=1, le=1000),
    session: AsyncSession = Depends(get_session),
) -> list[CandleResponse]:
    repo = CandleRepository(session)
    candles = await repo.get_range(
        symbol=symbol,
        timeframe=timeframe,
        start=start,
        end=end,
        limit=limit,
    )
    return [CandleResponse.model_validate(c) for c in candles]
