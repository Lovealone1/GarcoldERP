from datetime import datetime
from typing import Dict, Optional, List
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from dependency_injector.wiring import inject, Provide

from app.storage.database.db_connector import get_db
from app.app_containers import ApplicationContainer
from app.utils.date_utils import Period
from app.core.logger import logger

from app.v1_0.entities import ProfitDTO, ProfitPageDTO, ProfitItemDTO
from app.v1_0.services import ProfitService
from .period_params import period_range

router = APIRouter(prefix="/profits", tags=["Profits"])


# Declared before any parameterised GET so the literal path is reachable.
@router.get(
    "/summary",
    response_model=Dict[str, float],
    summary="Total profit over the whole filtered set",
)
@inject
async def profit_summary(
    q: Optional[str] = Query(None),
    period: Period = Depends(period_range),
    db: AsyncSession = Depends(get_db),
    service: ProfitService = Depends(
        Provide[ApplicationContainer.api_container.profit_service]
    ),
) -> Dict[str, float]:
    return await service.summarize_profits(
        db, q=q, date_from=period.date_from, date_to=period.date_to
    )


@router.get(
    "/",
    response_model=ProfitPageDTO,
    summary="List profits (paginated, ascending by id)",
)
@inject
async def list_profits(
    page: int = Query(1, ge=1, description="1-based page number"),
    page_size: Optional[int] = Query(None, ge=1, le=100),
    q: Optional[str] = Query(None, description="Matches the sale number"),
    period: Period = Depends(period_range),
    db: AsyncSession = Depends(get_db),
    service: ProfitService = Depends(
        Provide[ApplicationContainer.api_container.profit_service]
    ),
) -> ProfitPageDTO:
    """Filtering happens here rather than over a locally downloaded copy."""
    logger.debug(f"[ProfitRouter] list_profits page={page}")
    try:
        return await service.list_profits(
            page, db, page_size=page_size, q=q, date_from=period.date_from, date_to=period.date_to
        )
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