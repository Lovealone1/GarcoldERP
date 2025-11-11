from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status, WebSocketException
from app.core.realtime import manager
from app.core.security.realtime_auth import get_ws_identity, build_channel_id
from app.core.logger import logger

router = APIRouter(prefix="/v1/ws", tags=["Realtime"])

@router.websocket("/realtime")
async def websocket_realtime(websocket: WebSocket):
    try:
        identity = await get_ws_identity(websocket)
    except WebSocketException as e:
        await websocket.close(code=e.code)
        return

    channel_id = build_channel_id(identity)
    if not channel_id:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await manager.connect(channel_id, websocket)

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(channel_id, websocket)
    except Exception as e:
        manager.disconnect(channel_id, websocket)
        await websocket.close()
