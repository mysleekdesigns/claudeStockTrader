from datetime import datetime

from pydantic import BaseModel, field_validator

from backend.database.models import SignalDirection, SignalStatus


class SignalCreate(BaseModel):
    strategy_name: str
    direction: SignalDirection
    entry_price: float
    stop_loss: float
    take_profit: float
    confidence_score: float
    reasoning: str | None = None

    @field_validator("confidence_score")
    @classmethod
    def confidence_in_range(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("confidence_score must be between 0.0 and 1.0")
        return v

    @field_validator("entry_price", "stop_loss", "take_profit")
    @classmethod
    def positive_price(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Price must be positive")
        return v


class SignalResponse(BaseModel):
    id: int
    strategy_name: str
    direction: SignalDirection
    entry_price: float
    stop_loss: float
    take_profit: float
    confidence_score: float
    reasoning: str | None
    status: SignalStatus
    pips_result: float | None
    created_at: datetime
    resolved_at: datetime | None

    model_config = {"from_attributes": True}


class SignalResolution(BaseModel):
    status: SignalStatus
    pips_result: float

    @field_validator("status")
    @classmethod
    def must_be_terminal(cls, v: SignalStatus) -> SignalStatus:
        if v not in (SignalStatus.WON, SignalStatus.LOST, SignalStatus.EXPIRED):
            raise ValueError("Resolution status must be won, lost, or expired")
        return v
