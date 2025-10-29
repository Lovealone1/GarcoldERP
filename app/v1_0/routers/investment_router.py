from typing import List, Dict
from fastapi import APIRouter, HTTPException, Depends, Body, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from dependency_injector.wiring import inject, Provide

from app.storage.database.db_connector import get_db
from app.app_containers import ApplicationContainer
from app.core.logger import logger

from app.v1_0.schemas import InvestmentCreate, InvestmentAddBalanceIn
from app.v1_0.entities import InvestmentDTO, InvestmentPageDTO
from app.v1_0.services import InvestmentService

router = APIRouter(prefix="/investments", tags=["Investments"])


@router.post(
    "/create",
    response_model=InvestmentDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Create investment",
)
@inject
async def create_investment(
    request: InvestmentCreate,
    db: AsyncSession = Depends(get_db),
    service: InvestmentService = Depends(
        Provide[ApplicationContainer.api_container.investment_service]
    ),
):
    logger.info(f"[InvestmentRouter] create payload={request.model_dump()}")
    try:
        return await service.create(request, db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[InvestmentRouter] create error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create investment")


@router.get(
    "/by-id/{investment_id}",
    response_model=InvestmentDTO,
    summary="Get investment by ID",
)
@inject
async def get_investment(
    investment_id: int,
    db: AsyncSession = Depends(get_db),
    service: InvestmentService = Depends(
        Provide[ApplicationContainer.api_container.investment_service]
    ),
):
    logger.debug(f"[InvestmentRouter] get id={investment_id}")
    try:
        return await service.get(investment_id, db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[InvestmentRouter] get error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch investment")


@router.get(
    "",
    response_model=List[InvestmentDTO],
    summary="List all investments",
)
@inject
async def list_investments(
    db: AsyncSession = Depends(get_db),
    service: InvestmentService = Depends(
        Provide[ApplicationContainer.api_container.investment_service]
    ),
):
    logger.debug("[InvestmentRouter] list_all")
    try:
        return await service.list_all(db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[InvestmentRouter] list_all error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list investments")


@router.get(
    "/page",
    response_model=InvestmentPageDTO,
    summary="List investments paginated",
)
@inject
async def list_investments_paginated(
    page: int = Query(1, ge=1),
    db: AsyncSession = Depends(get_db),
    service: InvestmentService = Depends(
        Provide[ApplicationContainer.api_container.investment_service]
    ),
):
    logger.debug(f"[InvestmentRouter] list_paginated page={page}")
    try:
        return await service.list_paginated(page, db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[InvestmentRouter] list_paginated error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list investments")


@router.patch(
    "/by-id/{investment_id}/balance",
    response_model=InvestmentDTO,
    summary="Update investment balance",
)
@inject
async def update_investment_balance(
    investment_id: int,
    new_balance: float = Body(..., embed=True, ge=0),
    db: AsyncSession = Depends(get_db),
    service: InvestmentService = Depends(
        Provide[ApplicationContainer.api_container.investment_service]
    ),
):
    logger.info(f"[InvestmentRouter] update_balance id={investment_id} new_balance={new_balance}")
    try:
        return await service.update_balance(investment_id, new_balance, db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[InvestmentRouter] update_balance error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update investment balance")


@router.delete(
    "/by-id/{investment_id}",
    response_model=Dict[str, str],
    summary="Delete investment",
)
@inject
async def delete_investment(
    investment_id: int,
    db: AsyncSession = Depends(get_db),
    service: InvestmentService = Depends(
        Provide[ApplicationContainer.api_container.investment_service]
    ),
):
    logger.warning(f"[InvestmentRouter] delete id={investment_id}")
    try:
        ok = await service.delete(investment_id, db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[InvestmentRouter] delete error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete investment")

    if not ok:
        raise HTTPException(status_code=404, detail="Investment not found")
    return {"message": f"Investment with ID {investment_id} deleted successfully"}

@router.post(
    "/balance/add",
    status_code=status.HTTP_200_OK,
    response_model=InvestmentDTO,
    summary="Incrementa el saldo de una inversión y registra la transacción automática",
)
@inject
async def add_investment_balance(
    payload: InvestmentAddBalanceIn,
    db: AsyncSession = Depends(get_db),
    service: InvestmentService = Depends(
        Provide[ApplicationContainer.api_container.investment_service]
    ),
):
    try:
        return await service.add_balance(
            investment_id=payload.investment_id,
            amount=payload.amount,
            db=db,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[InvestmentRouter] add_balance error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to add balance")