from typing import Optional, List, Tuple, Dict, Any
from datetime import date

from sqlalchemy import select, delete, func, Date, cast
from sqlalchemy.ext.asyncio import AsyncSession

from app.v1_0.models import Profit
from app.v1_0.schemas import ProfitCreate
from .base_repository import BaseRepository

class ProfitRepository(BaseRepository[Profit]):
    def __init__(self) -> None:
        super().__init__(Profit)

    async def create_profit(
        self,
        payload: ProfitCreate,
        session: AsyncSession
    ) -> Profit:
        entity = Profit(
            sale_id=payload.sale_id,
            profit=payload.profit,
            created_at=payload.created_at,
        )
        await self.add(entity, session)
        return entity

    async def get_by_sale(
        self,
        sale_id: int,
        session: AsyncSession
    ) -> Optional[Profit]:
        stmt = select(Profit).where(Profit.sale_id == sale_id)
        return (await session.execute(stmt)).scalar_one_or_none()

    async def delete_by_sale(
        self,
        sale_id: int,
        session: AsyncSession
    ) -> int:
        stmt = delete(Profit).where(Profit.sale_id == sale_id)
        result = await session.execute(stmt)
        await session.flush()
        return int(result.rowcount or 0)

    async def list_paginated(
        self,
        offset: int,
        limit: int,
        session: AsyncSession
    ) -> Tuple[List[Profit], int]:
        stmt = (
            select(Profit)
            .order_by(Profit.id.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await session.execute(stmt)
        items: List[Profit ]= list(result.scalars().all())
        total = await session.scalar(select(func.count(Profit.id)))
        return items, int(total or 0)

    async def get_profit_by_sale_id(
        self,
        sale_id: int,
        session: AsyncSession
    ) -> Optional[Profit]:
        stmt = select(Profit).where(Profit.sale_id == sale_id)
        return (await session.execute(stmt)).scalar_one_or_none()

    async def profits_by_day(
        self,
        session: AsyncSession,
        date_from: date,
        date_to: date,
    ) -> List[Dict[str, Any]]:
        """
        Daily sum over [date_from, date_to] inclusive based on created_at.
        Returns: [{ "date": 'YYYY-MM-DD', "profit": float }, ...]
        """
        if date_from > date_to:
            date_from, date_to = date_to, date_from

        day_col = cast(Profit.created_at, Date)

        stmt = (
            select(
                day_col.label("date"),
                func.coalesce(func.sum(Profit.profit), 0).label("profit"),
            )
            .where(day_col >= date_from)
            .where(day_col <= date_to)
            .group_by(day_col)
            .order_by(day_col)
        )

        rows = (await session.execute(stmt)).mappings().all()
        return [
            {"date": r["date"].isoformat(), "profit": float(r["profit"])}
            for r in rows
        ]
