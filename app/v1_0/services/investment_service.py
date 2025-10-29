from typing import List, Optional
from math import ceil
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from typing import Literal

from app.core.logger import logger
from app.v1_0.repositories import InvestmentRepository, TransactionTypeRepository, BankRepository
from app.v1_0.schemas import InvestmentCreate, TransactionCreate, InvestmentAddBalanceIn, InvestmentWithdrawIn
from app.v1_0.entities import InvestmentDTO, InvestmentPageDTO
from .transaction_service import TransactionService

class InvestmentService:
    def __init__(self, 
        investment_repository: InvestmentRepository,
        transaction_type_repository: TransactionTypeRepository,
        transaction_service: TransactionService,
        bank_repository: BankRepository) -> None:
        self.investment_repository = investment_repository
        self.transaction_type_repository = transaction_type_repository
        self.transaction_service = transaction_service
        self.bank_repository = bank_repository
        self.PAGE_SIZE = 10

    async def _require(self, investment_id: int, db: AsyncSession):
        inv = await self.investment_repository.get_by_id(investment_id, db)
        if not inv:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Investment not found.")
        return inv

    async def create(self, payload: InvestmentCreate, db: AsyncSession) -> InvestmentDTO:
        logger.info("[InvestmentService] Creating investment: %s", payload.model_dump())
        try:
            async with db.begin():
                i = await self.investment_repository.create_investment(payload, db)

                initial = float(payload.balance or 0.0)
                if initial > 0:
                    if not getattr(payload, "bank_id", None):
                        raise HTTPException(
                            status_code=400,
                            detail="bank_id is required when initial balance > 0",
                        )

                    await self.bank_repository.decrease_balance(payload.bank_id, initial, db)

                    t = await self.transaction_type_repository.get_by_name("Aporte Inversion", session=db)
                    type_id = t.id if t else None

                    tx = TransactionCreate(
                        bank_id=payload.bank_id,
                        amount=initial, 
                        type_id=type_id,
                        description=f"Aporte inicial a inversión {i.name}",
                        is_auto=True,
                        created_at=datetime.now(),
                    )
                    await self.transaction_service.insert_transaction(tx, db)

            logger.info("[InvestmentService] Investment created ID=%s", i.id)
            return InvestmentDTO(
                id=i.id,
                name=i.name,
                balance=i.balance,
                maturity_date=i.maturity_date,
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error("[InvestmentService] Create failed: %s", e, exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to create investment")

    async def get(self, investment_id: int, db: AsyncSession) -> InvestmentDTO:
        logger.debug(f"[InvestmentService] Get investment ID={investment_id}")
        try:
            async with db.begin():
                i = await self._require(investment_id, db)
            return InvestmentDTO(
                id=i.id,
                name=i.name,
                balance=i.balance,
                maturity_date=i.maturity_date,
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"[InvestmentService] Get failed ID={investment_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to fetch investment")

    async def list_all(self, db: AsyncSession) -> List[InvestmentDTO]:
        logger.debug("[InvestmentService] List all investments")
        try:
            async with db.begin():
                rows = await self.investment_repository.list_all(db)
            return [
                InvestmentDTO(
                    id=i.id,
                    name=i.name,
                    balance=i.balance,
                    maturity_date=i.maturity_date,
                )
                for i in rows
            ]
        except Exception as e:
            logger.error(f"[InvestmentService] List failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to list investments")

    async def list_paginated(self, page: int, db: AsyncSession) -> InvestmentPageDTO:
        offset = max(page - 1, 0) * self.PAGE_SIZE
        async with db.begin():
            items, total = await self.investment_repository.list_paginated(
                offset=offset, limit=self.PAGE_SIZE, session=db
            )

        items_dto = [
            InvestmentDTO(
                id=i.id,
                name=i.name,
                balance=i.balance,
                maturity_date=i.maturity_date,
            )
            for i in items
        ]
        total = int(total or 0)
        total_pages = max(1, ceil(total / self.PAGE_SIZE)) if total else 1

        return InvestmentPageDTO(
            items=items_dto,
            page=page,
            page_size=self.PAGE_SIZE,
            total=total,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1,
        )

    async def update_balance(self, investment_id: int, new_balance: float, db: AsyncSession) -> InvestmentDTO:
        logger.info(f"[InvestmentService] Update balance ID={investment_id} -> {new_balance}")
        try:
            if new_balance < 0:
                raise HTTPException(status_code=400, detail="Balance must be >= 0.")
            async with db.begin():
                i = await self.investment_repository.update_balance(investment_id, new_balance, db)
            if not i:
                raise HTTPException(status_code=404, detail="Investment not found.")
            return InvestmentDTO(
                id=i.id,
                name=i.name,
                balance=i.balance,
                maturity_date=i.maturity_date,
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"[InvestmentService] Update balance failed ID={investment_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to update investment balance")
        
    async def add_balance(self, payload: InvestmentAddBalanceIn, db: AsyncSession) -> InvestmentDTO:
        investment_id = payload.investment_id
        amount = payload.amount
        kind: Literal["interest", "topup"] = payload.kind

        if amount <= 0:
            raise HTTPException(status_code=400, detail="amount must be > 0")

        async with db.begin():
            inv_row = await self.investment_repository.get_by_id(investment_id, db)
            if not inv_row:
                raise HTTPException(status_code=404, detail="Investment not found.")
            if not inv_row.bank_id:
                raise HTTPException(status_code=400, detail="Investment has no bank bound.")

            inv = await self.investment_repository.increment_balance(investment_id, amount, db)
            if not inv:
                raise HTTPException(status_code=404, detail="Investment not found after update.")

            if kind == "interest":
                t = await self.transaction_type_repository.get_by_name("Interes Inversion", session=db)
                type_id = t.id if t else None
                tx = TransactionCreate(
                    bank_id=inv_row.bank_id,
                    amount=amount,
                    type_id=type_id,
                    description=payload.description or f"Interes Inversion {inv_row.name}",
                    is_auto=False,
                    created_at=datetime.now(),
                )
            else:  
                if payload.source_bank_id is None:
                    raise HTTPException(status_code=400, detail="source_bank_id is required for kind='topup'")
                source_bank_id: int = payload.source_bank_id

                await self.bank_repository.decrease_balance(source_bank_id, amount, db)

                t = await self.transaction_type_repository.get_by_name("Retiro", session=db)
                type_id = t.id if t else None
                tx = TransactionCreate(
                    bank_id=source_bank_id,
                    amount=amount, 
                    type_id=type_id,
                    description=payload.description or f"Aporte a inversión {inv_row.name}",
                    is_auto=False,
                    created_at=datetime.now(),  
                )

            await self.transaction_service.insert_transaction(tx, db)

        return InvestmentDTO(
            id=inv.id,
            name=inv.name,
            balance=inv.balance,
            maturity_date=inv.maturity_date,
        )

    async def withdraw(self, payload: InvestmentWithdrawIn, db: AsyncSession) -> Optional[InvestmentDTO]:
        inv_id = payload.investment_id

        async with db.begin():
            inv_row = await self.investment_repository.get_by_id(inv_id, db)
            if not inv_row:
                raise HTTPException(status_code=404, detail="Investment not found.")

            current_balance = float(inv_row.balance or 0.0)
            if current_balance <= 0:
                raise HTTPException(status_code=400, detail="Investment has zero balance.")

            amount = current_balance if payload.kind == "full" else float(payload.amount)  # type: ignore[arg-type]
            if amount <= 0:
                raise HTTPException(status_code=400, detail="amount must be > 0")
            if amount > current_balance:
                raise HTTPException(status_code=400, detail="amount exceeds current balance")

            dest_bank_id = payload.destination_bank_id or inv_row.bank_id
            if not dest_bank_id:
                raise HTTPException(status_code=400, detail="destination_bank_id required")

            inv_after = await self.investment_repository.decrease_balance(inv_id, amount, db)
            if not inv_after:
                raise HTTPException(status_code=404, detail="Investment not found after update.")

            await self.bank_repository.increase_balance(dest_bank_id, amount, db)

            tx_name = "Retiro"
            t = await self.transaction_type_repository.get_by_name(tx_name, session=db)
            type_id = t.id if t else None

            tx = TransactionCreate(
                bank_id=dest_bank_id,
                amount=amount, 
                type_id=type_id,
                description=payload.description or (
                    f"{tx_name} {inv_row.name}" if tx_name == "Liquidacion Inversion"
                    else f"Retiro de inversión {inv_row.name}"
                ),
                is_auto=True,
                created_at=datetime.now(),
            )
            await self.transaction_service.insert_transaction(tx, db)

            if float(inv_after.balance or 0.0) == 0.0:
                await self.investment_repository.delete_investment(inv_id, db)
                return None  

        return InvestmentDTO(
            id=inv_after.id,
            name=inv_after.name,
            balance=inv_after.balance,
            maturity_date=inv_after.maturity_date,
        )

    async def delete(self, investment_id: int, db: AsyncSession) -> bool:
        logger.warning(f"[InvestmentService] Delete investment ID={investment_id}")
        try:
            async with db.begin():
                ok = await self.investment_repository.delete_investment(investment_id, db)
            if not ok:
                raise HTTPException(status_code=404, detail="Investment not found.")
            return True
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"[InvestmentService] Delete failed ID={investment_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to delete investment")
