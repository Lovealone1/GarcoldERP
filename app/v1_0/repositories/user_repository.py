from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from app.v1_0.models import User

class UserRepository:
    model = User

    async def get_by_sub(self, sub: str, session: AsyncSession) -> User | None:
        return await session.scalar(select(User).where(User.external_sub == sub))

    async def count_all(self, session: AsyncSession) -> int:
        return int((await session.execute(text("select count(*) from users"))).scalar() or 0)

    async def advisory_xact_lock(self, session: AsyncSession) -> None:
        await session.execute(text("select pg_advisory_xact_lock(8420001)"))

    async def create_with_role(self, *, sub: str, email: str | None, name: str | None, role_id: int, session: AsyncSession) -> User:
        u = User(external_sub=sub, email=email, display_name=name, role_id=role_id)
        session.add(u)
        await session.flush()
        return u

    async def upsert_basics(self, u: User, email: str | None, name: str | None, session: AsyncSession) -> User:
        changed = False
        if email and u.email != email: u.email, changed = email, True
        if name and u.display_name != name: u.display_name, changed = name, True
        if changed: await session.flush()
        return u

    async def set_role_by_sub(self, sub: str, role_id: int, session: AsyncSession) -> None:
        u = await self.get_by_sub(sub, session)
        if not u: raise ValueError("user_not_found")
        u.role_id = role_id
        await session.flush()

    