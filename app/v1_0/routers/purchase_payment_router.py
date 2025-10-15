from typing import Dict, List
from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from dependency_injector.wiring import inject, Provide

from app.storage.database.db_connector import get_db
from app.app_containers import ApplicationContainer
from app.core.logger import logger

from app.v1_0.schemas import PurchasePaymentCreate
from app.v1_0.entities import PurchasePaymentDTO, PurchasePaymentViewDTO
from app.v1_0.services.purchase_payment_service import PurchasePaymentService

router = APIRouter(prefix="/purchase-payments", tags=["PurchasePayments"])


@router.post(
    "/create",
    response_model=PurchasePaymentDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Register a payment for a credit purchase",
)
@inject
async def create_purchase_payment(
    payload: PurchasePaymentCreate,
    db: AsyncSession = Depends(get_db),
    service: PurchasePaymentService = Depends(
        Provide[ApplicationContainer.api_container.purchase_payment_service]
    ),
) -> PurchasePaymentDTO:
    logger.info(f"[PurchasePaymentRouter] create payload={payload.model_dump()}")
    try:
        return await service.create_purchase_payment(payload, db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[PurchasePaymentRouter] create error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create purchase payment")


@router.delete(
    "/{payment_id}",
    response_model=Dict[str, str],
    summary="Delete a purchase payment and restore balances",
)
@inject
async def delete_purchase_payment(
    payment_id: int,
    db: AsyncSession = Depends(get_db),
    service: PurchasePaymentService = Depends(
        Provide[ApplicationContainer.api_container.purchase_payment_service]
    ),
) -> Dict[str, str]:
    logger.warning(f"[PurchasePaymentRouter] delete id={payment_id}")
    try:
        ok = await service.delete_purchase_payment(payment_id, db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[PurchasePaymentRouter] delete error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete purchase payment")

    if not ok:
        raise HTTPException(status_code=404, detail="Purchase payment not found")
    return {"message": f"Purchase payment with ID {payment_id} deleted successfully"}


@router.get(
    "/by-purchase/{purchase_id}",
    response_model=List[PurchasePaymentViewDTO],
    summary="List payments for a purchase",
)
@inject
async def list_purchase_payments(
    purchase_id: int,
    db: AsyncSession = Depends(get_db),
    service: PurchasePaymentService = Depends(
        Provide[ApplicationContainer.api_container.purchase_payment_service]
    ),
) -> List[PurchasePaymentViewDTO]:
    logger.debug(f"[PurchasePaymentRouter] list by purchase id={purchase_id}")
    try:
        return await service.list_purchase_payments(purchase_id, db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[PurchasePaymentRouter] list error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list purchase payments")
