from typing import List, Optional, Tuple
from sqlalchemy import select, desc, or_, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.v1_0.models import Transaction
from app.v1_0.schemas import TransactionCreate
from .base_repository import BaseRepository

class TransactionRepository(BaseRepository[Transaction]):
    """CRUD for bank transactions."""

    def __init__(self) -> None:
        super().__init__(Transaction)

    async def create_transaction(
        self,
        payload: TransactionCreate,
        session: AsyncSession
    ) -> Transaction:
        """
        Create a Transaction from input schema. Flush only.
        """
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

    async def delete_transaction(
        self,
        transaction_id: int,
        session: AsyncSession
    ) -> bool:
        entity = await self.get_by_id(transaction_id, session)
        if not entity:
            return False
        await self.delete(entity, session)
        return True

    async def get_ids_for_purchase_payment(
        self,
        purchase_id: int,
        session: AsyncSession
    ) -> List[int]:
        """
        Matches descriptions containing 'pago compra {purchase_id}' or 'abono compra {purchase_id}'.
        """
        p1 = f"%pago compra {purchase_id}%"
        p2 = f"%abono compra {purchase_id}%"
        stmt = select(Transaction.id).where(
            or_(Transaction.description.ilike(p1), Transaction.description.ilike(p2))
        )
        return (await session.execute(stmt)).scalars().all()

    async def get_ids_for_sale_payment(
        self,
        sale_id: int,
        session: AsyncSession
    ) -> List[int]:
        """
        Matches descriptions containing 'pago venta {sale_id}'.
        """
        pattern = f"%pago venta {sale_id}%"
        stmt = select(Transaction.id).where(Transaction.description.ilike(pattern))
        return (await session.execute(stmt)).scalars().all()

    async def get_ids_for_expense(
        self,
        expense_id: int,
        session: AsyncSession
    ) -> List[int]:
        """
        Matches descriptions containing 'Gasto {expense_id}'.
        """
        pattern = f"%Gasto% {expense_id}%"
        stmt = select(Transaction.id).where(Transaction.description.ilike(pattern))
        return (await session.execute(stmt)).scalars().all()

    async def get_transaction_id_for_purchase_payment(
        self,
        payment_id: int,
        purchase_id: int,
        session: AsyncSession
    ) -> Optional[int]:
        """
        Matches '<payment_id> Abono compra {purchase_id}%'.
        """
        pattern = f"{payment_id} Abono compra {purchase_id}%"
        stmt = select(Transaction.id).where(Transaction.description.ilike(pattern))
        return (await session.execute(stmt)).scalar_one_or_none()

    async def get_transaction_id_for_sale_payment(
        self,
        payment_id: int,
        sale_id: int,
        session: AsyncSession
    ) -> Optional[int]:
        """
        Matches '<payment_id> Abono venta {sale_id}%'.
        """
        pattern = f"{payment_id} Abono venta {sale_id}%"
        stmt = select(Transaction.id).where(Transaction.description.ilike(pattern))
        return (await session.execute(stmt)).scalar_one_or_none()

    async def list_paginated(
        self,
        offset: int,
        limit: int,
        session: AsyncSession
    ) -> Tuple[List[Transaction], int]:
        """
        Order: id == -1 first, then created_at desc, then id desc.
        """
        pin_neg1 = case((Transaction.id == -1, 0), else_=1)
        stmt = (
            select(Transaction)
            .order_by(
                pin_neg1.asc(),
                desc(Transaction.created_at),
                Transaction.id.desc(),
            )
            .offset(offset)
            .limit(limit)
        )
        items = (await session.execute(stmt)).scalars().all()
        total = await session.scalar(select(func.count(Transaction.id)))
        return items, int(total or 0)
