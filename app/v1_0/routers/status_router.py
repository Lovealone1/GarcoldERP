from typing import List
from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from dependency_injector.wiring import inject, Provide

from app.storage.database.db_connector import get_db
from app.app_containers import ApplicationContainer
from app.core.logger import logger

from app.v1_0.entities import StatusDTO
from app.v1_0.services.status_service import StatusService

router = APIRouter(prefix="/statuses", tags=["Statuses"])

@router.get(
    "",
    response_model=List[StatusDTO],
    summary="List all statuses",
    status_code=status.HTTP_200_OK,
)
@inject
async def list_statuses(
    db: AsyncSession = Depends(get_db),
    service: StatusService = Depends(
        Provide[ApplicationContainer.api_container.status_service]
    ),
):
    logger.debug("[StatusRouter] list_statuses")
    try:
        return await service.list_statuses(db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[StatusRouter] list_statuses error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list statuses")
