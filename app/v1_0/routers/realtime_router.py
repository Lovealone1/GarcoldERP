import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status, WebSocketException

from app.core.logger import logger
from app.core.realtime import manager
from app.core.security.realtime_auth import build_channel_id, get_ws_identity

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
            raw = await websocket.receive_text()

            # Heartbeat. The client cannot tell a healthy idle socket from a
            # half-dead one (suspended tab, dropped NAT entry) without a reply,
            # so it pings and tears the connection down if nothing comes back.
            try:
                message = json.loads(raw)
            except (ValueError, TypeError):
                continue

            if isinstance(message, dict) and message.get("type") == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        manager.disconnect(channel_id, websocket)
    except Exception:
        logger.warning("[RT] socket error channel=%s", channel_id, exc_info=True)
        manager.disconnect(channel_id, websocket)
        try:
            await websocket.close()
        except Exception:
            pass
