from fastapi import WebSocket, HTTPException, status, Depends
from dependency_injector.wiring import inject
from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.database.db_connector import get_db
from .jwt import verify_token
from .deps import auth_deps

class WsIdentity:
    """
    Represents the authenticated WebSocket identity.
    """

    def __init__(self, sub: str, user_id: str, tenant_id: str | None = None) -> None:
        self.sub = sub
        self.user_id = user_id
        self.tenant_id = tenant_id

@inject
async def get_ws_identity(
    websocket: WebSocket,
    db: AsyncSession = Depends(get_db),
) -> WsIdentity:
    """
    Resolves and validates the WebSocket identity using the same JWT
    verification logic as HTTP requests.

    Args:
        websocket: Incoming WebSocket connection.
        db: Async database session.

    Returns:
        WsIdentity with subject, user identifier, and optional tenant identifier.

    Raises:
        HTTPException 401 if token is missing or invalid.
    """
    token = websocket.query_params.get("token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing token",
        )

    try:
        claims = await verify_token(token)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )

    sub = claims.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    user = await auth_deps.current_user(db, authorization=f"Bearer {token}")

    tenant_id = getattr(user, "tenant_id", None)
    user_identifier = str(getattr(user, "external_sub", None) or user.id)

    return WsIdentity(sub=sub, user_id=user_identifier, tenant_id=tenant_id)

def build_channel_id(identity: WsIdentity) -> str:
    """
    Builds the logical channel identifier from the resolved identity.

    Args:
        identity: WsIdentity instance.

    Returns:
        Channel identifier string.
    """
    if identity.tenant_id:
        return str(identity.tenant_id)
    return identity.user_id
