from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.v1_0.models import Company
from .base_repository import BaseRepository

class CompanyRepository(BaseRepository[Company]):
    def __init__(self):
        super().__init__(Company)

    async def get_by_id(
        self,
        company_id: int,
        session: AsyncSession
    ) -> Optional[Company]:
        """Return the company with the given ID or None if not found."""
        return await super().get_by_id(company_id, session)