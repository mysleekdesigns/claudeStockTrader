from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.brain.ab_testing import ABTestManager
from backend.database.deps import get_session
from backend.schemas.ab_test import ABTestResultsResponse, ABVariantSummary

router = APIRouter(prefix="/api", tags=["ab-tests"])


@router.get("/ab-tests", response_model=ABTestResultsResponse)
async def get_ab_test_results(
    session: AsyncSession = Depends(get_session),
) -> ABTestResultsResponse:
    manager = ABTestManager(session)
    results = await manager.get_results()

    variants = [
        ABVariantSummary(
            variant_name=v["variant_name"],
            total_cycles=v["total_cycles"],
            total_signals=v["total_signals"],
            total_won=v["total_won"],
            total_lost=v["total_lost"],
            win_rate=v["win_rate"],
            is_significant=results["significant"],
            p_value=results["p_value"],
        )
        for v in results["variants"]
    ]

    return ABTestResultsResponse(
        variants=variants,
        significant=results["significant"],
        p_value=results["p_value"],
        recommendation=results["recommendation"],
    )
