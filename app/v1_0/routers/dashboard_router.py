from typing import Optional
from datetime import date
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from dependency_injector.wiring import inject, Provide

from app.utils.database.db_connector import get_db
from app.app_containers import ApplicationContainer
from app.core.logger import logger

from app.v1_0.entities import FinalReportDTO, Bucket as BucketDTO
from app.v1_0.services import DashboardService

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

# app/v1_0/routers/dashboard_router.py

from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Query, Body, status
from sqlalchemy.ext.asyncio import AsyncSession
from dependency_injector.wiring import inject, Provide

from app.utils.database.db_connector import get_db
from app.app_containers import ApplicationContainer
from app.core.logger import logger

from app.v1_0.entities import FinalReportDTO, RequestMetaDTO
from app.v1_0.services import DashboardService

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.post(
    "",
    response_model=FinalReportDTO,
    status_code=status.HTTP_200_OK,
    summary="Get final dashboard report",
)
@inject
async def get_final_dashboard_report(
    payload: RequestMetaDTO = Body(..., embed=True),
    top_limit: Optional[int] = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    service: DashboardService = Depends(
        Provide[ApplicationContainer.api_container.dashboard_service]
    ),
) -> FinalReportDTO:
    logger.info(
        "[DashboardRouter] final_report "
        f"bucket={payload.bucket} pivot={payload.pivot} "
        f"date_from={payload.date_from} date_to={payload.date_to} "
        f"year={payload.year} month={payload.month} top_limit={top_limit}"
    )
    try:
        return await service.final_report(
            session=db,
            bucket=payload.bucket,
            pivot=payload.pivot,
            date_from=payload.date_from,
            date_to=payload.date_to,
            year=payload.year,
            month=payload.month,
            top_limit=top_limit,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[DashboardRouter] final_report error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate dashboard report")
