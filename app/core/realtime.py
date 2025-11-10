from typing import Dict, Set, Any
from fastapi import WebSocket

class ConnectionManager:
    """
    Manages active WebSocket connections grouped by a logical channel.

    A channel usually represents a tenant, branch, or any routing key that
    defines which clients should receive a given event.
    """

    def __init__(self) -> None:
        self._channels: Dict[str, Set[WebSocket]] = {}

    async def connect(self, channel_id: str, websocket: WebSocket) -> None:
        """
        Accepts and registers a new WebSocket connection in the given channel.

        Args:
            channel_id: Logical identifier for the channel.
            websocket: Client WebSocket connection.

        Returns:
            None
        """
        await websocket.accept()
        if channel_id not in self._channels:
            self._channels[channel_id] = set()
        self._channels[channel_id].add(websocket)

    def disconnect(self, channel_id: str, websocket: WebSocket) -> None:
        """
        Removes a WebSocket connection from the given channel.

        Args:
            channel_id: Logical identifier for the channel.
            websocket: WebSocket connection to remove.

        Returns:
            None
        """
        conns = self._channels.get(channel_id)
        if not conns:
            return
        conns.discard(websocket)
        if not conns:
            self._channels.pop(channel_id, None)

    async def broadcast(self, channel_id: str, message: dict) -> None:
        """
        Sends a JSON message to all active connections in the given channel.

        Args:
            channel_id: Logical identifier for the target channel.
            message: Serializable payload to be sent as JSON.

        Returns:
            None
        """
        conns = list(self._channels.get(channel_id, set()))
        if not conns:
            return

        dead: list[WebSocket] = []

        for ws in conns:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)

        if dead:
            alive = self._channels.get(channel_id, set())
            if not alive:
                return
            for ws in dead:
                alive.discard(ws)
            if not alive:
                self._channels.pop(channel_id, None)