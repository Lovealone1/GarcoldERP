from typing import List
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from dependency_injector.wiring import inject, Provide

from app.utils.database.db_connector import get_db
from app.app_containers import ApplicationContainer
from app.core.logger import logger

from app.v1_0.entities import ProfitDTO, ProfitPageDTO, ProfitItemDTO
from app.v1_0.services.profit_service import ProfitService

router = APIRouter(prefix="/profits", tags=["Profits"])


@router.get(
    "/",
    response_model=ProfitPageDTO,
    summary="List profits (paginated, ascending by id)",
)
@inject
async def list_profits(
    page: int = Query(1, ge=1, description="1-based page number"),
    db: AsyncSession = Depends(get_db),
    service: ProfitService = Depends(
        Provide[ApplicationContainer.api_container.profit_service]
    ),
) -> ProfitPageDTO:
    logger.debug(f"[ProfitRouter] list_profits page={page}")
    try:
        return await service.list_profits(page, db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ProfitRouter] list_profits error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list profits")


@router.get(
    "/by-sale/{sale_id}",
    response_model=ProfitDTO,
    summary="Get profit aggregate by sale id",
)
@inject
async def get_profit_by_sale(
    sale_id: int,
    db: AsyncSession = Depends(get_db),
    service: ProfitService = Depends(
        Provide[ApplicationContainer.api_container.profit_service]
    ),
) -> ProfitDTO:
    logger.info(f"[ProfitRouter] get_profit_by_sale sale_id={sale_id}")
    try:
        profit = await service.get_by_sale_id(sale_id, db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ProfitRouter] get_profit_by_sale error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get profit")

    return ProfitDTO(
        id=profit.id,
        sale_id=profit.sale_id,
        profit=float(profit.profit or 0.0),
        created_at=profit.created_at,
    )


@router.get(
    "/details/{sale_id}",
    response_model=List[ProfitItemDTO],
    summary="List profit details (per item) for a sale",
)
@inject
async def list_profit_details_by_sale(
    sale_id: int,
    db: AsyncSession = Depends(get_db),
    service: ProfitService = Depends(
        Provide[ApplicationContainer.api_container.profit_service]
    ),
) -> List[ProfitItemDTO]:
    logger.debug(f"[ProfitRouter] list_profit_details_by_sale sale_id={sale_id}")
    try:
        return await service.get_details_by_sale(sale_id, db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ProfitRouter] list_profit_details_by_sale error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list profit details")