from fastapi import WebSocket, status, WebSocketException
from sqlalchemy import select

from app.storage.database import async_session
from app.core.logger import logger
from app.core.security.jwt import verify_token
from app.v1_0.models import User
from app.core.security.deps import AuthContext

class WsIdentity:
    def __init__(self, sub: str, tenant_id: str | None, user_id: str | None):
        self.sub = sub
        self.tenant_id = tenant_id
        self.user_id = user_id


async def get_ws_identity(websocket: WebSocket) -> WsIdentity:
    token = websocket.query_params.get("token")
    if not token:
        logger.warning("[WS_AUTH] missing token url=%s", websocket.url)
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Missing token",
        )

    try:
        claims = await verify_token(token)
    except Exception as e:
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Invalid token",
        )

    sub = claims.get("sub")
    if not sub:
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Missing sub",
        )

    async with async_session() as db:
        user = await db.scalar(select(User).where(User.external_sub == sub))

    if not user:
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="User not provisioned",
        )

    tenant_id = getattr(user, "tenant_id", None)
    user_pk = getattr(user, "external_sub", None) or getattr(user, "id", None)

    ident = WsIdentity(
        sub=sub,
        tenant_id=str(tenant_id) if tenant_id else None,
        user_id=str(user_pk) if user_pk else None,
    )
    return ident




def build_channel_id(identity: WsIdentity) -> str:
    return "global"


def build_channel_id_from_auth(ctx: AuthContext) -> str:
    return "global"
