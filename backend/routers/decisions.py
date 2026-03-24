from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.deps import get_session
from backend.database.repositories import BacktestRepository, DecisionRepository
from backend.schemas import (
    BacktestRunResponse,
    DecisionLogResponse,
    OptimisedParamsResponse,
)

router = APIRouter(prefix="/api", tags=["decisions"])


@router.get("/decisions", response_model=list[DecisionLogResponse])
async def list_decisions(
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
) -> list[DecisionLogResponse]:
    repo = DecisionRepository(session)
    decisions = await repo.list_recent(limit=limit)
    return [DecisionLogResponse.model_validate(d) for d in decisions]


@router.get("/backtests", response_model=list[BacktestRunResponse])
async def list_backtests(
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
) -> list[BacktestRunResponse]:
    repo = BacktestRepository(session)
    runs = await repo.list_runs(limit=limit)
    return [BacktestRunResponse.model_validate(r) for r in runs]


@router.get("/params", response_model=list[OptimisedParamsResponse])
async def get_active_params(
    session: AsyncSession = Depends(get_session),
) -> list[OptimisedParamsResponse]:
    repo = BacktestRepository(session)
    params = await repo.get_active_params()
    return [OptimisedParamsResponse.model_validate(p) for p in params]
