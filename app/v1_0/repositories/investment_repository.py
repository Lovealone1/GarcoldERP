from typing import List, Optional, Tuple
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.v1_0.models import Investment
from app.v1_0.schemas import InvestmentCreate
from .base_repository import BaseRepository

class InvestmentRepository(BaseRepository[Investment]):
    def __init__(self) -> None:
        super().__init__(Investment)

    async def create_investment(
        self,
        payload: InvestmentCreate,
        session: AsyncSession
    ) -> Investment:
        """
        Create an Investment from input schema and flush to assign PK.
        """
        entity = Investment(
            name=payload.name,
            balance=payload.balance,
            maturity_date=payload.maturity_date,
        )
        await self.add(entity, session)
        return entity

    async def get_investment_by_id(
        self,
        investment_id: int,
        session: AsyncSession
    ) -> Optional[Investment]:
        return await super().get_by_id(investment_id, session)

    async def update_balance(
        self,
        investment_id: int,
        new_balance: float,
        session: AsyncSession
    ) -> Optional[Investment]:
        """
        Update only the balance field.
        """
        entity = await self.get_investment_by_id(investment_id, session)
        if not entity:
            return None
        entity.balance = new_balance
        await self.update(entity, session)
        return entity

    async def delete_investment(
        self,
        investment_id: int,
        session: AsyncSession
    ) -> bool:
        entity = await self.get_investment_by_id(investment_id, session)
        if not entity:
            return False
        await self.delete(entity, session)
        return True

    async def list_paginated(
        self,
        offset: int,
        limit: int,
        session: AsyncSession
    ) -> Tuple[List[Investment], int]:
        """
        Paginated list ordered by ID ASC. Returns (items, total).
        """
        stmt = (
            select(Investment)
            .order_by(Investment.id.asc())
            .offset(offset)
            .limit(limit)
        )
        items = (await session.execute(stmt)).scalars().all()
        total = await session.scalar(select(func.count(Investment.id)))
        return items, int(total or 0)

    async def list_all(
        self,
        session: AsyncSession
    ) -> List[Investment]:
        """
        Return ALL investments (unpaginated), ordered by ID ASC.
        """
        stmt = select(Investment).order_by(Investment.id.asc())
        return (await session.execute(stmt)).scalars().all()