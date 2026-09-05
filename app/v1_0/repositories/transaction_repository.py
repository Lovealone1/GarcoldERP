from typing import List, Optional
from sqlalchemy import select, desc, or_, func, tuple_, asc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from datetime import datetime

from app.v1_0.models import Bank, Transaction, TransactionType
from app.v1_0.schemas import TransactionCreate
from .base_repository import BaseRepository
from .paginated import list_paginated_keyset


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


def build_transaction_filters(
    *,
    q: Optional[str] = None,
    bank: Optional[str] = None,
    type_name: Optional[str] = None,
    origin: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> List:
    """
    Translate the transactions screen's filters into SQL.

    These used to be applied in the browser, which meant the client had to
    download every page first. Bank and type are matched by name because that
    is what the UI shows and what its dropdowns are built from.
    """
    # id == -1 is the synthetic opening-balance row, pinned separately.
    filters: List = [Transaction.id != -1]

    bank = _clean(bank)
    type_name = _clean(type_name)

    if bank:
        filters.append(Transaction.bank.has(Bank.name == bank))
    if type_name:
        filters.append(Transaction.type.has(TransactionType.name == type_name))

    if origin == "auto":
        filters.append(Transaction.is_auto.is_(True))
    elif origin == "manual":
        filters.append(Transaction.is_auto.is_(False))

    if date_from is not None:
        filters.append(Transaction.created_at >= date_from)
    if date_to is not None:
        filters.append(Transaction.created_at <= date_to)

    if q:
        term = q.strip()
        if term:
            like = f"%{term}%"
            conditions = [
                Transaction.description.ilike(like),
                Transaction.bank.has(Bank.name.ilike(like)),
                Transaction.type.has(TransactionType.name.ilike(like)),
            ]
            # The UI lets you search by row id, so an all-digit term also
            # matches the primary key exactly.
            if term.isdigit():
                conditions.append(Transaction.id == int(term))
            filters.append(or_(*conditions))

    return filters
class TransactionRepository(BaseRepository[Transaction]):
    def __init__(self) -> None:
        super().__init__(Transaction)

    async def create_transaction(self, payload: TransactionCreate, session: AsyncSession) -> Transaction:
        entity = Transaction(
            bank_id=payload.bank_id,
            amount=payload.amount,
            type_id=payload.type_id,
            description=payload.description,
            is_auto=payload.is_auto,
            created_at=payload.created_at,
        )
        await self.add(entity, session)
        return entity

    async def delete_transaction(self, transaction_id: int, session: AsyncSession) -> bool:
        entity = await self.get_by_id(transaction_id, session)
        if not entity:
            return False
        await self.delete(entity, session)
        return True

    async def get_ids_for_purchase_payment(self, purchase_id: int, session: AsyncSession) -> List[int]:
        p1 = f"%pago compra {purchase_id}%"
        p2 = f"%abono compra {purchase_id}%"
        stmt = select(Transaction.id).where(
            or_(Transaction.description.ilike(p1), Transaction.description.ilike(p2))
        )
        res = await session.execute(stmt)
        return list(res.scalars().all())

    async def get_ids_for_sale_payment(self, sale_id: int, session: AsyncSession) -> List[int]:
        pattern = f"%pago venta {sale_id}%"
        stmt = select(Transaction.id).where(Transaction.description.ilike(pattern))
        res = await session.execute(stmt)
        return list(res.scalars().all())

    async def get_ids_for_expense(self, expense_id: int, session: AsyncSession) -> List[int]:
        pattern = f"%Gasto% {expense_id}%"
        stmt = select(Transaction.id).where(Transaction.description.ilike(pattern))
        res = await session.execute(stmt)
        return list(res.scalars().all())

    async def get_transaction_id_for_purchase_payment(
        self, payment_id: int, purchase_id: int, session: AsyncSession
    ) -> Optional[int]:
        pattern = f"{payment_id} Abono compra {purchase_id}%"
        stmt = select(Transaction.id).where(Transaction.description.ilike(pattern))
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_transaction_id_for_sale_payment(
        self, payment_id: int, sale_id: int, session: AsyncSession
    ) -> Optional[int]:
        pattern = f"{payment_id} Abono venta {sale_id}%"
        stmt = select(Transaction.id).where(Transaction.description.ilike(pattern))
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_paginated(
        self,
        *,
        session,
        offset: int,
        limit: int,
        q: Optional[str] = None,
        bank: Optional[str] = None,
        type_name: Optional[str] = None,
        origin: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ):
        filters = build_transaction_filters(
            q=q,
            bank=bank,
            type_name=type_name,
            origin=origin,
            date_from=date_from,
            date_to=date_to,
        )
        # The pinned opening-balance row only belongs on an unfiltered listing;
        # showing it inside a filtered result would misrepresent the total.
        is_filtered = len(filters) > 1

        return await list_paginated_keyset(
            session=session,
            model=Transaction,
            created_col=Transaction.created_at,
            id_col=Transaction.id,
            limit=limit,
            offset=offset,
            base_filters=tuple(filters),
            eager=(selectinload(Transaction.bank), selectinload(Transaction.type)),
            pin_enabled=not is_filtered,
            pin_predicate=(Transaction.id == -1),
        )

    async def summarize_by_type(
        self,
        *,
        session,
        q: Optional[str] = None,
        bank: Optional[str] = None,
        type_name: Optional[str] = None,
        origin: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> dict[str, float]:
        """
        Total amount per transaction type for the current filter.

        The extract panel needs sums over the whole filtered set, not the
        visible page. It used to add up the rows the client had downloaded,
        which is only correct while the client downloads everything.

        Totals are returned per type name rather than pre-classified, so the
        screen keeps applying its own income/outgoing rules in one place.
        """
        filters = build_transaction_filters(
            q=q,
            bank=bank,
            type_name=type_name,
            origin=origin,
            date_from=date_from,
            date_to=date_to,
        )

        rows = (
            await session.execute(
                select(TransactionType.name, func.sum(Transaction.amount))
                .join(TransactionType, Transaction.type_id == TransactionType.id)
                .where(*filters)
                .group_by(TransactionType.name)
            )
        ).all()

        return {name: float(total or 0.0) for name, total in rows}

    async def distinct_filter_options(self, *, session) -> dict[str, List[str]]:
        """
        Bank and type names present in the data.

        The screen used to build its dropdowns from whatever rows it had
        downloaded; with server-side pagination it can no longer see them all.
        """
        banks = (
            await session.execute(
                select(Bank.name)
                .join(Transaction, Transaction.bank_id == Bank.id)
                .distinct()
                .order_by(Bank.name)
            )
        ).scalars().all()

        types = (
            await session.execute(
                select(TransactionType.name)
                .join(Transaction, Transaction.type_id == TransactionType.id)
                .distinct()
                .order_by(TransactionType.name)
            )
        ).scalars().all()

        return {"banks": list(banks), "types": list(types)}