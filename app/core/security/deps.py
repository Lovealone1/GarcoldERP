from dataclasses import dataclass
from typing import Any, Dict, Set
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

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

    async def permissions_for_role(self, session: AsyncSession, role_id: int) -> Set[str]:
        q = text("""
            select p.code
            from role_permission rp
            join permission p on p.id = rp.permission_id
            where rp.role_id = :rid
        """)
        rows = (await session.execute(q, {"rid": role_id})).all()
        return {r[0] for r in rows}

    async def context(self, session: AsyncSession, authorization: str | None) -> AuthContext:
        user = await self.current_user(session, authorization)
        perms = await self.permissions_for_role(session, user.role_id)
        role_code = getattr(user.role, "code", None)
        if role_code is None:
            role_code = await session.scalar(select(Role.code).where(Role.id == user.role_id))
        return AuthContext(user=user, role=role_code, permissions=perms)

    def require_any(self, *codes: str):
        want = set(codes)
        async def _check(ctx: AuthContext):
            if want and not (want & ctx.permissions):
                raise PermissionError("forbidden")
            return True
        return _check

auth_deps = AuthDeps()
