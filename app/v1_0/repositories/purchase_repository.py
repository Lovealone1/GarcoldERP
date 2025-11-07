from typing import List, Optional, Dict, Any, Tuple
from datetime import date, timedelta, datetime 

from sqlalchemy import select, func, Date, cast
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.v1_0.models import Purchase
from app.v1_0.schemas import PurchaseInsert
from .base_repository import BaseRepository
from .paginated import list_paginated_keyset

class PurchaseRepository(BaseRepository[Purchase]):
    def __init__(self) -> None:
        super().__init__(Purchase)

    async def create_purchase(
    self,
    dto: PurchaseInsert,
    session: AsyncSession
    ) -> Purchase:
        """
        Creates a new Purchase from the given DTO, adds it to the session,
        and flushes to assign its primary key without committing.
        """
        purchase = Purchase(**dto.model_dump())
        await self.add(purchase, session)
        return purchase

    async def get_purchase_by_id(
        self,
        purchase_id: int,
        session: AsyncSession
    ) -> Optional[Purchase]:
        """Return the Purchase by ID or None."""
        return await super().get_by_id(purchase_id, session)

    async def update_purchase(
        self,
        purchase_id: int,
        data: Dict[str, Any],
        session: AsyncSession
    ) -> Optional[Purchase]:
        """
        Update fields of an existing Purchase from a dict {field: value}.
        Flush only. No commit.
        """
        purchase = await session.get(Purchase, purchase_id)
        if not purchase:
            return None

        for field, value in data.items():
            setattr(purchase, field, value)

        await session.flush()
        await session.refresh(purchase)
        return purchase

    async def delete_purchase(
        self,
        purchase_id: int,
        session: AsyncSession
    ) -> bool:
        """Delete Purchase by ID. Return True if existed."""
        purchase = await self.get_purchase_by_id(purchase_id, session)
        if not purchase:
            return False
        await self.delete(purchase, session)
        return True

    async def list_paginated(
        self, *, session: AsyncSession, offset: int, limit: int
    ) -> Tuple[List[Purchase], int, bool]:
        return await list_paginated_keyset(
            session=session,
            model=Purchase,
            created_col=Purchase.purchase_date,
            id_col=Purchase.id,
            limit=limit,
            offset=offset,
            base_filters=(Purchase.id != -1,),
            eager=(
                selectinload(Purchase.supplier),
                selectinload(Purchase.bank),
                selectinload(Purchase.status),
            ),
            pin_enabled=True,
            pin_predicate=(Purchase.id == -1),
        )

    async def purchases_by_day(
        self,
        session: AsyncSession,
        date_from: date,
        date_to: date,
    ) -> List[Dict[str, Any]]:
        """
        Daily aggregates over [date_from, date_to] inclusive.
        Returns: [{ "date": date, "total": float, "balance": float }, ...]
        Groups by CAST(purchase_date AS DATE).
        """
        if date_from > date_to:
            date_from, date_to = date_to, date_from

        upper_exclusive = date_to + timedelta(days=1)
        day_col = cast(Purchase.purchase_date, Date)

        stmt = (
            select(
                day_col.label("date"),
                func.coalesce(func.sum(Purchase.total), 0.0).label("total"),
                func.coalesce(func.sum(Purchase.balance), 0.0).label("balance"),
            )
            .where(Purchase.purchase_date >= date_from)
            .where(Purchase.purchase_date < upper_exclusive)
            .group_by(day_col)
            .order_by(day_col.asc())
        )

        rows = await session.execute(stmt)
        result: List[Dict[str, Any]] = []
        for r in rows:
            result.append({
                "date": r.date,  
                "total": float(r.total or 0.0),
                "balance": float(r.balance or 0.0),
            })
        return result

    async def accounts_payable(
        self,
        session: AsyncSession,
        tz: str = "UTC",
    ) -> List[Dict[str, Any]]:
        """
        Purchases with pending balance.
        Returns: [{ supplier_id, date: 'YYYY-MM-DD', total, balance }, ...]
        Ordered by date ASC, then id ASC.
        """
        day_local = cast(func.timezone(tz, Purchase.purchase_date), Date)

        stmt = (
            select(
                Purchase.supplier_id.label("supplier_id"),
                day_local.label("date"),
                func.coalesce(Purchase.total, 0).label("total"),
                func.coalesce(Purchase.balance, 0).label("balance"),
            )
            .where(func.coalesce(Purchase.balance, 0) > 0)
            .order_by(day_local.asc(), Purchase.id.asc())
        )

        rows = (await session.execute(stmt)).mappings().all()
        return [
            {
                "supplier_id": r["supplier_id"],
                "date": r["date"].isoformat(),
                "total": float(r["total"]),
                "balance": float(r["balance"]),
            }
            for r in rows
        ]
        
    async def min_date(self, session: AsyncSession) -> Optional[date]:
        stmt = select(func.min(Purchase.purchase_date))
        res = await session.execute(stmt)
        v = res.scalar_one_or_none()
        if isinstance(v, datetime):
            return v.date()
        return v