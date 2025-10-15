from typing import List, Dict
from fastapi import APIRouter, HTTPException, Depends, Body, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from dependency_injector.wiring import inject, Provide

from app.utils.database.db_connector import get_db
from app.app_containers import ApplicationContainer
from app.core.logger import logger

from app.v1_0.schemas import LoanCreate
from app.v1_0.entities import LoanDTO, LoanPageDTO
from app.v1_0.services.loan_service import LoanService

router = APIRouter(prefix="/loans", tags=["Loans"])


@router.post(
    "/create",
    response_model=LoanDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Create loan",
)
@inject
async def create_loan(
    request: LoanCreate,
    db: AsyncSession = Depends(get_db),
    service: LoanService = Depends(
        Provide[ApplicationContainer.api_container.loan_service]
    ),
):
    logger.info(f"[LoanRouter] create payload={request.model_dump()}")
    try:
        return await service.create(request, db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[LoanRouter] create error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create loan")


@router.get(
    "/by-id/{loan_id}",
    response_model=LoanDTO,
    summary="Get loan by ID",
)
@inject
async def get_loan(
    loan_id: int,
    db: AsyncSession = Depends(get_db),
    service: LoanService = Depends(
        Provide[ApplicationContainer.api_container.loan_service]
    ),
):
    logger.debug(f"[LoanRouter] get id={loan_id}")
    try:
        return await service.get(loan_id, db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[LoanRouter] get error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch loan")


@router.get(
    "",
    response_model=List[LoanDTO],
    summary="List all loans",
)
@inject
async def list_loans(
    db: AsyncSession = Depends(get_db),
    service: LoanService = Depends(
        Provide[ApplicationContainer.api_container.loan_service]
    ),
):
    logger.debug("[LoanRouter] list_all")
    try:
        return await service.list_all(db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[LoanRouter] list_all error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list loans")


@router.get(
    "/page",
    response_model=LoanPageDTO,
    summary="List loans paginated",
)
@inject
async def list_loans_paginated(
    page: int = Query(1, ge=1),
    db: AsyncSession = Depends(get_db),
    service: LoanService = Depends(
        Provide[ApplicationContainer.api_container.loan_service]
    ),
):
    logger.debug(f"[LoanRouter] list_paginated page={page}")
    try:
        return await service.list_paginated(page, db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[LoanRouter] list_paginated error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list loans")


@router.patch(
    "/by-id/{loan_id}/amount",
    response_model=LoanDTO,
    summary="Update loan amount",
)
@inject
async def update_loan_amount(
    loan_id: int,
    new_amount: float = Body(..., embed=True, ge=0),
    db: AsyncSession = Depends(get_db),
    service: LoanService = Depends(
        Provide[ApplicationContainer.api_container.loan_service]
    ),
):
    logger.info(f"[LoanRouter] update_amount id={loan_id} new_amount={new_amount}")
    try:
        return await service.update_amount(loan_id, new_amount, db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[LoanRouter] update_amount error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update loan amount")


@router.delete(
    "/by-id/{loan_id}",
    response_model=Dict[str, str],
    summary="Delete loan",
)
@inject
async def delete_loan(
    loan_id: int,
    db: AsyncSession = Depends(get_db),
    service: LoanService = Depends(
        Provide[ApplicationContainer.api_container.loan_service]
    ),
):
    logger.warning(f"[LoanRouter] delete id={loan_id}")
    try:
        ok = await service.delete(loan_id, db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[LoanRouter] delete error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete loan")

    if not ok:
        raise HTTPException(status_code=404, detail="Loan not found")
    return {"message": f"Loan with ID {loan_id} deleted successfully"}
