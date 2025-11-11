from datetime import datetime
from typing import List, Optional
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import logger
from app.v1_0.entities import SalePaymentDTO, SalePaymentViewDTO 
from app.v1_0.schemas import SalePaymentCreate, TransactionCreate
from app.v1_0.repositories import (
    SaleRepository, 
    StatusRepository, 
    SalePaymentRepository, 
    BankRepository, 
    CustomerRepository
    )
from app.v1_0.services import TransactionService
from app.core.realtime import publish_realtime_event

class SalePaymentService: 
    def __init__(self,
        sale_repository: SaleRepository,
        status_repository: StatusRepository,
        sale_payment_repository: SalePaymentRepository,
        bank_repository: BankRepository,
        customer_repository: CustomerRepository,
        transaction_service: TransactionService
    ):
        self.sale_repository = sale_repository
        self.sale_payment_repository = sale_payment_repository
        self.status_repository = status_repository
        self.bank_repository = bank_repository
        self.customer_repository = customer_repository
        self.transaction_service = transaction_service
        
    async def create_sale_payment(
        self,
        payload: SalePaymentCreate,
        db: AsyncSession,
        channel_id: Optional[str] = None,
    ) -> SalePaymentDTO:
        """
        Register a payment for a credit sale, update balances, and emit realtime events.

        Operations:
        - Validate that the sale exists and is a credit sale.
        - Validate payment amount against remaining balance.
        - Create a payment record.
        - Decrease sale remaining balance.
        - Decrease customer credit balance.
        - Optionally mark sale as fully paid ("venta cancelada") when remaining becomes zero.
        - Increase bank balance and create a corresponding transaction.
        - Optionally publish realtime events for the payment and updated sale.

        Args:
            payload: Data for the sale payment (sale_id, bank_id, amount).
            db: Active async database session.
            channel_id: Optional realtime channel to publish events to.

        Returns:
            SalePaymentDTO representing the created payment.

        Raises:
            HTTPException: If the sale does not exist, is not credit,
                or if the payment amount is invalid.
            Exception: Propagated if database operations fail (after rollback).
        """
        async def _run() -> tuple[SalePaymentDTO, int]:
            sale = await self.sale_repository.get_by_id(payload.sale_id, session=db)
            if not sale:
                raise HTTPException(status_code=404, detail="Sale not found.")

            status_row = await self.status_repository.get_by_id(
                sale.status_id,
                session=db,
            )
            if not status_row or status_row.name.lower() != "venta credito":
                raise HTTPException(
                    status_code=400,
                    detail="Only credit sales can receive payments.",
                )

            remaining = float(sale.remaining_balance or 0.0)
            amount = float(payload.amount or 0.0)

            if remaining <= 0:
                raise HTTPException(
                    status_code=400,
                    detail="Sale has no pending balance.",
                )

            if amount <= 0 or amount > remaining:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid amount or exceeds pending balance.",
                )

            payment = await self.sale_payment_repository.create_payment(
                payload,
                session=db,
            )

            new_remaining = remaining - amount
            await self.sale_repository.update_sale(
                sale.id,
                {"remaining_balance": new_remaining},
                session=db,
            )

            await self.customer_repository.decrease_balance(
                sale.customer_id,
                amount,
                session=db,
            )

            if new_remaining == 0:
                canceled = await self.status_repository.get_by_name(
                    "venta cancelada",
                    session=db,
                )
                if canceled:
                    await self.sale_repository.update_sale(
                        sale.id,
                        {"status_id": canceled.id},
                        session=db,
                    )

            await self.bank_repository.increase_balance(
                payload.bank_id,
                amount,
                session=db,
            )

            try:
                tx_type_id = await self.transaction_service.type_repo.get_id_by_name(
                    "Pago venta",
                    session=db,
                )
            except Exception:
                tx_type_id = None

            await self.transaction_service.insert_transaction(
                TransactionCreate(
                    bank_id=payload.bank_id,
                    amount=amount,
                    type_id=tx_type_id,
                    description=f"{payment.id} Abono venta {payload.sale_id}",
                ),
                db=db,
            )

            dto = SalePaymentDTO(
                id=payment.id,
                sale_id=payment.sale_id,
                bank_id=payment.bank_id,
                amount=payment.amount,
                created_at=getattr(payment, "created_at", datetime.now()),
            )
            return dto, sale.id

        if not db.in_transaction():
            await db.begin()

        try:
            dto, sale_id = await _run()
            await db.commit()
        except Exception:
            await db.rollback()
            raise

        if channel_id:
            try:

                await publish_realtime_event(
                    channel_id=channel_id,
                    resource="sale_payment",
                    action="created",
                    payload={"id": dto.id, "sale_id": dto.sale_id},
                )

                await publish_realtime_event(
                    channel_id=channel_id,
                    resource="sale",
                    action="updated",
                    payload={"id": sale_id},
                )
                logger.info(
                    "[SaleService] Realtime sale payment created events published: payment_id=%s sale_id=%s",
                    dto.id,
                    sale_id,
                )
            except Exception as e:
                logger.error(
                    "[SaleService] realtime publish failed: %s",
                    e,
                    exc_info=True,
                )

        return dto
    
    async def delete_sale_payment(
        self,
        payment_id: int,
        db: AsyncSession,
        channel_id: Optional[str] = None,
    ) -> bool:
        """
        Delete a sale payment, restore balances, and emit realtime events.

        Operations:
        - Ensure the payment exists.
        - Ensure the associated sale exists.
        - If the sale was marked as fully paid ("venta cancelada"),
          revert it back to credit ("venta credito") when applicable.
        - Recalculate and update the sale remaining balance by adding the payment amount.
        - Decrease the bank balance by the payment amount.
        - Increase the customer credit balance by the same amount.
        - Delete the payment record.
        - Delete the associated transaction record.
        - Optionally emit realtime events for payment deletion and sale update.

        Args:
            payment_id: Identifier of the payment to delete.
            db: Active async database session.
            channel_id: Optional realtime channel to publish events to.

        Returns:
            True if the payment was found and deleted, False if no payment existed.

        Raises:
            HTTPException: If the associated sale does not exist.
            Exception: Propagated if database operations fail (after rollback).
        """
        async def _run() -> tuple[bool, Optional[int]]:
            payment = await self.sale_payment_repository.get_by_id(
                payment_id,
                session=db,
            )
            if not payment:
                return False, None

            sale = await self.sale_repository.get_by_id(
                payment.sale_id,
                session=db,
            )
            if not sale:
                raise HTTPException(
                    status_code=404,
                    detail="Associated sale not found",
                )

            current_status = await self.status_repository.get_by_id(
                sale.status_id,
                session=db,
            )
            if current_status and (current_status.name or "").lower() == "venta cancelada":
                credit_status = await self.status_repository.get_by_name(
                    "venta credito",
                    session=db,
                )
                if credit_status:
                    await self.sale_repository.update_sale(
                        sale.id,
                        {"status_id": credit_status.id},
                        session=db,
                    )

            amount = float(payment.amount or 0.0)
            new_remaining = float(sale.remaining_balance or 0.0) + amount

            await self.sale_repository.update_sale(
                sale.id,
                {"remaining_balance": new_remaining},
                session=db,
            )

            await self.bank_repository.decrease_balance(
                payment.bank_id,
                amount,
                session=db,
            )

            await self.customer_repository.increase_balance(
                sale.customer_id,
                amount,
                session=db,
            )

            await self.sale_payment_repository.delete_payment(
                payment_id,
                session=db,
            )

            await self.transaction_service.delete_sale_payment_transaction(
                payment_id,
                payment.sale_id,
                db=db,
            )

            return True, sale.id

        if not db.in_transaction():
            await db.begin()

        try:
            success, sale_id = await _run()
            await db.commit()
        except Exception:
            await db.rollback()
            raise

        if not success:
            return False

        if channel_id and sale_id is not None:
            try:
                await publish_realtime_event(
                    channel_id=channel_id,
                    resource="sale_payment",
                    action="deleted",
                    payload={"id": payment_id, "sale_id": sale_id},
                )
                await publish_realtime_event(
                    channel_id=channel_id,
                    resource="sale",
                    action="updated",
                    payload={"id": sale_id},
                )
                logger.info(
                    "[SaleService] Realtime sale payment deleted events published: payment_id=%s sale_id=%s",
                    payment_id,
                    sale_id,
                )
            except Exception as e:
                logger.error(
                    "[SaleService] realtime publish failed: %s",
                    e,
                    exc_info=True,
                )

        return True
    
    async def list_sale_payments(
    self,
    sale_id: int,
    db: AsyncSession
    ) -> List[SalePaymentViewDTO]:
        """
        List all payments made for a sale with resolved bank names and remaining balance.

        Builds a view-friendly representation of each payment, including:
        - Bank name (cached per bank_id).
        - Remaining balance for the sale.
        - Amount paid.
        - Created at timestamp.

        Args:
            sale_id: Identifier of the sale whose payments will be listed.
            db: Active async database session.

        Returns:
            List of SalePaymentViewDTO for all payments of the given sale.
            Returns an empty list if no payments exist.
        """
        payments = await self.sale_payment_repository.list_by_sale(sale_id, session=db)
        if not payments:
            return []

        sale = await self.sale_repository.get_by_id(sale_id, session=db)
        remaining_balance = float(getattr(sale, "remaining_balance", 0.0) or 0.0)

        bank_name_cache: dict[int, str] = {}
        result: List[SalePaymentViewDTO] = []

        for p in payments:
            if p.bank_id not in bank_name_cache:
                bank = await self.bank_repository.get_by_id(p.bank_id, session=db)
                bank_name_cache[p.bank_id] = bank.name if bank else "Desconocido"

            result.append(
                SalePaymentViewDTO(
                    id=p.id,
                    sale_id=p.sale_id,
                    bank=bank_name_cache[p.bank_id],
                    remaining_balance=remaining_balance,
                    amount_paid=float(p.amount or 0.0),
                    created_at=p.created_at,
                )
            )

        return result