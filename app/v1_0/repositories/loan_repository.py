# app/v1_0/repositories/loan_repository.py
from typing import List, Optional, Tuple
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.v1_0.models import Loan
from app.v1_0.entities import LoanDTO
from .base_repository import BaseRepository

class LoanRepository(BaseRepository[Loan]):
    def __init__(self) -> None:
        super().__init__(Loan)

    async def create_loan(self, dto: LoanDTO, session: AsyncSession) -> Loan:
        """
        Create a new Loan from DTO and flush to assign its ID.
        """
        entity = Loan(**dto.model_dump())
        await self.add(entity, session)
        return entity

    async def update_amount(
        self,
        loan_id: int,
        new_amount: float,
        session: AsyncSession
    ) -> Optional[Loan]:
        """
        Update only the amount field for a Loan.
        """
        entity = await self.get_by_id(loan_id, session)
        if not entity:
            return None

        entity.amount = new_amount
        await session.flush()
        await session.refresh(entity)
        return entity

    async def delete_loan(
        self,
        loan_id: int,
        session: AsyncSession
    ) -> bool:
        """
        Delete a Loan by its ID and return True if it existed.
        """
        entity = await self.get_by_id(loan_id, session)
        if not entity:
            return False

        await self.delete(entity, session)
        return True

    async def list_paginated(
        self,
        offset: int,
        limit: int,
        session: AsyncSession
    ) -> Tuple[List[Loan], int]:
        """
        Paginated list of Loans, ordered by ID ascending.
        Returns (items, total).
        """
        stmt = (
            select(Loan)
            .order_by(Loan.id.asc())
            .offset(offset)
            .limit(limit)
        )
        items = (await session.execute(stmt)).scalars().all()
        total = await session.scalar(select(func.count(Loan.id)))
        return items, int(total or 0)

    async def list_all(self, session: AsyncSession) -> List[Loan]:
        """
        Return all Loans, ordered by ID ascending.
        """
        stmt = select(Loan).order_by(Loan.id.asc())
        result = await session.execute(stmt)
        return list(result.scalars().all())
