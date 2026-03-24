from datetime import datetime
from typing import Any

from pydantic import BaseModel

from backend.database.models import BacktestResult, BacktestRunType


class DecisionLogResponse(BaseModel):
    id: int
    ranked_strategies: dict[str, Any] | list[Any]
    risk_status: str
    position_size_multiplier: float
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class BacktestRunResponse(BaseModel):
    id: int
    run_type: BacktestRunType
    window_days: int
    train_start: datetime | None
    test_start: datetime | None
    test_end: datetime | None
    result: BacktestResult
    params_used: dict[str, Any] | None
    metrics: dict[str, Any] | None
    created_at: datetime

    model_config = {"from_attributes": True}


class OptimisedParamsResponse(BaseModel):
    id: int
    strategy_name: str
    params: dict[str, Any]
    is_active: bool
    validated_at: datetime | None

    model_config = {"from_attributes": True}
