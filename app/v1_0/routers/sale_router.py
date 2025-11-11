from typing import Dict, List, Any, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Body, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from dependency_injector.wiring import inject, Provide

from app.core.security.deps import AuthContext, get_auth_context
from app.storage.database.db_connector import get_db
from app.app_containers import ApplicationContainer
from app.core.logger import logger

from app.v1_0.entities import SaleDTO, SalePageDTO, SaleItemViewDTO
from app.v1_0.services import SaleService
from app.core.security.realtime_auth import build_channel_id_from_auth
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
    cart: List[Dict[str, Any]] = Body(..., embed=True),
    sale_date: Optional[datetime] = Body(None, embed=True),
    db: AsyncSession = Depends(get_db),
    auth_ctx: AuthContext = Depends(get_auth_context),
    service: SaleService = Depends(
        Provide[ApplicationContainer.api_container.sale_service]
    ),
):
    logger.info(
        "[SaleRouter] finalize_sale customer_id=%s bank_id=%s status_id=%s cart_len=%s sale_date=%s",
        customer_id,
        bank_id,
        status_id,
        len(cart) if cart else 0,
        sale_date,
    )

    channel_id = build_channel_id_from_auth(auth_ctx)

    try:
        return await service.finalize_sale(
            customer_id=customer_id,
            bank_id=bank_id,
            status_id=status_id,
            cart=cart,
            db=db,
            sale_date=sale_date,
            channel_id=channel_id,
        )
    except HTTPException:
        raise
    except Exception as e:
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
    auth_ctx: AuthContext = Depends(get_auth_context),
    service: SaleService = Depends(Provide[ApplicationContainer.api_container.sale_service]),
):
    channel_id = build_channel_id_from_auth(auth_ctx) 
    await service.delete_sale(sale_id=sale_id, db=db, channel_id=channel_id)

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
