from typing import List, Optional, Tuple
from sqlalchemy import select, func, update
from sqlalchemy.sql import literal
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

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
            bank_id=payload.bank_id, 
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
        result = await session.execute(stmt)
        items: List[Investment] = list(result.scalars().all())
        total = await session.scalar(select(func.count(Investment.id))) or 0
        return items, int(total or 0)

    async def increment_balance(self, investment_id: int, amount: float, session: AsyncSession):
        stmt = (
            update(Investment)
            .where(Investment.id == investment_id)
            .values(balance=Investment.balance + literal(amount))
            .returning(Investment)
        )
        res = await session.execute(stmt)
        return res.scalar_one_or_none()
    
    async def decrease_balance(
    self,
    investment_id: int,
    amount: float,
    session: AsyncSession,
    ) -> Optional[Investment]:
        if amount <= 0:
            raise ValueError("amount_must_be_positive")

        stmt = (
            update(Investment)
            .where(Investment.id == investment_id)
            .where(func.coalesce(Investment.balance, 0) >= amount)  
            .values(
                balance=func.coalesce(Investment.balance, 0) - amount
            )
            .returning(Investment)
        )
        res = await session.execute(stmt)
        inv = res.scalar_one_or_none()
        if inv is None:
            raise ValueError("insufficient_balance_or_not_found")
        return inv

    async def list_all(
        self,
        session: AsyncSession
    ) -> List[Investment]:
        """
        Return ALL investments (unpaginated), ordered by ID ASC.
        """
        stmt = select(Investment).order_by(Investment.id.asc())
        result = await session.execute(stmt)
        return list(result.scalars().all())