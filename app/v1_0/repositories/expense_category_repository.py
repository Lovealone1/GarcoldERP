from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession

from app.v1_0.models import ExpenseCategory
from app.v1_0.entities import ExpenseCategoryDTO
from .base_repository import BaseRepository

class ExpenseCategoryRepository(BaseRepository[ExpenseCategory]):
    def __init__(self):
        super().__init__(ExpenseCategory)

    async def create_category(
        self,
        dto: ExpenseCategoryDTO,
        session: AsyncSession
    ) -> ExpenseCategory:
        """
        Create a new category from DTO.
        Ignores dto.id if DB auto-generates PK.
        """
        category = ExpenseCategory(nombre=dto.name)
        await self.add(category, session)
        return category

    async def get_category_by_id(
        self,
        category_id: int,
        session: AsyncSession
    ) -> Optional[ExpenseCategory]:
        return await super().get_by_id(category_id, session=session)

    async def get_all_categories(
        self,
        session: AsyncSession
    ) -> List[ExpenseCategory]:
        return await super().get_all(session=session)

    async def delete_category(
        self,
        category_id: int,
        session: AsyncSession
    ) -> bool:
        category = await self.get_category_by_id(category_id, session)
        if not category:
            return False
        await self.delete(category, session)
        return True
