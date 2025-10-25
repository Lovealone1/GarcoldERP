from typing import Dict, Any, List, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Body, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from dependency_injector.wiring import inject, Provide

from app.storage.database.db_connector import get_db
from app.app_containers import ApplicationContainer
from app.core.logger import logger

from app.v1_0.entities import PurchaseDTO, PurchaseItemViewDTO, PurchasePageDTO
from app.v1_0.services import PurchaseService

router = APIRouter(prefix="/purchases", tags=["Purchases"])


@router.post(
    "/create",
    response_model=PurchaseDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Finalize a purchase from cart",
)
@inject
async def finalize_purchase(
    supplier_id: int = Body(..., embed=True, description="Supplier ID"),
    bank_id: int = Body(..., embed=True, description="Bank ID"),
    status_id: int = Body(..., embed=True, description="Status ID"),
    cart: List[Dict[str, Any]] = Body(..., embed=True, description="Purchase cart items"),
    purchase_date: Optional[datetime] = Body(None, embed=True, description="Optional purchase datetime"),
    db: AsyncSession = Depends(get_db),
    service: PurchaseService = Depends(Provide[ApplicationContainer.api_container.purchase_service]),
):
    logger.info(
        "[PurchaseRouter] finalize_purchase "
        f"supplier_id={supplier_id} bank_id={bank_id} status_id={status_id} "
        f"cart_len={len(cart) if isinstance(cart, list) else 'N/A'} purchase_date={purchase_date}"
    )
    try:
        return await service.finalize_purchase(
            supplier_id=supplier_id,
            bank_id=bank_id,
            status_id=status_id,
            cart=cart,
            db=db,
            purchase_date=purchase_date,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[PurchaseRouter] finalize_purchase error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to finalize purchase")

@router.get(
    "/{purchase_id}",
    response_model=PurchaseDTO,
    summary="Get a purchase by ID",
)
@inject
async def get_purchase(
    purchase_id: int,
    db: AsyncSession = Depends(get_db),
    service: PurchaseService = Depends(
        Provide[ApplicationContainer.api_container.purchase_service]
    ),
) -> PurchaseDTO:
    logger.debug(f"[PurchaseRouter] get_purchase id={purchase_id}")
    try:
        return await service.get_purchase(purchase_id, db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[PurchaseRouter] get_purchase error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch purchase")


@router.get(
    "/",
    response_model=PurchasePageDTO,
    summary="List purchases (paginated)",
)
@inject
async def list_purchases(
    page: int = Query(1, ge=1, description="1-based page number"),
    db: AsyncSession = Depends(get_db),
    service: PurchaseService = Depends(
        Provide[ApplicationContainer.api_container.purchase_service]
    ),
) -> PurchasePageDTO:
    logger.debug(f"[PurchaseRouter] list_purchases page={page}")
    try:
        return await service.list_purchases(page, db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[PurchaseRouter] list_purchases error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list purchases")


@router.get(
    "/{purchase_id}/items",
    response_model=List[PurchaseItemViewDTO],
    summary="List items for a purchase",
)
@inject
async def list_purchase_items(
    purchase_id: int,
    db: AsyncSession = Depends(get_db),
    service: PurchaseService = Depends(
        Provide[ApplicationContainer.api_container.purchase_service]
    ),
) -> List[PurchaseItemViewDTO]:
    logger.debug(f"[PurchaseRouter] list_purchase_items purchase_id={purchase_id}")
    try:
        return await service.list_items(purchase_id, db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[PurchaseRouter] list_purchase_items error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list purchase items")


@router.delete(
    "/{purchase_id}",
    response_model=Dict[str, str],
    summary="Delete a purchase",
    status_code=status.HTTP_200_OK,
)
@inject
async def delete_purchase(
    purchase_id: int,
    db: AsyncSession = Depends(get_db),
    service: PurchaseService = Depends(
        Provide[ApplicationContainer.api_container.purchase_service]
    ),
) -> Dict[str, str]:
    logger.warning(f"[PurchaseRouter] delete_purchase id={purchase_id}")
    try:
        await service.delete_purchase(purchase_id, db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[PurchaseRouter] delete_purchase error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete purchase")

    return {"message": f"Purchase with ID {purchase_id} deleted successfully"}