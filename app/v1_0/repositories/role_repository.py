from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.v1_0.models import Role

class RoleRepository:
    async def get_id_by_code(self, code: str, session: AsyncSession) -> int | None:
        return await session.scalar(select(Role.id).where(Role.code == code))

    async def get_code_by_id(self, id_: int, session: AsyncSession) -> str | None:
        return await session.scalar(select(Role.code).where(Role.id == id_))
    
    async def list_all(self, session: AsyncSession) -> list[Role]:
        res = await session.execute(select(Role).order_by(Role.code))
        rows: List[Role] = list(res.scalars().all())
        return rows