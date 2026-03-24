from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    database: str
    redis: str
    feed: str
    scheduler: str
