from typing import List
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import logger
from app.v1_0.entities import ExpenseCategoryDTO
from app.v1_0.repositories import ExpenseCategoryRepository
from app.v1_0.schemas import ExpenseCategoryCreate


class ExpenseCategoryService:
    """CRUD operations for expense categories."""

    def __init__(self, expense_category_repository: ExpenseCategoryRepository) -> None:
        self.repo = expense_category_repository

    async def _require(self, category_id: int, db: AsyncSession):
        """Fetch category or raise 404.

        Args:
            category_id: Expense category ID.
            db: Active async DB session.

        Returns:
            ORM category row.

        Raises:
            HTTPException: 404 if not found.
        """
        cat = await self.repo.get_category_by_id(category_id, db)
        if not cat:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Expense category not found."
            )
        return cat

    async def create(self, payload: ExpenseCategoryCreate, db: AsyncSession) -> ExpenseCategoryDTO:
        """Create a new expense category.

        Args:
            payload: Category data.
            db: Active async DB session.

        Returns:
            ExpenseCategoryDTO.

        Raises:
            HTTPException: 500 on failure.
        """
        logger.info("[ExpenseCategoryService] Creating category: %s", payload)
        try:
            async with db.begin():
                c = await self.repo.create_category(payload, db)
            logger.info("[ExpenseCategoryService] Created ID=%s", c.id)
            return ExpenseCategoryDTO(id=c.id, name=c.name)
        except Exception as e:
            logger.error("[ExpenseCategoryService] Create failed: %s", e, exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to create expense category")

    async def get(self, category_id: int, db: AsyncSession) -> ExpenseCategoryDTO:
        """Get a category by ID.

        Args:
            category_id: Expense category ID.
            db: Active async DB session.

        Returns:
            ExpenseCategoryDTO.

        Raises:
            HTTPException: 404 if not found, 500 on failure.
        """
        logger.debug("[ExpenseCategoryService] Get ID=%s", category_id)
        try:
            async with db.begin():
                c = await self._require(category_id, db)
            return ExpenseCategoryDTO(id=c.id, name=c.name)
        except HTTPException:
            raise
        except Exception as e:
            logger.error(
                "[ExpenseCategoryService] Get failed ID=%s: %s", category_id, e, exc_info=True
            )
            raise HTTPException(status_code=500, detail="Failed to fetch expense category")

    async def list_all(self, db: AsyncSession) -> List[ExpenseCategoryDTO]:
        """List all expense categories.

        Args:
            db: Active async DB session.

        Returns:
            List of ExpenseCategoryDTO.

        Raises:
            HTTPException: 500 on failure.
        """
        logger.debug("[ExpenseCategoryService] List all")
        try:
            async with db.begin():
                rows = await self.repo.get_all_categories(db)
            return [ExpenseCategoryDTO(id=c.id, name=c.name) for c in rows]
        except Exception as e:
            logger.error("[ExpenseCategoryService] List failed: %s", e, exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to list expense categories")

    async def delete(self, category_id: int, db: AsyncSession) -> bool:
        """Delete a category by ID.

        Args:
            category_id: Expense category ID.
            db: Active async DB session.

        Returns:
            True on success.

        Raises:
            HTTPException: 404 if not found, 500 on failure.
        """
        logger.warning("[ExpenseCategoryService] Delete ID=%s", category_id)
        try:
            async with db.begin():
                ok = await self.repo.delete_category(category_id, db)
            if not ok:
                raise HTTPException(status_code=404, detail="Expense category not found.")
            return True
        except HTTPException:
            raise
        except Exception as e:
            logger.error(
                "[ExpenseCategoryService] Delete failed ID=%s: %s", category_id, e, exc_info=True
            )
            raise HTTPException(status_code=500, detail="Failed to delete expense category")
