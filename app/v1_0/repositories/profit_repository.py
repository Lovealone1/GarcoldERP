from typing import Optional, List, Tuple, Dict, Any
from datetime import date

from sqlalchemy import select, delete, func, Date, String, cast, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.v1_0.models import Customer, Profit, Sale
from app.v1_0.schemas import ProfitCreate
from .base_repository import BaseRepository
from .paginated import list_paginated_keyset
def _clean(value):
    """A field holding only whitespace means "no filter"."""
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


def build_profit_filters(*, q=None, date_from=None, date_to=None):
    """
    Translate the profits screen's filters into SQL.

    The search box matches against the sale number, as a substring, which is
    what the client-side version did.
    """
    filters = []

    if date_from is not None:
        filters.append(Profit.created_at >= date_from)
    if date_to is not None:
        filters.append(Profit.created_at <= date_to)

    term = _clean(q)
    if term:
        like = f"%{term}%"
        filters.append(
            or_(
                cast(Profit.sale_id, String).ilike(like),
                # The screen searches by customer too; it used to do so against
                # names it had fetched one sale at a time.
                Profit.sale_id.in_(
                    select(Sale.id)
                    .join(Customer, Sale.customer_id == Customer.id)
                    .where(Customer.name.ilike(like))
                ),
            )
        )

    return filters


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
        session: AsyncSession,
        q=None,
        date_from=None,
        date_to=None,
    ) -> Tuple[List[Profit], int]:
        """
        Keyset pagination: (created_at DESC, id DESC).
        Conserva la firma (items, total). Si luego quieres `has_next`,
        expón otro método o cambia la tupla a 3 elementos.
        """
        items, total, _has_next = await list_paginated_keyset(
            session=session,
            model=Profit,
            created_col=Profit.created_at,  
            id_col=Profit.id,                
            limit=limit,
            offset=offset,
            base_filters=tuple(
                build_profit_filters(q=q, date_from=date_from, date_to=date_to)
            ),
            eager=(),                        
            pin_enabled=False,               
            pin_predicate=None,
        )
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

    async def customer_names_for(self, sale_ids, *, session: AsyncSession) -> dict[int, str]:
        """
        Customer name per sale id, in one query.

        Replaces the screen's per-sale lookups.
        """
        ids = [int(i) for i in sale_ids if i is not None]
        if not ids:
            return {}

        rows = (
            await session.execute(
                select(Sale.id, Customer.name)
                .join(Customer, Sale.customer_id == Customer.id)
                .where(Sale.id.in_(ids))
            )
        ).all()
        return {int(sale_id): name for sale_id, name in rows}

    async def summarize(
        self,
        *,
        session: AsyncSession,
        q=None,
        date_from=None,
        date_to=None,
    ) -> dict:
        """Total profit over the whole filtered set, not just the page."""
        filters = build_profit_filters(q=q, date_from=date_from, date_to=date_to)
        row = (
            await session.execute(
                select(
                    func.coalesce(func.sum(Profit.profit), 0.0),
                    func.count(Profit.id),
                ).where(*filters)
            )
        ).first()
        total, count = row or (0.0, 0)
        return {"total": float(total or 0.0), "count": int(count or 0)}
