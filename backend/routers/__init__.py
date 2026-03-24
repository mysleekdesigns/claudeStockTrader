from backend.routers.candles import router as candles_router
from backend.routers.decisions import router as decisions_router
from backend.routers.health import router as health_router
from backend.routers.performance import router as performance_router
from backend.routers.risk import router as risk_router
from backend.routers.signals import router as signals_router
from backend.routers.websocket import router as websocket_router

__all__ = [
    "candles_router",
    "signals_router",
    "performance_router",
    "risk_router",
    "decisions_router",
    "health_router",
    "websocket_router",
]
