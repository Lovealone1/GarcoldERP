from typing import Any
from dependency_injector.wiring import inject, Provide

from app.app_containers import ApplicationContainer
from app.core.realtime import ConnectionManager

@inject
async def publish_realtime_event(
    channel_id: str,
    resource: str,
    action: str,
    payload: dict[str, Any] | None = None,
    manager: ConnectionManager = Provide[
        ApplicationContainer.api_container.realtime_manager
    ],
) -> None:
    """
    Broadcasts a standardized realtime event to all clients in the given channel.

    Args:
        channel_id: Logical channel identifier.
        resource: Domain resource name (for example "sale", "purchase", "product").
        action: Event action name (for example "created", "updated", "deleted").
        payload: Optional event payload with additional data.

    Returns:
        None
    """
    message = {
        "type": f"{resource}.{action}",
        "resource": resource,
        "action": action,
        "payload": payload or {},
    }
    await manager.broadcast(channel_id, message)
