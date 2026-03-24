from datetime import datetime

from pydantic import BaseModel

from backend.database.models import Timeframe


class CandleResponse(BaseModel):
    id: int
    symbol: str
    timeframe: Timeframe
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    model_config = {"from_attributes": True}
