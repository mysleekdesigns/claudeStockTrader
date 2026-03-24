from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.deps import get_session
from backend.database.models import SignalStatus
from backend.database.repositories import SignalRepository
from backend.schemas import SignalResolution, SignalResponse

router = APIRouter(prefix="/api/signals", tags=["signals"])


@router.get("", response_model=list[SignalResponse])
async def list_signals(
    strategy: str | None = Query(None),
    status: SignalStatus | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> list[SignalResponse]:
    repo = SignalRepository(session)
    signals = await repo.list_signals(
        strategy_name=strategy,
        status=status,
        limit=limit,
        offset=offset,
    )
    return [SignalResponse.model_validate(s) for s in signals]


@router.post("/{signal_id}/resolve", response_model=dict)
async def resolve_signal(
    signal_id: int,
    body: SignalResolution,
    session: AsyncSession = Depends(get_session),
) -> dict:
    repo = SignalRepository(session)
    signal = await repo.get_by_id(signal_id)
    if signal is None:
        raise HTTPException(status_code=404, detail="Signal not found")
    if signal.status not in (SignalStatus.PENDING, SignalStatus.ACTIVE):
        raise HTTPException(status_code=400, detail="Signal already resolved")
    await repo.resolve(signal_id, body.status, body.pips_result)
    return {"status": "resolved", "signal_id": signal_id}
