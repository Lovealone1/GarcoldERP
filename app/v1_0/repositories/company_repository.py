from typing import Optional, Dict, Any 
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.v1_0.models import Company
from app.v1_0.entities import Regimen, ALLOWED_FIELDS
from .base_repository import BaseRepository

class CompanyRepository(BaseRepository[Company]):
    def __init__(self):
        super().__init__(Company)

    async def get_by_id(self, company_id: int, session: AsyncSession) -> Optional[Company]:
        return await super().get_by_id(company_id, session)

    async def get_single(self, session: AsyncSession) -> Optional[Company]:
        return await session.scalar(select(Company).limit(1))

    async def patch_single(self, session: AsyncSession, **fields: Any) -> Company:
        company = await self.get_single(session)
        if not company:
            raise ValueError("company_not_found")

        to_update: Dict[str, Any] = {k: v for k, v in fields.items() if k in ALLOWED_FIELDS and v is not None}

        if "regimen" in to_update:
            reg = to_update["regimen"]
            if isinstance(reg, str):
                to_update["regimen"] = Regimen(reg)

        for k, v in to_update.items():
            setattr(company, k, v)

        await session.flush()
        return company