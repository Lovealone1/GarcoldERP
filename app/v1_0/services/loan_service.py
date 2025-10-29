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

    async def create(self, payload: LoanCreate, db: AsyncSession) -> LoanDTO:
        logger.info(f"[LoanService] Creating loan: {payload.model_dump()}")
        try:
            async with db.begin():
                l = await self.loan_repository.create_loan(payload, db)
            logger.info(f"[LoanService] Loan created ID={l.id}")
            return LoanDTO(
                id=l.id, 
                name=l.name, 
                amount=l.amount, 
                created_at=l.created_at
                )
        except Exception as e:
            logger.error(f"[LoanService] Create failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to create loan")

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

    async def update_amount(self, loan_id: int, new_amount: float, db: AsyncSession) -> LoanDTO:
        logger.info(f"[LoanService] Update amount ID={loan_id} -> {new_amount}")
        try:
            if new_amount < 0:
                raise HTTPException(status_code=400, detail="Amount must be >= 0.")
            async with db.begin():
                l = await self.loan_repository.update_amount(loan_id, new_amount, db)
            if not l:
                raise HTTPException(status_code=404, detail="Loan not found.")
            return LoanDTO(
                id=l.id, 
                name=l.name, 
                amount=l.amount, 
                created_at=l.created_at
                )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"[LoanService] Update amount failed ID={loan_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to update loan amount")

    async def delete(self, loan_id: int, db: AsyncSession) -> bool:
        logger.warning(f"[LoanService] Delete loan ID={loan_id}")
        try:
            async with db.begin():
                ok = await self.loan_repository.delete_loan(loan_id, db)
            if not ok:
                raise HTTPException(status_code=404, detail="Loan not found.")
            return True
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"[LoanService] Delete failed ID={loan_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to delete loan")

    async def apply_payment(self, payload: LoanApplyPaymentIn, db: AsyncSession) -> Optional[LoanDTO]:
        logger.info(f"[LoanService] Apply payment loan_id={payload.loan_id} amount={payload.amount} bank_id={payload.bank_id}")
        try:
            if payload.amount <= 0:
                raise HTTPException(status_code=400, detail="Amount must be > 0.")
            async with db.begin():
                await self.bank_repository.decrease_balance(payload.bank_id, payload.amount, db)
                loan_after, deleted = await self.loan_repository.apply_payment(payload.loan_id, payload.amount, db)

                t = await self.transaction_type_repository.get_by_name("Retiro", session=db)
                type_id = t.id if t else None
                tx = TransactionCreate(
                    bank_id=payload.bank_id,
                    amount=payload.amount,  
                    type_id=type_id,
                    description=payload.description or f"Pago crédito {payload.loan_id}",
                    is_auto=True,
                    created_at=datetime.now(),
                )
                await self.transaction_service.insert_transaction(tx, db)

            if deleted:
                return None
            if not loan_after:
                raise HTTPException(status_code=404, detail="Loan not found.")
            return LoanDTO(
                id=loan_after.id,
                name=loan_after.name,
                amount=loan_after.amount,
                created_at=loan_after.created_at,
            )
        except HTTPException:
            raise
        except ValueError as e:
            msg = str(e)
            if msg == "amount_must_be_positive":
                raise HTTPException(status_code=400, detail="Amount must be > 0.")
            if msg == "insufficient_amount_or_not_found":
                raise HTTPException(status_code=400, detail="Insufficient amount or loan not found.")
            raise HTTPException(status_code=400, detail=msg)
        except Exception as e:
            logger.error(f"[LoanService] Apply payment failed loan_id={payload.loan_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to apply payment")