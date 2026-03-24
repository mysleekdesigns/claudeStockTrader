import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

router = APIRouter(tags=["websocket"])
logger = logging.getLogger(__name__)

REDIS_CHANNELS = ["candles:XAU/USD", "signals:XAU/USD", "risk:alerts"]

CHANNEL_TYPE_MAP = {
    "candles:XAU/USD": "candle",
    "signals:XAU/USD": "signal",
    "risk:alerts": "risk_update",
}


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict) -> None:
        disconnected: list[WebSocket] = []
        for ws in self.active_connections:
            try:
                await ws.send_json(message)
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            self.disconnect(ws)


manager = ConnectionManager()


@router.websocket("/ws/live")
async def websocket_live(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    redis = websocket.app.state.redis
    pubsub = redis.pubsub()

    try:
        await pubsub.subscribe(*REDIS_CHANNELS)

        async def redis_listener() -> None:
            """Forward Redis pub/sub messages to the WebSocket client."""
            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                channel = message["channel"]
                msg_type = CHANNEL_TYPE_MAP.get(channel, "unknown")
                try:
                    data = json.loads(message["data"])
                except (json.JSONDecodeError, TypeError):
                    data = message["data"]
                await websocket.send_json({"type": msg_type, "data": data})

        async def client_listener() -> None:
            """Handle ping/pong keepalive from the client."""
            while True:
                try:
                    data = await websocket.receive_text()
                    if data == "ping":
                        await websocket.send_text("pong")
                except WebSocketDisconnect:
                    break

        redis_task = asyncio.create_task(redis_listener())
        client_task = asyncio.create_task(client_listener())

        done, pending = await asyncio.wait(
            {redis_task, client_task},
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in pending:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass

    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("WebSocket error")
    finally:
        manager.disconnect(websocket)
        await pubsub.unsubscribe(*REDIS_CHANNELS)
        await pubsub.aclose()
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.close()
