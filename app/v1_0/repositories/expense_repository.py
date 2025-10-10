from typing import List, Tuple, Dict, Any
from datetime import date

from sqlalchemy import select, func, Date, cast
from sqlalchemy.ext.asyncio import AsyncSession

from app.v1_0.models import Expense
from app.v1_0.schemas import ExpenseCreate
from .base_repository import BaseRepository

class ExpenseRepository(BaseRepository[Expense]):
    def __init__(self) -> None:
        super().__init__(Expense)

    async def create_expense(
        self,
        payload: ExpenseCreate,
        session: AsyncSession
    ) -> Expense:
        """
        Create an expense from input schema and flush to assign PK.
        """
        entity = Expense(
            expense_category_id=payload.expense_category_id,
            bank_id=payload.bank_id,
            amount=payload.amount,
            expense_date=payload.expense_date,
        )
        await self.add(entity, session)
        return entity

    async def delete_expense(
        self,
        expense_id: int,
        session: AsyncSession
    ) -> bool:
        """
        Delete an expense by ID. Return True if it existed.
        """
        entity = await self.get_by_id(expense_id, session)
        if not entity:
            return False
        await self.delete(entity, session)
        return True

    async def list_paginated(
        self,
        offset: int,
        limit: int,
        session: AsyncSession
    ) -> Tuple[List[Expense], int]:
        """
        Paginated list ordered by ID ASC. Returns (items, total).
        """
        stmt = (
            select(Expense)
            .order_by(Expense.id.asc())
            .offset(offset)
            .limit(limit)
        )
        items = (await session.execute(stmt)).scalars().all()
        total = await session.scalar(select(func.count(Expense.id)))
        return items, int(total or 0)

    async def expenses_by_day(
        self,
        session: AsyncSession,
        date_from: date,
        date_to: date,
    ) -> List[Dict[str, Any]]:
        """
        Daily aggregates in inclusive range [date_from, date_to].
        Works whether `expense_date` is DATE or TIMESTAMP by casting to DATE.
        Returns: [{ "date": 'YYYY-MM-DD', "expense_category_id": int, "amount": float }, ...]
        """
        if date_from > date_to:
            date_from, date_to = date_to, date_from

        day_col = cast(Expense.expense_date, Date)
        stmt = (
            select(
                day_col.label("date"),
                Expense.expense_category_id.label("expense_category_id"),
                func.coalesce(func.sum(Expense.amount), 0).label("amount"),
            )
            .where(day_col >= date_from)
            .where(day_col <= date_to)
            .group_by(day_col, Expense.expense_category_id)
            .order_by(day_col.asc(), Expense.expense_category_id.asc())
        )

        rows = (await session.execute(stmt)).mappings().all()
        return [
            {
                "date": r["date"].isoformat(),
                "expense_category_id": int(r["expense_category_id"]),
                "amount": float(r["amount"]),
            }
            for r in rows
        ]
