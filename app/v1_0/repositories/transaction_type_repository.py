from typing import Optional, List
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.v1_0.models import TransactionType
from .base_repository import BaseRepository

class TransactionTypeRepository(BaseRepository[TransactionType]):
    """
    Repository for CRUD operations on TransactionType.
    Each method explicitly receives an AsyncSession.
    """

    def __init__(self) -> None:
        super().__init__(TransactionType)

    async def create_type(
        self,
        name: str,
        session: AsyncSession
    ) -> TransactionType:
        """
        Create a new TransactionType with the given name.
        """
        entity = TransactionType(name=name)
        await self.add(entity, session)
        return entity

    async def get_by_id(
        self,
        type_id: int,
        session: AsyncSession
    ) -> Optional[TransactionType]:
        """
        Retrieve a TransactionType by its ID.
        """
        return await super().get_by_id(type_id, session)

    async def get_by_name(
        self,
        name: str,
        session: AsyncSession
    ) -> Optional[TransactionType]:
        """
        Retrieve a TransactionType that matches the given name (case-insensitive).
        """
        stmt = select(TransactionType).where(func.lower(TransactionType.name) == name.lower())
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(
        self,
        session: AsyncSession
    ) -> List[TransactionType]:
        """
        Retrieve all transaction types, ordered alphabetically by name.
        """
        stmt = select(TransactionType).order_by(TransactionType.name.asc())
        rows = await session.execute(stmt)
        return list(rows.scalars().all())