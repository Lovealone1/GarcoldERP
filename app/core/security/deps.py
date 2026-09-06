from dataclasses import dataclass
from typing import Any, Dict, Set, Optional
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Header, HTTPException, status

from app.storage.database.db_connector import async_session
from app.core.security.jwt import verify_token
from app.v1_0.models import User,Role

@dataclass(frozen=True)
class AuthContext:
    user: User
    role: str | None
    permissions: Set[str]

class AuthDeps:
    async def claims(self, authorization: str | None) -> Dict[str, Any]:
        if not authorization or not authorization.startswith("Bearer "):
            raise ValueError("token faltante")
        token = authorization.split(" ", 1)[1].strip()
        return await verify_token(token)

    async def current_user(self, session: AsyncSession, authorization: str | None) -> User:
        claims = await self.claims(authorization)
        sub = claims.get("sub")
        if not sub:
            raise ValueError("sub faltante en token")
        user = await session.scalar(select(User).where(User.external_sub == sub))
        if not user:
            raise ValueError("usuario no provisionado")
        return user

    async def permissions_for_role(self, session: AsyncSession, role_id: Optional[int]) -> Set[str]:
        if not role_id:
            return set()
        q = text("""
            select p.code
            from role_permission rp
            join permission p on p.id = rp.permission_id
            where rp.role_id = :rid
        """)
        rows = (await session.execute(q, {"rid": role_id})).all()
        return {r[0] for r in rows}

    async def context(self, session: AsyncSession, authorization: Optional[str]) -> AuthContext:
        user = await self.current_user(session, authorization)
        perms = await self.permissions_for_role(session, user.role_id)
        role_code: Optional[str] = None
        if user.role_id:
            role_code = getattr(user.role, "code", None) or await session.scalar(
                select(Role.code).where(Role.id == user.role_id)
            )
        return AuthContext(user=user, role=role_code, permissions=perms)

    def require_any(self, *codes: str):
        want = set(codes)
        async def _check(ctx: AuthContext):
            if want and not (want & ctx.permissions):
                raise PermissionError("forbidden")
            return True
        return _check

auth_deps = AuthDeps()

async def get_auth_context(
    authorization: str | None = Header(None),
) -> AuthContext:
    """
    Resolves authenticated context (user, role, permissions) from the Authorization header.

    Runs on its own short-lived session, deliberately not the one the handler
    receives from ``get_db``.

    FastAPI caches ``Depends(get_db)`` per request, so while this dependency
    asked for a session it got the *same* object the endpoint later works with.
    Its SELECTs autobegin a transaction on that session and nothing ever ends
    it, so by the time a service reached ``async with db.begin()`` SQLAlchemy
    raised ``A transaction is already begun on this Session``. Authentication
    is applied to every router (see app/v1_0/v1_router.py), so that broke every
    endpoint whose service opens its own transaction block -- expenses and the
    customer detail among them.

    Owning a separate session also keeps the two concerns independent: an
    authentication read is not committed or rolled back as part of a business
    write, and a failed business transaction cannot invalidate the identity
    that authorised it. ``get_ws_identity`` already worked this way.

    ``AuthContext.user`` is detached once this session closes. Its loaded
    columns stay readable; lazy relationship access would not, so everything
    the context needs -- the role code -- is resolved to a plain value here.

    Args:
        authorization: Authorization header with Bearer token.

    Returns:
        AuthContext with user, role code, and permissions.

    Raises:
        HTTPException 401 if token or user are invalid.
    """
    try:
        async with async_session() as db:
            return await auth_deps.context(db, authorization)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )