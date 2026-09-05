from typing import Dict, Any, List, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Body, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from dependency_injector.wiring import inject, Provide

from app.core.security.deps import AuthContext, get_auth_context
from app.core.security.realtime_auth import build_channel_id_from_auth
from app.storage.database.db_connector import get_db
from app.app_containers import ApplicationContainer
from app.utils.date_utils import Period
from app.core.logger import logger

from app.v1_0.entities import PurchaseDTO, PurchaseItemViewDTO, PurchasePageDTO
from app.v1_0.services import PurchaseService
from .period_params import period_range, totals_with_period, with_period

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
    purchase_date: Optional[datetime] = Body(
        None,
        embed=True,
        description="Optional purchase datetime",
    ),
    db: AsyncSession = Depends(get_db),
    auth_ctx: AuthContext = Depends(get_auth_context),
    service: PurchaseService = Depends(
        Provide[ApplicationContainer.api_container.purchase_service]
    ),
) -> PurchaseDTO:
    logger.info(
        "[PurchaseRouter] finalize_purchase "
        "supplier_id=%s bank_id=%s status_id=%s cart_len=%s purchase_date=%s",
        supplier_id,
        bank_id,
        status_id,
        len(cart) if isinstance(cart, list) else "N/A",
        purchase_date,
    )

    channel_id = build_channel_id_from_auth(auth_ctx)

    try:
        return await service.finalize_purchase(
            supplier_id=supplier_id,
            bank_id=bank_id,
            status_id=status_id,
            cart=cart,
            db=db,
            purchase_date=purchase_date,
            channel_id=channel_id,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "[PurchaseRouter] finalize_purchase error: %s",
            e,
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to finalize purchase",
        )

# Registered before GET /{purchase_id}: FastAPI matches routes in order, so a
# parameterised path declared first would swallow /filter-options and /summary
# and reject them as an invalid purchase id.
@router.get(
    "/filter-options",
    response_model=Dict[str, List[str]],
    summary="Distinct bank, status and supplier names present in purchases",
)
@inject
async def purchase_filter_options(
    db: AsyncSession = Depends(get_db),
    service: PurchaseService = Depends(
        Provide[ApplicationContainer.api_container.purchase_service]
    ),
) -> Dict[str, List[str]]:
    """Feeds the filter dropdowns, previously derived from downloaded rows."""
    return await service.list_filter_options(db)


@router.get(
    "/summary",
    response_model=Dict[str, Any],
    summary="Totals over the whole filtered set",
)
@inject
async def purchase_summary(
    q: Optional[str] = Query(None),
    status_name: Optional[str] = Query(None, alias="status"),
    bank: Optional[str] = Query(None),
    supplier: Optional[str] = Query(None),
    period: Period = Depends(period_range),
    db: AsyncSession = Depends(get_db),
    service: PurchaseService = Depends(
        Provide[ApplicationContainer.api_container.purchase_service]
    ),
) -> Dict[str, Any]:
    return totals_with_period(await service.summarize_purchases(
        db,
        q=q,
        status=status_name,
        bank=bank,
        supplier=supplier,
        date_from=period.date_from,
        date_to=period.date_to,
    ), period)


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
    page_size: Optional[int] = Query(None, ge=1, le=100),
    q: Optional[str] = Query(None, description="Matches id, supplier, bank or status"),
    status_name: Optional[str] = Query(None, alias="status"),
    bank: Optional[str] = Query(None),
    supplier: Optional[str] = Query(None),
    period: Period = Depends(period_range),
    db: AsyncSession = Depends(get_db),
    service: PurchaseService = Depends(
        Provide[ApplicationContainer.api_container.purchase_service]
    ),
) -> PurchasePageDTO:
    """
    Filtering happens here rather than in the browser, which previously walked
    every page to build a complete local copy first.
    """
    logger.debug(f"[PurchaseRouter] list_purchases page={page}")
    try:
        return with_period(await service.list_purchases(
            page,
            db,
            page_size=page_size,
            q=q,
            status=status_name,
            bank=bank,
            supplier=supplier,
            date_from=period.date_from,
            date_to=period.date_to,
        ), period)
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
    auth_ctx: AuthContext = Depends(get_auth_context),
    service: PurchaseService = Depends(
        Provide[ApplicationContainer.api_container.purchase_service]
    ),
) -> Dict[str, str]:
    logger.warning(
        "[PurchaseRouter] delete_purchase id=%s",
        purchase_id,
    )

    channel_id = build_channel_id_from_auth(auth_ctx)

    try:
        await service.delete_purchase(
            purchase_id=purchase_id,
            db=db,
            channel_id=channel_id,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "[PurchaseRouter] delete_purchase error: %s",
            e,
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to delete purchase",
        )

    return {
        "message": f"Purchase with ID {purchase_id} deleted successfully"
    }
