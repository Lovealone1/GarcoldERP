from datetime import datetime, timezone
from typing import Any, Dict, Sequence, Set
from uuid import uuid4

from fastapi import WebSocket

from app.core.logger import logger

#: Envelope version. Bump when the shape changes incompatibly so clients can
#: tell an old payload from a new one instead of guessing.
EVENT_VERSION = 1


#: Query roots each resource actually invalidates on the client.
#:
#: The API is the only side that knows what a mutation really touched: creating
#: a sale writes a transaction, moves a bank balance, decrements stock, records
#: a profit and can move a customer balance, yet it publishes a single
#: `sale.created`. Shipping that fan-out with the event means the frontend does
#: not have to keep a duplicate table in sync, and the server can widen it
#: without a frontend release.
#:
#: Names match the frontend query roots (src/lib/query/queryKeys.ts).
RESOURCE_AFFECTS: Dict[str, tuple[str, ...]] = {
    "sale": (
        "sales", "transactions", "transactions-head", "products", "all-products",
        "profits", "banks", "customers", "dashboard",
    ),
    "sale_payment": (
        "sales", "sale-payments", "transactions", "transactions-head",
        "banks", "customers", "dashboard",
    ),
    "purchase": (
        "purchases", "transactions", "transactions-head", "products",
        "all-products", "banks", "suppliers", "dashboard",
    ),
    "purchase_payment": (
        "purchases", "purchase-payments", "transactions", "transactions-head",
        "banks", "suppliers", "dashboard",
    ),
    "expense": ("expenses", "transactions", "transactions-head", "banks", "dashboard"),
    "transaction": ("transactions", "transactions-head", "banks", "dashboard"),
    "customer": ("customers", "customer"),
    "customer_payment": (
        "customers", "customer", "transactions", "transactions-head",
        "banks", "dashboard",
    ),
    "supplier": ("suppliers",),
    "product": ("products", "all-products"),
    "bank": ("banks", "dashboard"),
    "investment": ("banks", "transactions", "transactions-head", "dashboard"),
    "loan": ("banks", "transactions", "transactions-head", "dashboard"),
}


class ConnectionManager:
    """
    Manages active WebSocket connections grouped by logical channel IDs.

    Connections live in this process's memory. That is correct only while the
    API runs as a single worker: a mutation handled by a different worker would
    broadcast to a set that does not contain the client's socket, and the event
    would be lost. `app.main` asserts the single-worker assumption at startup.
    """

    def __init__(self) -> None:
        self._channels: Dict[str, Set[WebSocket]] = {}

    async def connect(self, channel_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._channels.setdefault(channel_id, set()).add(websocket)
        logger.info(
            "[RT] connected channel=%s total=%s",
            channel_id,
            len(self._channels[channel_id]),
        )

    def disconnect(self, channel_id: str, websocket: WebSocket) -> None:
        conns = self._channels.get(channel_id)
        if not conns:
            return
        conns.discard(websocket)
        if not conns:
            self._channels.pop(channel_id, None)
        logger.info("[RT] disconnected channel=%s remaining=%s", channel_id, len(conns))

    def connection_count(self, channel_id: str) -> int:
        return len(self._channels.get(channel_id, ()))

    async def broadcast(self, channel_id: str, message: dict) -> int:
        """Send to every socket on the channel. Returns how many received it."""
        conns = list(self._channels.get(channel_id, set()))
        if not conns:
            return 0

        delivered = 0
        dead: list[WebSocket] = []

        for ws in conns:
            try:
                await ws.send_json(message)
                delivered += 1
            except Exception:
                # A socket that raises here is gone; drop it rather than letting
                # it accumulate and slow every later broadcast.
                dead.append(ws)

        if dead:
            alive = self._channels.get(channel_id)
            if alive is not None:
                for ws in dead:
                    alive.discard(ws)
                if not alive:
                    self._channels.pop(channel_id, None)
            logger.warning("[RT] dropped %s dead connection(s) channel=%s", len(dead), channel_id)

        return delivered


manager = ConnectionManager()


def build_event(
    resource: str,
    action: str,
    payload: dict[str, Any] | None = None,
    affects: Sequence[str] | None = None,
) -> dict[str, Any]:
    """
    Build a realtime envelope.

    `event_id` and `occurred_at` let a client detect duplicates and reason about
    ordering; `affects` carries the fan-out so the client does not have to infer
    which of its caches a movement invalidated.
    """
    resolved_affects = tuple(affects) if affects is not None else RESOURCE_AFFECTS.get(resource, ())

    return {
        "v": EVENT_VERSION,
        "event_id": str(uuid4()),
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "type": f"{resource}.{action}",
        "resource": resource,
        "action": action,
        "payload": payload or {},
        "affects": list(resolved_affects),
    }


async def publish_realtime_event(
    channel_id: str,
    resource: str,
    action: str,
    payload: dict[str, Any] | None = None,
    affects: Sequence[str] | None = None,
) -> None:
    """
    Broadcast a standardized realtime event to all clients in the given channel.

    Callers must invoke this *after* the database transaction commits. Publishing
    inside the transaction would let a receiving client refetch and read
    pre-commit state.
    """
    message = build_event(resource, action, payload, affects)
    delivered = await manager.broadcast(channel_id, message)

    logger.info(
        "[RT] published type=%s event_id=%s channel=%s delivered=%s",
        message["type"],
        message["event_id"],
        channel_id,
        delivered,
    )
