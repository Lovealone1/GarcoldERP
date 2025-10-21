from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.v1_0.repositories.user_repository import UserRepository

class UserService:
    def __init__(self, user_repository: UserRepository) -> None:
        self.user_repo = user_repository

    async def set_role_by_sub(self, *, sub: str, role_id: int, db: AsyncSession) -> None:
        async with db.begin():
            await self.user_repo.set_role_by_sub(sub, role_id, db)

    async def upsert_basics_by_sub(
        self, *, sub: str, email: Optional[str], name: Optional[str], db: AsyncSession
    ) -> None:
        u = await self.user_repo.get_by_sub(sub, db)
        if not u:
            return
        await self.user_repo.upsert_basics(u, email=email, name=name, session=db)
        await db.commit() 