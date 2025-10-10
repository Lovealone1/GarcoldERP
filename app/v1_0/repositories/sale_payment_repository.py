from typing import List
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.v1_0.models import SalePayment
from app.v1_0.schemas import SalePaymentCreate
from .base_repository import BaseRepository

class SalePaymentRepository(BaseRepository[SalePayment]):
    def __init__(self) -> None:
        super().__init__(SalePayment)

    async def create_payment(
        self,
        payload: SalePaymentCreate,
        session: AsyncSession
    ) -> SalePayment:
        """
        Insert a new sale payment and flush. No commit here.
        """
        payment = SalePayment(
            sale_id=payload.sale_id,
            bank_id=payload.bank_id,
            amount=payload.amount,
            created_at=payload.created_at,  
        )
        await self.add(payment, session)
        return payment

    async def list_by_sale(
        self,
        sale_id: int,
        session: AsyncSession
    ) -> List[SalePayment]:
        """
        Return all payments for the given sale.
        """
        stmt = select(SalePayment).where(SalePayment.sale_id == sale_id)
        return (await session.execute(stmt)).scalars().all()

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

    async def delete_by_sale(
        self,
        sale_id: int,
        session: AsyncSession
    ) -> int:
        """
        Delete all payments linked to a sale. Return affected rows.
        """
        stmt = delete(SalePayment).where(SalePayment.sale_id == sale_id)
        result = await session.execute(stmt)
        await session.flush()
        return int(result.rowcount or 0)
