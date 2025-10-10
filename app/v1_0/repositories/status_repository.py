from typing import List, Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.v1_0.models import Status
from .base_repository import BaseRepository

class StatusRepository(BaseRepository[Status]):
    def __init__(self) -> None:
        super().__init__(Status)

    async def get_by_id(
        self,
        status_id: int,
        session: AsyncSession
    ) -> Optional[Status]:
        """
        Return a Status by its ID.
        """
        return await super().get_by_id(status_id, session)

    async def get_by_name(
        self,
        name: str,
        session: AsyncSession
    ) -> Optional[Status]:
        """
        Return a Status by its name (case-insensitive).
        """
        stmt = select(Status).where(func.lower(Status.name) == name.lower())
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_statuses(
        self,
        session: AsyncSession
    ) -> List[Status]:
        """
        Return all Status records ordered by ID.
        """
        stmt = select(Status).order_by(Status.id.asc())
        result = await session.execute(stmt)
        return list(result.scalars().all())