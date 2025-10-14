from typing import List, Optional
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.v1_0.models import PurchasePayment
from app.v1_0.schemas import PurchasePaymentCreate  
from .base_repository import BaseRepository

class PurchasePaymentRepository(BaseRepository[PurchasePayment]):
    def __init__(self) -> None:
        super().__init__(PurchasePayment)

    async def create_payment(
    self,
    payload: PurchasePaymentCreate,
    session: AsyncSession
    ) -> PurchasePayment:
        payment = PurchasePayment(**payload.model_dump())
        await self.add(payment, session)
        return payment

    async def list_by_purchase(
        self,
        purchase_id: int,
        session: AsyncSession
    ) -> List[PurchasePayment]:
        """
        Return all payments for a given purchase.
        """
        stmt = select(PurchasePayment).where(PurchasePayment.purchase_id == purchase_id)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def delete_payment(
        self,
        payment_id: int,
        session: AsyncSession
    ) -> bool:
        """
        Delete a payment by ID. Return True if it existed.
        """
        payment = await self.get_by_id(payment_id, session)
        if not payment:
            return False
        await self.delete(payment, session)
        return True

    async def delete_by_purchase(
        self,
        purchase_id: int,
        session: AsyncSession
    ) -> int:
        """
        Delete all payments for a purchase. Return affected rows.
        """
        stmt = delete(PurchasePayment).where(PurchasePayment.purchase_id == purchase_id)
        result = await session.execute(stmt)
        await session.flush()
        return int(result.rowcount or 0)
