from typing import List

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import logger
from app.v1_0.entities import StatusDTO
from app.v1_0.repositories import StatusRepository


class StatusService:
    """Application service for reading status records."""

    def __init__(self, status_repository: StatusRepository) -> None:
        """Initialize the service with its repository dependency."""
        self.status_repository = status_repository

    async def list_statuses(self, db: AsyncSession) -> List[StatusDTO]:
        """
        Return all statuses as DTOs.

        Opens a short transaction for consistency on read. Maps ORM rows to
        lightweight StatusDTO objects.

        Args:
            db: Active async SQLAlchemy session.

        Returns:
            A list of StatusDTO instances.

        Raises:
            HTTPException: 500 if the repository call fails.
        """
        logger.debug("[StatusService] List statuses")
        try:
            async with db.begin():
                rows = await self.status_repository.list_statuses(db)
            return [StatusDTO(id=s.id, name=s.name) for s in rows]
        except Exception as e:
            logger.error(f"[StatusService] List failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to list statuses")
