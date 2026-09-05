from typing import List, Optional, Tuple, Dict, Any
from datetime import date, datetime

from sqlalchemy import select, func, Date, cast, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.v1_0.models import Bank, Expense, ExpenseCategory
from app.v1_0.schemas import ExpenseCreate
from .base_repository import BaseRepository


def _clean(value: Optional[str]) -> Optional[str]:
    """
    Normalise an exact-match filter.

    A form field that contains only whitespace means "no filter", not "match a
    name made of spaces". Free-text search already trimmed; these did not.
    """
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


def build_expense_filters(
    *,
    q: Optional[str] = None,
    category: Optional[str] = None,
    bank: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> List:
    """
    Translate the expenses screen's filters into SQL.

    These were the worst off of the four: the client sent them, the API ignored
    them, and the hook did not filter locally either -- the page filtered only
    the eight rows it happened to be showing, so the result and its pagination
    disagreed with each other.
    """
    filters: List = []

    category = _clean(category)
    bank = _clean(bank)

    if category:
        filters.append(Expense.category.has(ExpenseCategory.name == category))
    if bank:
        filters.append(Expense.bank.has(Bank.name == bank))
    if date_from is not None:
        filters.append(Expense.expense_date >= date_from)
    if date_to is not None:
        filters.append(Expense.expense_date <= date_to)

    if q:
        term = q.strip()
        if term:
            like = f"%{term}%"
            conditions = [
                Expense.category.has(ExpenseCategory.name.ilike(like)),
                Expense.bank.has(Bank.name.ilike(like)),
            ]
            if term.isdigit():
                conditions.append(Expense.id == int(term))
            filters.append(or_(*conditions))

    return filters
from .paginated import list_paginated_keyset

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
        *,
        session: AsyncSession,
        offset: int,
        limit: int,
        q: Optional[str] = None,
        category: Optional[str] = None,
        bank: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Tuple[List[Expense], int, bool]:
        extra = build_expense_filters(
            q=q, category=category, bank=bank, date_from=date_from, date_to=date_to
        )
        return await list_paginated_keyset(
            session=session,
            model=Expense,
            created_col=Expense.expense_date,
            id_col=Expense.id,
            limit=limit,
            offset=offset,
            base_filters=(Expense.id != -1, *extra),
            eager=(
                selectinload(Expense.category),
                selectinload(Expense.bank),
            ),
            pin_enabled=not extra,
            pin_predicate=(Expense.id == -1),
        )

    async def summarize(
        self,
        *,
        session: AsyncSession,
        q: Optional[str] = None,
        category: Optional[str] = None,
        bank: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Dict[str, float]:
        extra = build_expense_filters(
            q=q, category=category, bank=bank, date_from=date_from, date_to=date_to
        )
        row = (
            await session.execute(
                select(
                    func.coalesce(func.sum(Expense.amount), 0.0),
                    func.count(Expense.id),
                ).where(Expense.id != -1, *extra)
            )
        ).first()

        total, count = row or (0.0, 0)
        return {"total": float(total or 0.0), "count": int(count or 0)}

    async def distinct_filter_options(self, *, session: AsyncSession) -> Dict[str, List[str]]:
        """
        Category and bank names present in expenses.

        The screen built its bank dropdown from the rows on the current page,
        so the options changed as you paged.
        """
        categories = (
            await session.execute(
                select(ExpenseCategory.name)
                .join(Expense, Expense.expense_category_id == ExpenseCategory.id)
                .distinct()
                .order_by(ExpenseCategory.name)
            )
        ).scalars().all()

        banks = (
            await session.execute(
                select(Bank.name)
                .join(Expense, Expense.bank_id == Bank.id)
                .distinct()
                .order_by(Bank.name)
            )
        ).scalars().all()

        return {"categories": list(categories), "banks": list(banks)}

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
