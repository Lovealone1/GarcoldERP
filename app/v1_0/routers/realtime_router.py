from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from dependency_injector.wiring import inject, Provide

from app.app_containers import ApplicationContainer
from app.core.realtime import ConnectionManager
from app.core.security.realtime_auth import get_ws_identity, build_channel_id, WsIdentity

router = APIRouter(
    prefix="/ws",
    tags=["Realtime"],
)


@router.websocket("/realtime")
@inject
async def realtime_websocket(
    websocket: WebSocket,
    identity: WsIdentity = Depends(get_ws_identity),
    manager: ConnectionManager = Depends(
        Provide[ApplicationContainer.api_container.realtime_manager]
    ),
) -> None:
    channel_id = build_channel_id(identity)

    await manager.connect(channel_id, websocket)

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(channel_id, websocket)
    except Exception:
        manager.disconnect(channel_id, websocket)
