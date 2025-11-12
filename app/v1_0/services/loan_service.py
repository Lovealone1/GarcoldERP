from typing import List, Optional
from datetime import datetime
from math import ceil
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import logger
from app.v1_0.repositories import LoanRepository, BankRepository, TransactionTypeRepository
from .transaction_service import TransactionService
from app.v1_0.schemas import LoanCreate, LoanApplyPaymentIn, TransactionCreate
from app.v1_0.entities import LoanDTO, LoanPageDTO
from app.core.realtime import publish_realtime_event

class LoanService:
    def __init__(self, 
        loan_repository: LoanRepository, 
        bank_repository: BankRepository,
        transaction_service: TransactionService,
        transaction_type_repository: TransactionTypeRepository) -> None:
        self.loan_repository = loan_repository
        self.bank_repository = bank_repository
        self.transaction_service = transaction_service
        self.transaction_type_repository = transaction_type_repository
        self.PAGE_SIZE = 10

    async def _require(self, loan_id: int, db: AsyncSession):
        loan = await self.loan_repository.get_by_id(loan_id, db)
        if not loan:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loan not found.")
        return loan

    async def create(
        self,
        payload: LoanCreate,
        db: AsyncSession,
        channel_id: Optional[str] = None,
    ) -> LoanDTO:
        logger.info(
            "[LoanService] Creating loan: %s",
            payload.model_dump(),
        )

        async def _run() -> LoanDTO:
            l = await self.loan_repository.create_loan(payload, db)
            logger.info(
                "[LoanService] Loan created ID=%s",
                l.id,
            )
            return LoanDTO(
                id=l.id,
                name=l.name,
                amount=l.amount,
                created_at=l.created_at,
            )

        if not db.in_transaction():
            await db.begin()
        try:
            dto = await _run()
            await db.commit()
        except Exception as e:
            await db.rollback()
            logger.error(
                "[LoanService] Create failed: %s",
                e,
                exc_info=True,
            )
            raise HTTPException(
                status_code=500,
                detail="Failed to create loan",
            )

        if channel_id:
            try:
                await publish_realtime_event(
                    channel_id=channel_id,
                    resource="loan",
                    action="created",
                    payload={"id": dto.id},
                )
            except Exception as e:
                logger.error(
                    "[LoanService] RT publish failed (create): %s",
                    e,
                    exc_info=True,
                )

        return dto

    async def get(self, loan_id: int, db: AsyncSession) -> LoanDTO:
        logger.debug(f"[LoanService] Get loan ID={loan_id}")
        try:
            async with db.begin():
                l = await self._require(loan_id, db)
            return LoanDTO(
                id=l.id, 
                name=l.name, 
                amount=l.amount, 
                created_at=l.created_at
                )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"[LoanService] Get failed ID={loan_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to fetch loan")

    async def list_all(self, db: AsyncSession) -> List[LoanDTO]:
        logger.debug("[LoanService] List all loans")
        try:
            async with db.begin():
                rows = await self.loan_repository.list_all(db)
            return [LoanDTO(
                id=l.id, 
                name=l.name, 
                amount=l.amount, 
                created_at=l.created_at) 
                    for l in rows]
        except Exception as e:
            logger.error(f"[LoanService] List failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to list loans")

    async def list_paginated(self, page: int, db: AsyncSession) -> LoanPageDTO:
        offset = max(page - 1, 0) * self.PAGE_SIZE
        async with db.begin():
            items, total = await self.loan_repository.list_paginated(
                offset=offset, limit=self.PAGE_SIZE, session=db
            )

        items_dto = [LoanDTO(
            id=l.id, 
            name=l.name, 
            amount=l.amount, 
            created_at=l.created_at) 
                for l in items]
        total = int(total or 0)
        total_pages = max(1, ceil(total / self.PAGE_SIZE)) if total else 1

        return LoanPageDTO(
            items=items_dto,
            page=page,
            page_size=self.PAGE_SIZE,
            total=total,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1,
        )

    async def update_amount(
        self,
        loan_id: int,
        new_amount: float,
        db: AsyncSession,
        channel_id: Optional[str] = None,
    ) -> LoanDTO:
        logger.info(
            "[LoanService] Update amount ID=%s -> %s",
            loan_id,
            new_amount,
        )

        if new_amount < 0:
            raise HTTPException(
                status_code=400,
                detail="Amount must be >= 0.",
            )

        async def _run() -> LoanDTO:
            l = await self.loan_repository.update_amount(
                loan_id,
                new_amount,
                db,
            )
            if not l:
                raise HTTPException(
                    status_code=404,
                    detail="Loan not found.",
                )
            return LoanDTO(
                id=l.id,
                name=l.name,
                amount=l.amount,
                created_at=l.created_at,
            )

        if not db.in_transaction():
            await db.begin()
        try:
            dto = await _run()
            await db.commit()
        except HTTPException:
            await db.rollback()
            raise
        except Exception as e:
            await db.rollback()
            logger.error(
                "[LoanService] Update amount failed ID=%s: %s",
                loan_id,
                e,
                exc_info=True,
            )
            raise HTTPException(
                status_code=500,
                detail="Failed to update loan amount",
            )

        if channel_id:
            try:
                await publish_realtime_event(
                    channel_id=channel_id,
                    resource="loan",
                    action="updated",
                    payload={"id": dto.id},
                )
            except Exception as e:
                logger.error(
                    "[LoanService] RT publish failed (update_amount): %s",
                    e,
                    exc_info=True,
                )

        return dto

    async def delete(
        self,
        loan_id: int,
        db: AsyncSession,
        channel_id: Optional[str] = None,
    ) -> bool:
        logger.warning(
            "[LoanService] Delete loan ID=%s",
            loan_id,
        )

        async def _run() -> bool:
            ok = await self.loan_repository.delete_loan(
                loan_id,
                db,
            )
            if not ok:
                raise HTTPException(
                    status_code=404,
                    detail="Loan not found.",
                )
            return True

        if not db.in_transaction():
            await db.begin()
        try:
            ok = await _run()
            await db.commit()
        except HTTPException:
            await db.rollback()
            raise
        except Exception as e:
            await db.rollback()
            logger.error(
                "[LoanService] Delete failed ID=%s: %s",
                loan_id,
                e,
                exc_info=True,
            )
            raise HTTPException(
                status_code=500,
                detail="Failed to delete loan",
            )

        if channel_id:
            try:
                await publish_realtime_event(
                    channel_id=channel_id,
                    resource="loan",
                    action="deleted",
                    payload={"id": loan_id},
                )
            except Exception as e:
                logger.error(
                    "[LoanService] RT publish failed (delete): %s",
                    e,
                    exc_info=True,
                )

        return True

    async def apply_payment(
        self,
        payload: LoanApplyPaymentIn,
        db: AsyncSession,
        channel_id: Optional[str] = None,
    ) -> Optional[LoanDTO]:
        logger.info(
            "[LoanService] Apply payment loan_id=%s amount=%s bank_id=%s",
            payload.loan_id,
            payload.amount,
            payload.bank_id,
        )

        amount = float(payload.amount or 0.0)
        if amount <= 0:
            raise HTTPException(
                status_code=400,
                detail="Amount must be > 0.",
            )

        async def _run() -> tuple[Optional[LoanDTO], bool]:
            await self.bank_repository.decrease_balance(
                payload.bank_id,
                amount,
                db,
            )

            loan_after, deleted = await self.loan_repository.apply_payment(
                payload.loan_id,
                amount,
                db,
            )

            t = await self.transaction_type_repository.get_by_name(
                "Retiro",
                session=db,
            )
            type_id = t.id if t else None
            tx = TransactionCreate(
                bank_id=payload.bank_id,
                amount=amount,
                type_id=type_id,
                description=payload.description
                or f"Pago crédito {payload.loan_id}",
                is_auto=True,
                created_at=datetime.now(),
            )
            await self.transaction_service.insert_transaction(tx, db)

            if deleted:
                return None, True

            if not loan_after:
                raise HTTPException(
                    status_code=404,
                    detail="Loan not found.",
                )

            dto = LoanDTO(
                id=loan_after.id,
                name=loan_after.name,
                amount=loan_after.amount,
                created_at=loan_after.created_at,
            )
            return dto, False

        if not db.in_transaction():
            await db.begin()
        try:
            dto, deleted = await _run()
            await db.commit()
        except HTTPException as e:
            await db.rollback()
            # mappeo de ValueError ya lo hacías arriba, aquí no lo necesitas
            raise e
        except ValueError as e:
            await db.rollback()
            msg = str(e)
            if msg == "amount_must_be_positive":
                raise HTTPException(
                    status_code=400,
                    detail="Amount must be > 0.",
                )
            if msg == "insufficient_amount_or_not_found":
                raise HTTPException(
                    status_code=400,
                    detail="Insufficient amount or loan not found.",
                )
            raise HTTPException(
                status_code=400,
                detail=msg,
            )
        except Exception as e:
            await db.rollback()
            logger.error(
                "[LoanService] Apply payment failed loan_id=%s: %s",
                payload.loan_id,
                e,
                exc_info=True,
            )
            raise HTTPException(
                status_code=500,
                detail="Failed to apply payment",
            )

        if channel_id:
            try:
                if deleted:
                    await publish_realtime_event(
                        channel_id=channel_id,
                        resource="loan",
                        action="deleted",
                        payload={"id": payload.loan_id},
                    )
                else:
                    await publish_realtime_event(
                        channel_id=channel_id,
                        resource="loan",
                        action="updated",
                        payload={"id": dto.id},  # type: ignore[arg-type]
                    )
            except Exception as e:
                logger.error(
                    "[LoanService] RT publish failed (apply_payment): %s",
                    e,
                    exc_info=True,
                )

        return dto