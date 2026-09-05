from typing import Optional, List, Dict, Any, Tuple
from datetime import date, timedelta, datetime
from sqlalchemy import select, func, cast, Date, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.v1_0.models import Bank, Customer, Sale, Status
from app.v1_0.schemas import SaleInsert
from .base_repository import BaseRepository
from .paginated import list_paginated_keyset


def build_sale_filters(
    *,
    q: Optional[str] = None,
    status: Optional[str] = None,
    bank: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> List:
    """
    Translate the sales screen's filters into SQL.

    These ran in the browser, which forced the client to download every page
    first. Status and bank match by name because that is what the UI shows and
    what its dropdowns offer.
    """
    filters: List = []

    if status:
        filters.append(Sale.status.has(Status.name == status))
    if bank:
        filters.append(Sale.bank.has(Bank.name == bank))
    if date_from is not None:
        filters.append(Sale.created_at >= date_from)
    if date_to is not None:
        filters.append(Sale.created_at <= date_to)

    if q:
        term = q.strip()
        if term:
            like = f"%{term}%"
            conditions = [
                Sale.customer.has(Customer.name.ilike(like)),
                Sale.bank.has(Bank.name.ilike(like)),
                Sale.status.has(Status.name.ilike(like)),
            ]
            # The screen lets you search by sale number.
            if term.isdigit():
                conditions.append(Sale.id == int(term))
            filters.append(or_(*conditions))

    return filters
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
        *,
        session: AsyncSession,
        offset: int,
        limit: int,
        q: Optional[str] = None,
        status: Optional[str] = None,
        bank: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Tuple[List[Sale], int, bool]:
        extra = build_sale_filters(
            q=q, status=status, bank=bank, date_from=date_from, date_to=date_to
        )
        return await list_paginated_keyset(
            session=session,
            model=Sale,
            created_col=Sale.created_at,
            id_col=Sale.id,
            limit=limit,
            offset=offset,
            base_filters=(Sale.id != -1, *extra),
            eager=(
                selectinload(Sale.customer),
                selectinload(Sale.bank),
                selectinload(Sale.status),
            ),
            # The pinned row does not belong inside a filtered result: it would
            # add a row that does not match and inflate the reported total.
            pin_enabled=not extra,
            pin_predicate=(Sale.id == -1),
        )

    async def summarize(
        self,
        *,
        session: AsyncSession,
        q: Optional[str] = None,
        status: Optional[str] = None,
        bank: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Dict[str, float]:
        """
        Totals over the whole filtered set.

        The screen shows a summed total for the current filter; it used to add
        up the rows the client had downloaded.
        """
        extra = build_sale_filters(
            q=q, status=status, bank=bank, date_from=date_from, date_to=date_to
        )
        row = (
            await session.execute(
                select(
                    func.coalesce(func.sum(Sale.total), 0.0),
                    func.coalesce(func.sum(Sale.remaining_balance), 0.0),
                    func.count(Sale.id),
                ).where(Sale.id != -1, *extra)
            )
        ).first()

        total, remaining, count = row or (0.0, 0.0, 0)
        return {
            "total": float(total or 0.0),
            "remaining_balance": float(remaining or 0.0),
            "count": int(count or 0),
        }

    async def distinct_filter_options(self, *, session: AsyncSession) -> Dict[str, List[str]]:
        """Bank and status names present in sales, for the filter dropdowns."""
        banks = (
            await session.execute(
                select(Bank.name)
                .join(Sale, Sale.bank_id == Bank.id)
                .distinct()
                .order_by(Bank.name)
            )
        ).scalars().all()

        statuses = (
            await session.execute(
                select(Status.name)
                .join(Sale, Sale.status_id == Status.id)
                .distinct()
                .order_by(Status.name)
            )
        ).scalars().all()

        return {"banks": list(banks), "statuses": list(statuses)}

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