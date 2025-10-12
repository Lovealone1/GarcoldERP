from typing import List
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import logger
from app.v1_0.repositories import ExpenseCategoryRepository
from app.v1_0.entities import ExpenseCategoryDTO
from app.v1_0.schemas import ExpenseCategoryCreate


class ExpenseCategoryService:
    def __init__(self, repo: ExpenseCategoryRepository) -> None:
        self.repo = repo

    async def _require(self, category_id: int, db: AsyncSession):
        cat = await self.repo.get_category_by_id(category_id, db)
        if not cat:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense category not found.")
        return cat

    async def create(self, payload: ExpenseCategoryCreate, db: AsyncSession) -> ExpenseCategoryDTO:
        logger.info(f"[ExpenseCategoryService] Creating category: {payload}")
        try:
            async with db.begin():
                c = await self.repo.create_category(payload, db)
            logger.info(f"[ExpenseCategoryService] Created ID={c.id}")
            return ExpenseCategoryDTO(id=c.id, name=c.name)
        except Exception as e:
            logger.error(f"[ExpenseCategoryService] Create failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to create expense category")

    async def get(self, category_id: int, db: AsyncSession) -> ExpenseCategoryDTO:
        logger.debug(f"[ExpenseCategoryService] Get ID={category_id}")
        try:
            async with db.begin():
                c = await self._require(category_id, db)
            return ExpenseCategoryDTO(id=c.id, name=c.name)
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"[ExpenseCategoryService] Get failed ID={category_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to fetch expense category")

    async def list_all(self, db: AsyncSession) -> List[ExpenseCategoryDTO]:
        logger.debug("[ExpenseCategoryService] List all")
        try:
            async with db.begin():
                rows = await self.repo.get_all_categories(db)
            return [ExpenseCategoryDTO(id=c.id, name=c.name) for c in rows]
        except Exception as e:
            logger.error(f"[ExpenseCategoryService] List failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to list expense categories")

    async def delete(self, category_id: int, db: AsyncSession) -> bool:
        logger.warning(f"[ExpenseCategoryService] Delete ID={category_id}")
        try:
            async with db.begin():
                ok = await self.repo.delete_category(category_id, db)
            if not ok:
                raise HTTPException(status_code=404, detail="Expense category not found.")
            return True
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"[ExpenseCategoryService] Delete failed ID={category_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to delete expense category")
