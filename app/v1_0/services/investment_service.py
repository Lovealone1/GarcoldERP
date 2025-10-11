from typing import List
from math import ceil
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import logger
from app.v1_0.repositories import InvestmentRepository
from app.v1_0.schemas import InvestmentCreate
from app.v1_0.entities import InvestmentDTO, InvestmentPageDTO

class InvestmentService:
    def __init__(self, investment_repository: InvestmentRepository) -> None:
        self.investment_repository = investment_repository
        self.PAGE_SIZE = 10

    async def _require(self, investment_id: int, db: AsyncSession):
        inv = await self.investment_repository.get_by_id(investment_id, db)
        if not inv:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Investment not found.")
        return inv

    async def create(self, payload: InvestmentCreate, db: AsyncSession) -> InvestmentDTO:
        logger.info(f"[InvestmentService] Creating investment: {payload.model_dump()}")
        try:
            async with db.begin():
                i = await self.investment_repository.create_investment(payload, db)
            logger.info(f"[InvestmentService] Investment created ID={i.id}")
            return InvestmentDTO(
                id=i.id,
                name=i.name,
                balance=i.balance,
                maturity_date=i.maturity_date,
            )
        except Exception as e:
            logger.error(f"[InvestmentService] Create failed: {e}", exc_info=True)
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
