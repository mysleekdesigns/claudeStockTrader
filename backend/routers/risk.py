from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.deps import get_session
from backend.database.repositories import RiskRepository
from backend.schemas import RiskStateResponse

router = APIRouter(prefix="/api/risk", tags=["risk"])


@router.get("/state", response_model=RiskStateResponse)
async def get_risk_state(
    session: AsyncSession = Depends(get_session),
) -> RiskStateResponse:
    repo = RiskRepository(session)
    state = await repo.get_current()
    if state is None:
        raise HTTPException(status_code=404, detail="No risk state found")
    return RiskStateResponse.model_validate(state)
