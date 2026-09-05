from typing import List, Optional, Dict, Any, Tuple
from datetime import date, timedelta, datetime 

from sqlalchemy import select, func, Date, cast, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.v1_0.models import Bank, Purchase, Status, Supplier
from app.v1_0.schemas import PurchaseInsert
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


def build_purchase_filters(
    *,
    q: Optional[str] = None,
    status: Optional[str] = None,
    bank: Optional[str] = None,
    supplier: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> List:
    """
    Translate the purchases screen's filters into SQL.

    They ran in the browser, which forced the client to download every page
    first. Names rather than ids, because names are what the UI shows.
    """
    filters: List = []

    status = _clean(status)
    bank = _clean(bank)
    supplier = _clean(supplier)

    if status:
        filters.append(Purchase.status.has(Status.name == status))
    if bank:
        filters.append(Purchase.bank.has(Bank.name == bank))
    if supplier:
        filters.append(Purchase.supplier.has(Supplier.name == supplier))
    if date_from is not None:
        filters.append(Purchase.purchase_date >= date_from)
    if date_to is not None:
        filters.append(Purchase.purchase_date <= date_to)

    if q:
        term = q.strip()
        if term:
            like = f"%{term}%"
            conditions = [
                Purchase.supplier.has(Supplier.name.ilike(like)),
                Purchase.bank.has(Bank.name.ilike(like)),
                Purchase.status.has(Status.name.ilike(like)),
            ]
            if term.isdigit():
                conditions.append(Purchase.id == int(term))
            filters.append(or_(*conditions))

    return filters
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
        self,
        *,
        session: AsyncSession,
        offset: int,
        limit: int,
        q: Optional[str] = None,
        status: Optional[str] = None,
        bank: Optional[str] = None,
        supplier: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Tuple[List[Purchase], int, bool]:
        extra = build_purchase_filters(
            q=q,
            status=status,
            bank=bank,
            supplier=supplier,
            date_from=date_from,
            date_to=date_to,
        )
        return await list_paginated_keyset(
            session=session,
            model=Purchase,
            created_col=Purchase.purchase_date,
            id_col=Purchase.id,
            limit=limit,
            offset=offset,
            base_filters=(Purchase.id != -1, *extra),
            eager=(
                selectinload(Purchase.supplier),
                selectinload(Purchase.bank),
                selectinload(Purchase.status),
            ),
            # A pinned row inside a filtered result would not match the filter
            # and would inflate the reported total.
            pin_enabled=not extra,
            pin_predicate=(Purchase.id == -1),
        )

    async def summarize(
        self,
        *,
        session: AsyncSession,
        q: Optional[str] = None,
        status: Optional[str] = None,
        bank: Optional[str] = None,
        supplier: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Dict[str, float]:
        """Totals over the whole filtered set, not the visible page."""
        extra = build_purchase_filters(
            q=q,
            status=status,
            bank=bank,
            supplier=supplier,
            date_from=date_from,
            date_to=date_to,
        )
        row = (
            await session.execute(
                select(
                    func.coalesce(func.sum(Purchase.total), 0.0),
                    func.coalesce(func.sum(Purchase.balance), 0.0),
                    func.count(Purchase.id),
                ).where(Purchase.id != -1, *extra)
            )
        ).first()

        total, balance, count = row or (0.0, 0.0, 0)
        return {
            "total": float(total or 0.0),
            "balance": float(balance or 0.0),
            "count": int(count or 0),
        }

    async def distinct_filter_options(self, *, session: AsyncSession) -> Dict[str, List[str]]:
        """Names present in purchases, for the filter dropdowns."""
        banks = (
            await session.execute(
                select(Bank.name)
                .join(Purchase, Purchase.bank_id == Bank.id)
                .distinct()
                .order_by(Bank.name)
            )
        ).scalars().all()

        statuses = (
            await session.execute(
                select(Status.name)
                .join(Purchase, Purchase.status_id == Status.id)
                .distinct()
                .order_by(Status.name)
            )
        ).scalars().all()

        suppliers = (
            await session.execute(
                select(Supplier.name)
                .join(Purchase, Purchase.supplier_id == Supplier.id)
                .distinct()
                .order_by(Supplier.name)
            )
        ).scalars().all()

        return {
            "banks": list(banks),
            "statuses": list(statuses),
            "suppliers": list(suppliers),
        }

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