from fastapi import WebSocket, status, WebSocketException
from sqlalchemy import select

from app.core.logger import logger
from app.core.security.deps import AuthContext
from app.core.security.jwt import verify_token
from app.storage.database import async_session
from app.v1_0.models import User

#: The only realtime channel.
#:
#: This deployment serves a single company: there is no tenant or company
#: column on users, sales, banks or any other table, so there is nothing to
#: partition on and every authenticated user is entitled to the same stream.
#: A per-tenant channel would need a tenant dimension in the schema first.
GLOBAL_CHANNEL = "global"


class WsIdentity:
    """Who is on the other end of an authenticated socket."""

    def __init__(self, sub: str, user_id: str | None):
        self.sub = sub
        self.user_id = user_id


async def get_ws_identity(websocket: WebSocket) -> WsIdentity:
    token = websocket.query_params.get("token")
    if not token:
        logger.warning("[WS_AUTH] missing token")
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Missing token",
        )

    try:
        claims = await verify_token(token)
    except Exception:
        logger.warning("[WS_AUTH] invalid token")
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

    return WsIdentity(sub=sub, user_id=str(user.external_sub or user.id))


def build_channel_id(identity: WsIdentity) -> str:
    return GLOBAL_CHANNEL


def build_channel_id_from_auth(ctx: AuthContext) -> str:
    return GLOBAL_CHANNEL
