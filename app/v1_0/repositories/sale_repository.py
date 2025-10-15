from typing import Optional, List, Dict, Any, Tuple
from datetime import date, timedelta, datetime
from sqlalchemy import select, func, cast, Date
from sqlalchemy.ext.asyncio import AsyncSession

from app.v1_0.models import Sale
from app.v1_0.schemas import SaleInsert
from .base_repository import BaseRepository

class SaleRepository(BaseRepository[Sale]):
    def __init__(self) -> None:
        super().__init__(Sale)

    async def create_sale(
        self,
        dto: SaleInsert,
        session: AsyncSession
    ) -> Sale:
        """
        Creates a new Sale from the DTO, adds it to the session,
        and flushes to assign its primary key without committing.
        """
        sale = Sale(**dto.model_dump())
        await self.add(sale, session)
        return sale

    async def get_by_id(
        self,
        sale_id: int,
        session: AsyncSession
    ) -> Optional[Sale]:
        return await super().get_by_id(sale_id, session)

    async def get_all(
        self,
        session: AsyncSession
    ) -> List[Sale]:
        return await super().list_all(session)

    async def update_sale(
        self,
        sale_id: int,
        data: Dict[str, Any],
        session: AsyncSession
    ) -> Optional[Sale]:
        """
        Partial update. Flush only.
        """
        sale = await session.get(Sale, sale_id)
        if not sale:
            return None

        for field, value in data.items():
            setattr(sale, field, value)

        await session.flush()
        await session.refresh(sale)
        return sale

    async def delete_sale(
        self,
        sale_id: int,
        session: AsyncSession
    ) -> bool:
        sale = await self.get_by_id(sale_id, session)
        if not sale:
            return False
        await self.delete(sale, session)
        return True

    async def list_paginated(
        self,
        offset: int,
        limit: int,
        session: AsyncSession
    ) -> Tuple[List[Sale], int]:
        stmt = (
            select(Sale)
            .order_by(Sale.id.asc())
            .offset(offset)
            .limit(limit)
        )
        result = await session.execute(stmt)
        items: List[Sale] = list(result.scalars().all())
        total = await session.scalar(select(func.count(Sale.id)))
        return items, int(total or 0)

    async def sales_by_day(
        self,
        session: AsyncSession,
        date_from: date,
        date_to: date,
        tz: str = "UTC",
    ) -> List[Dict[str, Any]]:
        if date_from > date_to:
            date_from, date_to = date_to, date_from

        day_local = cast(func.timezone(tz, Sale.created_at), Date)

        stmt = (
            select(
                day_local.label("date"),
                func.coalesce(func.sum(Sale.total), 0).label("total"),
                func.coalesce(func.sum(Sale.remaining_balance), 0).label("remaining_balance"),
            )
            .where(
                func.timezone(tz, Sale.created_at) >= date_from,
                func.timezone(tz, Sale.created_at) < (date_to + timedelta(days=1)),
            )
            .group_by(day_local)
            .order_by(day_local)
        )

        rows = (await session.execute(stmt)).mappings().all()
        return [
            {
                "date": r["date"].isoformat(),
                "total": float(r["total"]),
                "remaining_balance": float(r["remaining_balance"]),
            }
            for r in rows
        ]

    async def accounts_receivable(
        self,
        session: AsyncSession,
        tz: str = "UTC",
    ) -> List[Dict[str, Any]]:
        """
        Sales with pending balance.
        Returns: [{ customer_id, date: 'YYYY-MM-DD', total, remaining_balance }, ...]
        """
        day_local = cast(func.timezone(tz, Sale.created_at), Date)

        stmt = (
            select(
                Sale.customer_id.label("customer_id"),
                day_local.label("date"),
                func.coalesce(Sale.total, 0).label("total"),
                func.coalesce(Sale.remaining_balance, 0).label("remaining_balance"),
            )
            .where(func.coalesce(Sale.remaining_balance, 0) > 0)
            .order_by(day_local.asc(), Sale.id.asc())
            .limit(10)
        )

        rows = (await session.execute(stmt)).mappings().all()
        return [
            {
                "customer_id": r["customer_id"],
                "date": r["date"].isoformat(),
                "total": float(r["total"]),
                "remaining_balance": float(r["remaining_balance"]),
            }
            for r in rows
        ]
    
    async def min_date(self, session: AsyncSession) -> Optional[date]:
        stmt = select(func.min(Sale.created_at))
        res = await session.execute(stmt)
        v = res.scalar_one_or_none()
        return v.date() if isinstance(v, datetime) else v