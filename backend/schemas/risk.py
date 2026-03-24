from datetime import datetime

from pydantic import BaseModel


class RiskStateResponse(BaseModel):
    id: int
    date: datetime
    daily_loss_pct: float
    consecutive_stops: int
    is_shutdown: bool
    shutdown_until: datetime | None

    model_config = {"from_attributes": True}
