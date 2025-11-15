from math import ceil
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import logger
from app.core.realtime import publish_realtime_event
from app.v1_0.entities import ExpenseDTO, ExpensePageDTO, ExpenseViewDTO
from app.v1_0.repositories import (
    ExpenseRepository,
    BankRepository,
    ExpenseCategoryRepository,
)
from app.v1_0.schemas import ExpenseCreate, TransactionCreate
from app.v1_0.services import TransactionService


class ExpenseService:
    def __init__(
        self,
        expense_repository: ExpenseRepository,
        bank_repository: BankRepository,
        expense_category_repository: ExpenseCategoryRepository,
        transaction_service: TransactionService,
    ) -> None:
        self.expense_repo = expense_repository
        self.bank_repo = bank_repository
        self.category_repo = expense_category_repository
        self.tx_service = transaction_service
        self.PAGE_SIZE = 8

    async def _require(
        self,
        expense_id: int,
        db: AsyncSession,
    ):
        """
        Ensure an expense exists or raise an HTTP 404 error.

        Args:
            expense_id: Identifier of the expense to fetch.
            db: Active async database session.

        Returns:
            ORM expense entity if found.

        Raises:
            HTTPException: If the expense does not exist.
        """
        e = await self.expense_repo.get_by_id(expense_id, session=db)
        if not e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Expense not found.",
            )
        return e

    async def create(
        self,
        payload: ExpenseCreate,
        db: AsyncSession,
        channel_id: Optional[str] = None,
    ) -> ExpenseDTO:
        """
        Create a new expense, update bank balance, and register its transaction.

        Operations:
        - Validate bank and expense category existence.
        - Validate positive amount and sufficient bank balance.
        - Resolve transaction type "Gasto".
        - Decrease bank balance by expense amount.
        - Create expense record.
        - Insert corresponding automatic transaction.
        - Optionally emit a realtime "expense:created" event.

        Args:
            payload: ExpenseCreate data with expense fields.
            db: Active async database session.
            channel_id: Optional realtime channel identifier for event publishing.

        Returns:
            ExpenseDTO representing the created expense.

        Raises:
            HTTPException:
                - 400 for invalid amount or insufficient balance.
                - 404 for missing bank or category.
                - 500 if transaction type is missing or creation fails.
        """
        logger.info(
            "[ExpenseService] Creating expense: %s",
            payload.model_dump(),
        )

        async def _run() -> ExpenseDTO:
            bank = await self.bank_repo.get_by_id(
                payload.bank_id,
                session=db,
            )
            if not bank:
                raise HTTPException(
                    status_code=404,
                    detail="Bank not found.",
                )

            cat = await self.category_repo.get_by_id(
                payload.expense_category_id,
                session=db,
            )
            if not cat:
                raise HTTPException(
                    status_code=404,
                    detail="Expense category not found.",
                )

            if payload.amount <= 0:
                raise HTTPException(
                    status_code=400,
                    detail="Amount must be greater than zero.",
                )

            if float(bank.balance or 0) < float(payload.amount or 0):
                raise HTTPException(
                    status_code=400,
                    detail="Insufficient bank balance.",
                )

            expense_type_id = await self.tx_service.type_repo.get_id_by_name(
                "Gasto",
                session=db,
            )
            if expense_type_id is None:
                raise HTTPException(
                    status_code=500,
                    detail="Transaction type 'Gasto' not found.",
                )

            await self.bank_repo.decrease_balance(
                payload.bank_id,
                payload.amount,
                session=db,
            )

            exp = await self.expense_repo.create_expense(
                payload,
                session=db,
            )

            desc = f"Gasto {cat.name} {exp.id}"
            await self.tx_service.insert_transaction(
                TransactionCreate(
                    bank_id=payload.bank_id,
                    amount=payload.amount,
                    type_id=expense_type_id,
                    description=desc,
                    is_auto=True,
                ),
                db=db,
            )

            logger.info(
                "[ExpenseService] Expense created ID=%s",
                exp.id,
            )

            return ExpenseDTO(
                id=exp.id,
                expense_category_id=exp.expense_category_id,
                amount=exp.amount,
                bank_id=exp.bank_id,
                expense_date=exp.expense_date,
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
                "[ExpenseService] Create failed: %s",
                e,
                exc_info=True,
            )
            raise HTTPException(
                status_code=500,
                detail="Failed to create expense",
            )

        if channel_id:
            try:
                await publish_realtime_event(
                    channel_id=channel_id,
                    resource="expense",
                    action="created",
                    payload={"id": dto.id},
                )
                logger.info(
                    "[ExpenseService] RT expense created published: id=%s",
                    dto.id,
                )
            except Exception as e:
                logger.error(
                    "[ExpenseService] RT publish failed (create): %s",
                    e,
                    exc_info=True,
                )

        return dto

    async def delete(
        self,
        expense_id: int,
        db: AsyncSession,
        channel_id: Optional[str] = None,
    ) -> bool:
        """
        Delete an expense, restore bank balance, and remove related transactions.

        Operations:
        - If expense does not exist, return False.
        - Validate linked bank exists.
        - Increase bank balance by expense amount.
        - Delete expense record.
        - Attempt to delete associated expense transactions.
        - Optionally emit a realtime "expense:deleted" event.

        Args:
            expense_id: Identifier of the expense to delete.
            db: Active async database session.
            channel_id: Optional realtime channel identifier for event publishing.

        Returns:
            True if the expense existed and was deleted, False if it did not exist.

        Raises:
            HTTPException:
                - 404 if linked bank not found.
                - 500 if delete flow fails.
        """

        async def _run() -> bool:
            exp = await self.expense_repo.get_by_id(
                expense_id,
                session=db,
            )
            if not exp:
                return False

            bank = await self.bank_repo.get_by_id(
                exp.bank_id,
                session=db,
            )
            if not bank:
                raise HTTPException(
                    status_code=404,
                    detail="Linked bank not found.",
                )

            await self.bank_repo.increase_balance(
                exp.bank_id,
                float(exp.amount or 0),
                session=db,
            )

            deleted = await self.expense_repo.delete_expense(
                expense_id,
                session=db,
            )

            try:
                await self.tx_service.delete_expense_transactions(
                    expense_id,
                    db=db,
                )
            except Exception as e:
                logger.warning(
                    "[ExpenseService] delete_expense_transactions failed id=%s: %s",
                    expense_id,
                    e,
                )

            return bool(deleted)

        if not db.in_transaction():
            await db.begin()

        try:
            existed = await _run()
            await db.commit()
        except HTTPException:
            await db.rollback()
            raise
        except Exception as e:
            await db.rollback()
            logger.error(
                "[ExpenseService] Delete failed ID=%s: %s",
                expense_id,
                e,
                exc_info=True,
            )
            raise HTTPException(
                status_code=500,
                detail="Failed to delete expense",
            )

        if not existed:
            return False

        if channel_id:
            try:
                await publish_realtime_event(
                    channel_id=channel_id,
                    resource="expense",
                    action="deleted",
                    payload={"id": expense_id},
                )
                logger.info(
                    "[ExpenseService] RT expense deleted published: id=%s",
                    expense_id,
                )
            except Exception as e:
                logger.error(
                    "[ExpenseService] RT publish failed (delete): %s",
                    e,
                    exc_info=True,
                )

        return True

    async def list_paginated(
        self,
        page: int,
        db: AsyncSession,
    ) -> ExpensePageDTO:
        """
        List expenses in a paginated format with resolved category and bank names.

        For each expense:
        - Includes category name.
        - Includes bank name or a fallback label.
        - Includes normalized amount and expense date.

        Args:
            page: Page number to retrieve (1-based).
            db: Active async database session.

        Returns:
            ExpensePageDTO containing:
                - items: List of ExpenseViewDTO.
                - page: Current page.
                - page_size: Items per page.
                - total: Total number of expenses.
                - total_pages: Total number of pages.
                - has_next: Whether a next page exists.
                - has_prev: Whether a previous page exists.
        """
        page_size = self.PAGE_SIZE
        offset = max(page - 1, 0) * page_size

        async with db.begin():
            items, total, *_ = await self.expense_repo.list_paginated(
                session=db,
                offset=offset,
                limit=page_size,
            )

        view_items: List[ExpenseViewDTO] = [
            ExpenseViewDTO(
                id=e.id,
                category_name=getattr(e.category, "name", ""),
                bank_name=(
                    e.bank.name
                    if getattr(e, "bank", None)
                    else f"Bank {e.bank_id}"
                ),
                amount=float(e.amount or 0.0),
                expense_date=e.expense_date,
            )
            for e in items
        ]

        total = int(total or 0)
        total_pages = max(1, ceil(total / page_size)) if total else 1

        return ExpensePageDTO(
            items=view_items,
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1,
        )
