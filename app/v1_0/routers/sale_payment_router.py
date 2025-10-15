from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from dependency_injector.wiring import inject, Provide
from typing import Dict, List

from app.utils.database.db_connector import get_db
from app.app_containers import ApplicationContainer
from app.core.logger import logger

from app.v1_0.schemas import SalePaymentCreate
from app.v1_0.entities import SalePaymentDTO, SalePaymentViewDTO
from app.v1_0.services import SalePaymentService

router = APIRouter(prefix="/sale-payments", tags=["SalePayments"])


@router.post(
    "/create",
    response_model=SalePaymentDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Create a payment for a credit sale",
)
@inject
async def create_sale_payment(
    request: SalePaymentCreate,
    db: AsyncSession = Depends(get_db),
    service: SalePaymentService = Depends(
        Provide[ApplicationContainer.api_container.sale_payment_service]
    ),
) -> SalePaymentDTO:
    logger.info(f"[SalePaymentRouter] create payload={request.model_dump()}")
    try:
        return await service.create_sale_payment(request, db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[SalePaymentRouter] create error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create sale payment")

@router.delete(
    "/{payment_id}",
    response_model=Dict[str, str],
    summary="Delete a sale payment and restore balances",
    status_code=status.HTTP_200_OK,
)
@inject
async def delete_sale_payment(
    payment_id: int,
    db: AsyncSession = Depends(get_db),
    service: SalePaymentService = Depends(
        Provide[ApplicationContainer.api_container.sale_payment_service]
    ),
):
    logger.warning(f"[SalePaymentRouter] delete payment_id={payment_id}")
    try:
        ok = await service.delete_sale_payment(payment_id=payment_id, db=db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[SalePaymentRouter] delete error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete sale payment")

    if not ok:
        raise HTTPException(status_code=404, detail="Sale payment not found")

    return {"message": f"Sale payment with ID {payment_id} deleted successfully"}

@router.get(
    "/by-sale/{sale_id}",
    response_model=List[SalePaymentViewDTO],
    summary="List all payments for a sale",
)
@inject
async def list_payments_by_sale(
    sale_id: int,
    db: AsyncSession = Depends(get_db),
    service: SalePaymentService = Depends(
        Provide[ApplicationContainer.api_container.sale_payment_service]
    ),
) -> List[SalePaymentViewDTO]:
    logger.debug(f"[SalePaymentRouter] list_payments_by_sale sale_id={sale_id}")
    try:
        return await service.list_sale_payments(sale_id, db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[SalePaymentRouter] list_payments_by_sale error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list sale payments")