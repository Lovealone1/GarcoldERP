from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from app.core.logger import logger
from app.v1_0.repositories import StatusRepository
from app.v1_0.entities import StatusDTO

class StatusService:
    def __init__(self, status_repository: StatusRepository) -> None:
        self.status_repository = status_repository

    async def list_statuses(self, db: AsyncSession) -> List[StatusDTO]:
        logger.debug("[StatusService] List statuses")
        try:
            async with db.begin():
                rows = await self.status_repository.list_statuses(db)
            return [StatusDTO(id=s.id, name=s.name) for s in rows]
        except Exception as e:
            logger.error(f"[StatusService] List failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to list statuses")
