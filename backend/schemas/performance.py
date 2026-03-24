from datetime import datetime

from pydantic import BaseModel


class StrategyPerformanceResponse(BaseModel):
    id: int
    strategy_name: str
    window_days: int
    win_rate: float
    avg_rr: float
    total_signals: int
    sharpe_ratio: float
    max_drawdown: float
    updated_at: datetime

    model_config = {"from_attributes": True}


class PnLPoint(BaseModel):
    timestamp: datetime
    cumulative_pnl: float
    strategy_name: str | None = None
