# app/core/realtime.py

from typing import Dict, Set, Any
from fastapi import WebSocket
from app.core.logger import logger


class ConnectionManager:
    """
    Manages active WebSocket connections grouped by logical channel IDs.
    """

    def __init__(self) -> None:
        self._channels: Dict[str, Set[WebSocket]] = {}

    async def connect(self, channel_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        if channel_id not in self._channels:
            self._channels[channel_id] = set()
        self._channels[channel_id].add(websocket)
        logger.info("[RT] connected channel=%s total=%s", channel_id, len(self._channels[channel_id]))

    def disconnect(self, channel_id: str, websocket: WebSocket) -> None:
        conns = self._channels.get(channel_id)
        if not conns:
            return
        conns.discard(websocket)
        if not conns:
            self._channels.pop(channel_id, None)

    async def broadcast(self, channel_id: str, message: dict) -> None:
        conns = list(self._channels.get(channel_id, set()))
        if not conns:
            return

        dead: list[WebSocket] = []

        for ws in conns:
            try:
                await ws.send_json(message)
            except Exception as e:
                dead.append(ws)

        if dead:
            alive = self._channels.get(channel_id, set())
            if alive:
                for ws in dead:
                    alive.discard(ws)
                if not alive:
                    self._channels.pop(channel_id, None)


manager = ConnectionManager()


async def publish_realtime_event(
    channel_id: str,
    resource: str,
    action: str,
    payload: dict[str, Any] | None = None,
) -> None:
    """
    Broadcasts a standardized realtime event to all clients in the given channel.
    """
    message = {
        "type": f"{resource}.{action}",
        "resource": resource,
        "action": action,
        "payload": payload or {},
    }
    await manager.broadcast(channel_id, message)
