from typing import Optional, Dict, Any
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security.deps import auth_deps
from app.v1_0.services import AuthService

# app/v1_0/routers/_auth_helpers.py
async def require_claims(authorization: Optional[str]) -> Dict[str, Any]:
    if not authorization:
        raise HTTPException(401, "missing Authorization")
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "invalid auth scheme")
    try:
        return await auth_deps.claims(authorization)
    except ValueError as e:
        # añade logging del mensaje exacto
        from app.core.logger import logger
        logger.warning(f"[Auth] verify_token failed: {e}")
        raise HTTPException(status_code=401, detail=str(e))


async def ensure_current_user(
    db: AsyncSession,
    authorization: Optional[str],
    auth_service: AuthService,
):
    claims = await require_claims(authorization)
    sub = claims.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="sub faltante")

    email = claims.get("email")
    name = None
    umd = claims.get("user_metadata")
    if isinstance(umd, dict):
        name = umd.get("full_name") or umd.get("name")

    return await auth_service.ensure_user(
        db, sub=sub, email=email, display_name=name
    )
