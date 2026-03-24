from datetime import datetime

from pydantic import BaseModel


class ABTestRunResponse(BaseModel):
    id: int
    variant_name: str
    decision_cycle_id: int
    signals_created: int
    signals_won: int
    signals_lost: int
    win_rate: float
    created_at: datetime

    model_config = {"from_attributes": True}


class ABVariantSummary(BaseModel):
    variant_name: str
    total_cycles: int
    total_signals: int
    total_won: int
    total_lost: int
    win_rate: float
    is_significant: bool
    p_value: float | None


class ABTestResultsResponse(BaseModel):
    variants: list[ABVariantSummary]
    significant: bool
    p_value: float | None
    recommendation: str
