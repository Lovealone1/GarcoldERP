from datetime import datetime
from typing import List
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import logger
from app.v1_0.schemas import PurchasePaymentCreate, TransactionCreate
from app.v1_0.entities import PurchasePaymentDTO, PurchasePaymentViewDTO
from app.v1_0.repositories import (
    PurchaseRepository,
    StatusRepository,
    PurchasePaymentRepository,
    BankRepository,
)
from app.v1_0.services.transaction_service import TransactionService


class PurchasePaymentService:
    """
    Service to manage payments for credit purchases.
    Mirrors SalePaymentService behavior, but money flows out of the bank.
    """

    def __init__(
        self,
        purchase_repository: PurchaseRepository,
        status_repository: StatusRepository,
        purchase_payment_repository: PurchasePaymentRepository,
        bank_repository: BankRepository,
        transaction_service: TransactionService,
    ) -> None:
        self.purchase_repository = purchase_repository
        self.status_repository = status_repository
        self.purchase_payment_repository = purchase_payment_repository
        self.bank_repository = bank_repository
        self.transaction_service = transaction_service

    async def create_purchase_payment(
        self, payload: PurchasePaymentCreate, db: AsyncSession
    ) -> PurchasePaymentDTO:
        """
        Register a payment for a credit purchase.
        - Decreases purchase balance.
        - Decreases bank balance.
        - If balance reaches 0, set status to 'compra cancelada'.
        - Creates a bank transaction with Spanish description.
        """
        async with db.begin():
            purchase = await self.purchase_repository.get_by_id(payload.purchase_id, session=db)
            if not purchase:
                raise HTTPException(status_code=404, detail="Purchase not found.")

            status_row = await self.status_repository.get_by_id(purchase.status_id, session=db)
            if not status_row or (status_row.name or "").lower() != "compra credito":
                raise HTTPException(status_code=400, detail="Only credit purchases can receive payments.")

            remaining = float(purchase.balance or 0.0)
            amount = float(payload.amount or 0.0)
            if remaining <= 0:
                raise HTTPException(status_code=400, detail="Purchase has no pending balance.")
            if amount <= 0 or amount > remaining:
                raise HTTPException(status_code=400, detail="Invalid amount or exceeds pending balance.")

            bank = await self.bank_repository.get_by_id(payload.bank_id, session=db)
            if not bank:
                raise HTTPException(status_code=404, detail="Bank not found.")
            if float(bank.balance or 0.0) < amount:
                raise HTTPException(status_code=400, detail="Insufficient bank balance.")

            payment = await self.purchase_payment_repository.create_payment(payload, session=db)

            new_balance = remaining - amount
            await self.purchase_repository.update_purchase(
                purchase.id, {"balance": new_balance}, session=db
            )

            if new_balance == 0:
                canceled = await self.status_repository.get_by_name("compra cancelada", session=db)
                if canceled:
                    await self.purchase_repository.update_purchase(
                        purchase.id, {"status_id": canceled.id}, session=db
                    )

            await self.bank_repository.decrease_balance(payload.bank_id, amount, session=db)

            try:
                tx_type_id = await self.transaction_service.type_repo.get_id_by_name(
                    "Pago compra", session=db
                )
            except Exception as e:
                logger.warning("[PurchasePaymentService] get_id_by_name failed: %s", e, exc_info=True)
                tx_type_id = None

            await self.transaction_service.insert_transaction(
                TransactionCreate(
                    bank_id=payload.bank_id,
                    amount=amount,
                    type_id=tx_type_id,
                    description=f"{payment.id} Abono compra {payload.purchase_id}",
                ),
                db=db,
            )

        return PurchasePaymentDTO(
            id=payment.id,
            purchase_id=payment.purchase_id,
            bank_id=payment.bank_id,
            amount=payment.amount,
            created_at=getattr(payment, "created_at", datetime.now()),
        )

    async def delete_purchase_payment(
        self, payment_id: int, db: AsyncSession
    ) -> bool:
        """
        Delete a purchase payment and restore balances.

        - If purchase was marked 'compra cancelada', switch it back to 'compra credito'.
        - Restore purchase.balance by the payment amount.
        - Increase the bank balance by the payment amount.
        - Remove related bank transaction(s) for this payment.
        """
        async with db.begin():
            payment = await self.purchase_payment_repository.get_by_id(payment_id, session=db)
            if not payment:
                return False

            purchase = await self.purchase_repository.get_by_id(payment.purchase_id, session=db)
            if not purchase:
                raise HTTPException(status_code=404, detail="Associated purchase not found")

            current_status = await self.status_repository.get_by_id(purchase.status_id, session=db)
            if current_status and (current_status.name or "").lower() == "compra cancelada":
                credit_status = await self.status_repository.get_by_name("compra credito", session=db)
                if credit_status:
                    await self.purchase_repository.update_purchase(
                        purchase.id, {"status_id": credit_status.id}, session=db
                    )

            amount = float(payment.amount or 0.0)
            new_balance = float(purchase.balance or 0.0) + amount
            await self.purchase_repository.update_purchase(
                purchase.id, {"balance": new_balance}, session=db
            )

            await self.bank_repository.increase_balance(payment.bank_id, amount, session=db)

            await self.purchase_payment_repository.delete_payment(payment_id, session=db)

            await self.transaction_service.delete_purchase_payment_transaction(
                payment_id, payment.purchase_id, db=db
            )

        return True

    async def list_purchase_payments(
        self, purchase_id: int, db: AsyncSession
    ) -> List[PurchasePaymentViewDTO]:
        """
        Return all payments made for a purchase as view DTOs.
        """
        payments = await self.purchase_payment_repository.list_by_purchase(purchase_id, session=db)
        if not payments:
            return []

        purchase = await self.purchase_repository.get_by_id(purchase_id, session=db)
        remaining_balance = float(getattr(purchase, "balance", 0.0) or 0.0)

        bank_name_cache: dict[int, str] = {}
        result: List[PurchasePaymentViewDTO] = []

        for p in payments:
            if p.bank_id not in bank_name_cache:
                bank = await self.bank_repository.get_by_id(p.bank_id, session=db)
                bank_name_cache[p.bank_id] = bank.name if bank else "Desconocido"

            result.append(
                PurchasePaymentViewDTO(
                    id=p.id,
                    purchase_id=p.purchase_id,
                    bank=bank_name_cache[p.bank_id],
                    remaining_balance=remaining_balance,
                    amount_paid=float(p.amount or 0.0),
                    created_at=p.created_at,
                )
            )

        return result
