from math import ceil
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.core.logger import logger
from app.v1_0.repositories import (
    ExpenseRepository,
    BankRepository,
    ExpenseCategoryRepository,
)
from app.v1_0.services import TransactionService
from app.v1_0.schemas import ExpenseCreate, TransactionCreate
from app.v1_0.entities import ExpenseDTO, ExpensePageDTO, ExpenseViewDTO

class ExpenseService:
    def __init__(
        self,
        expense_repository: ExpenseRepository,
        bank_repository: BankRepository,
        expense_category_repository: ExpenseCategoryRepository,
        transaction_service: TransactionService
    ) -> None:
        self.expense_repo = expense_repository
        self.bank_repo = bank_repository
        self.category_repo = expense_category_repository
        self.tx_service = transaction_service
        self.PAGE_SIZE = 8

    async def _require(self, expense_id: int, db: AsyncSession):
        e = await self.expense_repo.get_by_id(expense_id, session=db)
        if not e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found.")
        return e

    async def create(self, payload: ExpenseCreate, db: AsyncSession) -> ExpenseDTO:
        logger.info(f"[ExpenseService] Creating expense: {payload.model_dump()}")
        try:
            async with db.begin():
                bank = await self.bank_repo.get_by_id(payload.bank_id, session=db)
                if not bank:
                    raise HTTPException(status_code=404, detail="Bank not found.")
                cat = await self.category_repo.get_by_id(payload.expense_category_id, session=db)
                if not cat:
                    raise HTTPException(status_code=404, detail="Expense category not found.")
                if payload.amount <= 0:
                    raise HTTPException(status_code=400, detail="Amount must be greater than zero.")
                if (bank.balance or 0) < payload.amount:
                    raise HTTPException(status_code=400, detail="Insufficient bank balance.")

                expense_type_id = await self.tx_service.type_repo.get_id_by_name("Gasto", session=db)
                if expense_type_id is None:
                    raise HTTPException(status_code=500, detail="Transaction type 'Gasto' not found.")

                await self.bank_repo.decrease_balance(payload.bank_id, payload.amount, session=db)
                exp = await self.expense_repo.create_expense(payload, session=db)

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

            logger.info(f"[ExpenseService] Expense created ID={exp.id}")
            return ExpenseDTO(
                id=exp.id,
                expense_category_id=exp.expense_category_id,
                amount=exp.amount,
                bank_id=exp.bank_id,
                expense_date=exp.expense_date,
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"[ExpenseService] Create failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to create expense")
    
    async def delete(self, expense_id: int, db: AsyncSession) -> bool:
        """Delete an expense, restore bank balance, and remove its transactions."""
        async with db.begin():
            exp = await self.expense_repo.get_by_id(expense_id, session=db)
            if not exp:
                return False

            bank = await self.bank_repo.get_by_id(exp.bank_id, session=db)
            if not bank:
                raise HTTPException(status_code=404, detail="Linked bank not found.")

            await self.bank_repo.increase_balance(exp.bank_id, float(exp.amount or 0), session=db)

            deleted = await self.expense_repo.delete_expense(expense_id, session=db)

            try:
                await self.tx_service.delete_expense_transactions(expense_id, db=db)
            except Exception:
                pass

            return deleted

    async def list_paginated(self, page: int, db: AsyncSession) -> ExpensePageDTO:
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