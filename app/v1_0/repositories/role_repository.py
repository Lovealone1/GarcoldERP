from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.v1_0.models import Role

class RoleRepository:
    async def get_id_by_code(self, code: str, session: AsyncSession) -> int | None:
        return await session.scalar(select(Role.id).where(Role.code == code))

    async def get_code_by_id(self, id_: int, session: AsyncSession) -> str | None:
        return await session.scalar(select(Role.code).where(Role.id == id_))