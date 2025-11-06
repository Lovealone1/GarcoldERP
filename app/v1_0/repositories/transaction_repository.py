from typing import List, Optional
from sqlalchemy import select, desc, or_, func, tuple_, asc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.v1_0.models import Transaction
from app.v1_0.schemas import TransactionCreate
from .base_repository import BaseRepository

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

    async def list_paginated(self, offset: int, limit: int, session: AsyncSession):
        pin_exists = bool(await session.scalar(
            select(func.count()).where(Transaction.id == -1)
        ))
        eff_offset = max(offset - (1 if pin_exists else 0), 0)

        total_rows = await session.scalar(
            select(func.count(Transaction.id)).where(Transaction.id != -1)
        ) or 0

        take = limit + 1

        if eff_offset == 0:
            rows = (
                await session.execute(
                    select(Transaction)
                    .options(selectinload(Transaction.bank), selectinload(Transaction.type))
                    .where(Transaction.id != -1)
                    .order_by(desc(Transaction.created_at), Transaction.id.desc())
                    .limit(take)
                )
            ).scalars().all()

        else:
            anchor = (
                await session.execute(
                    select(Transaction.created_at, Transaction.id)
                    .where(Transaction.id != -1)
                    .order_by(desc(Transaction.created_at), Transaction.id.desc())
                    .offset(eff_offset - 1).limit(1)
                )
            ).first()

            if not anchor:
                rows = []
            else:
                ac, aid = anchor
                rows = (
                    await session.execute(
                        select(Transaction)
                        .options(selectinload(Transaction.bank), selectinload(Transaction.type))
                        .where(Transaction.id != -1)
                        .where(tuple_(Transaction.created_at, Transaction.id) < tuple_(ac, aid))  
                        .order_by(desc(Transaction.created_at), Transaction.id.desc())
                        .limit(take)
                    )
                ).scalars().all()

        items: list[Transaction] = []
        if offset == 0 and pin_exists:
            pin = (
                await session.execute(
                    select(Transaction)
                    .options(selectinload(Transaction.bank), selectinload(Transaction.type))
                    .where(Transaction.id == -1).limit(1)
                )
            ).scalars().first()
            if pin:
                items.append(pin)

        remaining_core = max(total_rows - eff_offset, 0)
        visible_core = min(limit, remaining_core)  

        has_next = eff_offset + visible_core < total_rows

        page_rows = rows[:visible_core] if eff_offset == 0 else rows[:visible_core]
        items.extend(page_rows)

        total = total_rows + (1 if pin_exists else 0)
        return items, total, has_next
