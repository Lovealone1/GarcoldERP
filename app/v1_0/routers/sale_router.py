from typing import Dict, List, Any, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Body, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from dependency_injector.wiring import inject, Provide

from app.storage.database.db_connector import get_db
from app.app_containers import ApplicationContainer
from app.core.logger import logger

from app.v1_0.entities import SaleDTO, SalePageDTO, SaleItemViewDTO
from app.v1_0.services import SaleService

router = APIRouter(prefix="/sales", tags=["Sales"])


@router.post(
    "/create",
    response_model=SaleDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Finalize a sale from a cart",
)
@inject
async def finalize_sale(
    customer_id: int = Body(..., embed=True),
    bank_id: int = Body(..., embed=True),
    status_id: int = Body(..., embed=True),
    cart: List[Dict[str, Any]] = Body(..., embed=True, description="Cart items"),
    sale_date: Optional[datetime] = Body(None, embed=True, description="Optional sale datetime"),
    db: AsyncSession = Depends(get_db),
    service: SaleService = Depends(Provide[ApplicationContainer.api_container.sale_service]),
):
    logger.info(
        "[SaleRouter] finalize_sale "
        f"customer_id={customer_id} bank_id={bank_id} status_id={status_id} "
        f"cart_len={len(cart) if cart else 0} sale_date={sale_date}"
    )
    try:
        return await service.finalize_sale(customer_id, bank_id, status_id, cart, db, sale_date=sale_date)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[SaleRouter] finalize_sale error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to finalize sale")


@router.get(
    "/by-id/{sale_id}",
    response_model=SaleDTO,
    summary="Get a sale by ID",
)
@inject
async def get_sale(
    sale_id: int,
    db: AsyncSession = Depends(get_db),
    service: SaleService = Depends(Provide[ApplicationContainer.api_container.sale_service]),
):
    logger.debug(f"[SaleRouter] get_sale id={sale_id}")
    try:
        return await service.get_sale(sale_id, db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[SaleRouter] get_sale error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch sale")


@router.delete(
    "/{sale_id}",
    response_model=Dict[str, str],
    summary="Delete a sale (reverts balances/inventory as needed)",
)
@inject
async def delete_sale(
    sale_id: int,
    db: AsyncSession = Depends(get_db),
    service: SaleService = Depends(Provide[ApplicationContainer.api_container.sale_service]),
):
    logger.warning(f"[SaleRouter] delete_sale id={sale_id}")
    try:
        await service.delete_sale(sale_id, db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[SaleRouter] delete_sale error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete sale")

    return {"message": f"Sale with ID {sale_id} deleted successfully"}


@router.get(
    "",
    response_model=SalePageDTO,
    summary="List sales (paginated)",
)
@inject
async def list_sales(
    page: int = Query(1, ge=1),
    db: AsyncSession = Depends(get_db),
    service: SaleService = Depends(Provide[ApplicationContainer.api_container.sale_service]),
):
    logger.debug(f"[SaleRouter] list_sales page={page}")
    try:
        return await service.list_sales(page, db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[SaleRouter] list_sales error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list sales")


@router.get(
    "/{sale_id}/items",
    response_model=List[SaleItemViewDTO],
    summary="List items for a sale",
)
@inject
async def list_sale_items(
    sale_id: int,
    db: AsyncSession = Depends(get_db),
    service: SaleService = Depends(Provide[ApplicationContainer.api_container.sale_service]),
):
    logger.debug(f"[SaleRouter] list_sale_items sale_id={sale_id}")
    try:
        return await service.list_items(sale_id, db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[SaleRouter] list_sale_items error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list sale items")
