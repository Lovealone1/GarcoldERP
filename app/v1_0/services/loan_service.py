from math import ceil
from typing import List, Optional
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import logger
from app.core.realtime import publish_realtime_event
from app.v1_0.entities import LoanDTO, LoanPageDTO
from app.v1_0.repositories import (
    LoanRepository,
    BankRepository,
    TransactionTypeRepository,
)
from app.v1_0.schemas import (
    LoanCreate,
    LoanApplyPaymentIn,
    TransactionCreate,
)
from .transaction_service import TransactionService


class LoanService:
    def __init__(
        self,
        loan_repository: LoanRepository,
        bank_repository: BankRepository,
        transaction_service: TransactionService,
        transaction_type_repository: TransactionTypeRepository,
    ) -> None:
        self.loan_repository = loan_repository
        self.bank_repository = bank_repository
        self.transaction_service = transaction_service
        self.transaction_type_repository = transaction_type_repository
        self.PAGE_SIZE = 10

    async def _require(
        self,
        loan_id: int,
        db: AsyncSession,
    ):
        """
        Ensure that a loan exists; otherwise raise 404.

        Args:
            loan_id: Loan identifier to fetch.
            db: Active async database session.

        Returns:
            ORM loan entity.

        Raises:
            HTTPException: With 404 status if the loan does not exist.
        """
        loan = await self.loan_repository.get_by_id(loan_id, db)
        if not loan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Loan not found.",
            )
        return loan

    async def create(
        self,
        payload: LoanCreate,
        db: AsyncSession,
        channel_id: Optional[str] = None,
    ) -> LoanDTO:
        """
        Create a new loan record.

        Args:
            payload: LoanCreate data with name, amount, and metadata.
            db: Active async database session.
            channel_id: Optional realtime channel to publish "loan:created".

        Returns:
            LoanDTO for the created loan.

        Raises:
            HTTPException: With 500 status if persistence fails.
        """
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

    async def get(
        self,
        loan_id: int,
        db: AsyncSession,
    ) -> LoanDTO:
        """
        Retrieve a single loan by ID.

        Args:
            loan_id: Loan identifier.
            db: Active async database session.

        Returns:
            LoanDTO with the loan data.

        Raises:
            HTTPException:
                404 if loan does not exist.
                500 on unexpected errors.
        """
        logger.debug(
            "[LoanService] Get loan ID=%s",
            loan_id,
        )
        try:
            async with db.begin():
                l = await self._require(loan_id, db)
            return LoanDTO(
                id=l.id,
                name=l.name,
                amount=l.amount,
                created_at=l.created_at,
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(
                "[LoanService] Get failed ID=%s: %s",
                loan_id,
                e,
                exc_info=True,
            )
            raise HTTPException(
                status_code=500,
                detail="Failed to fetch loan",
            )

    async def list_all(
        self,
        db: AsyncSession,
    ) -> List[LoanDTO]:
        """
        List all loans without pagination.

        Args:
            db: Active async database session.

        Returns:
            List of LoanDTO.
        """
        logger.debug("[LoanService] List all loans")
        try:
            async with db.begin():
                rows = await self.loan_repository.list_all(db)
            return [
                LoanDTO(
                    id=l.id,
                    name=l.name,
                    amount=l.amount,
                    created_at=l.created_at,
                )
                for l in rows
            ]
        except Exception as e:
            logger.error(
                "[LoanService] List failed: %s",
                e,
                exc_info=True,
            )
            raise HTTPException(
                status_code=500,
                detail="Failed to list loans",
            )

    async def list_paginated(
        self,
        page: int,
        db: AsyncSession,
    ) -> LoanPageDTO:
        """
        List loans in a paginated format.

        Args:
            page: 1-based page number.
            db: Active async database session.

        Returns:
            LoanPageDTO with items and pagination metadata.
        """
        offset = max(page - 1, 0) * self.PAGE_SIZE
        async with db.begin():
            items, total = await self.loan_repository.list_paginated(
                offset=offset,
                limit=self.PAGE_SIZE,
                session=db,
            )

        items_dto = [
            LoanDTO(
                id=l.id,
                name=l.name,
                amount=l.amount,
                created_at=l.created_at,
            )
            for l in items
        ]
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
        """
        Set a loan amount to a specific non-negative value.

        Note:
        This method does not handle any external side effects beyond the loan itself.

        Args:
            loan_id: Loan identifier.
            new_amount: New amount value (must be >= 0).
            db: Active async database session.
            channel_id: Optional realtime channel for "loan:updated".

        Returns:
            Updated LoanDTO.

        Raises:
            HTTPException:
                400 if new_amount < 0.
                404 if loan not found.
                500 if update fails.
        """
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
        """
        Delete a loan by ID.

        Note:
        This method does not revert any prior financial flows linked to the loan.

        Args:
            loan_id: Loan identifier.
            db: Active async database session.
            channel_id: Optional realtime channel for "loan:deleted".

        Returns:
            True if the loan was deleted.

        Raises:
            HTTPException:
                404 if the loan does not exist.
                500 on failure.
        """
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
        """
        Apply a payment to a loan and record the corresponding bank transaction.

        Flow:
        - Validate amount > 0.
        - Decrease the specified bank balance by amount.
        - Apply payment to the loan via repository (which may fully settle and delete).
        - Create an automatic "Retiro" transaction describing the payment.
        - Emit realtime events for updated or deleted loan.

        Args:
            payload: LoanApplyPaymentIn with loan_id, bank_id, amount, and optional description.
            db: Active async database session.
            channel_id: Optional realtime channel for "loan:updated" or "loan:deleted".

        Returns:
            Updated LoanDTO if the loan remains active.
            None if the loan is fully paid and removed.

        Raises:
            HTTPException:
                400 for invalid amounts or business rule violations.
                404 if loan cannot be resolved.
                500 if processing fails.
        """
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
