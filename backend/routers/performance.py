from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.deps import get_session
from backend.database.models import Signal, SignalStatus
from backend.database.repositories import PerformanceRepository
from backend.schemas import PnLPoint, StrategyPerformanceResponse

router = APIRouter(prefix="/api/performance", tags=["performance"])


@router.get("/strategies", response_model=list[StrategyPerformanceResponse])
async def get_strategy_performance(
    session: AsyncSession = Depends(get_session),
) -> list[StrategyPerformanceResponse]:
    repo = PerformanceRepository(session)
    records = await repo.get_all()
    return [StrategyPerformanceResponse.model_validate(r) for r in records]


@router.get("/pnl", response_model=list[PnLPoint])
async def get_pnl_history(
    session: AsyncSession = Depends(get_session),
) -> list[PnLPoint]:
    query = (
        select(Signal)
        .where(Signal.status.in_([SignalStatus.WON, SignalStatus.LOST]))
        .where(Signal.pips_result.isnot(None))
        .order_by(Signal.resolved_at.asc())
    )
    result = await session.execute(query)
    signals = result.scalars().all()

    cumulative = 0.0
    points: list[PnLPoint] = []
    for s in signals:
        cumulative += s.pips_result  # type: ignore[operator]
        points.append(
            PnLPoint(
                timestamp=s.resolved_at,  # type: ignore[arg-type]
                cumulative_pnl=cumulative,
                strategy_name=s.strategy_name,
            )
        )
    return points
