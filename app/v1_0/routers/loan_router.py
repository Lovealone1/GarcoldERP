from typing import List, Dict, Union, Any
from fastapi import APIRouter, HTTPException, Depends, Body, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from dependency_injector.wiring import inject, Provide


from app.core.security.deps import AuthContext, get_auth_context
from app.core.security.realtime_auth import build_channel_id_from_auth
from app.storage.database.db_connector import get_db
from app.app_containers import ApplicationContainer
from app.core.logger import logger

from app.v1_0.schemas import LoanCreate, LoanApplyPaymentIn
from app.v1_0.entities import LoanDTO, LoanPageDTO
from app.v1_0.services import LoanService

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
    auth_ctx: AuthContext = Depends(get_auth_context),
    service: LoanService = Depends(
        Provide[ApplicationContainer.api_container.loan_service]
    ),
) -> LoanDTO:
    logger.info("[LoanRouter] create payload=%s", request.model_dump())
    channel_id = build_channel_id_from_auth(auth_ctx)

    try:
        return await service.create(
            payload=request,
            db=db,
            channel_id=channel_id,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[LoanRouter] create error: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to create loan",
        )


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
    auth_ctx: AuthContext = Depends(get_auth_context),
    service: LoanService = Depends(
        Provide[ApplicationContainer.api_container.loan_service]
    ),
) -> LoanDTO:
    logger.info(
        "[LoanRouter] update_amount id=%s new_amount=%s",
        loan_id,
        new_amount,
    )
    channel_id = build_channel_id_from_auth(auth_ctx)

    try:
        return await service.update_amount(
            loan_id=loan_id,
            new_amount=new_amount,
            db=db,
            channel_id=channel_id,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[LoanRouter] update_amount error: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to update loan amount",
        )


@router.delete(
    "/by-id/{loan_id}",
    response_model=Dict[str, str],
    summary="Delete loan",
)
@inject
async def delete_loan(
    loan_id: int,
    db: AsyncSession = Depends(get_db),
    auth_ctx: AuthContext = Depends(get_auth_context),
    service: LoanService = Depends(
        Provide[ApplicationContainer.api_container.loan_service]
    ),
) -> Dict[str, str]:
    logger.warning("[LoanRouter] delete id=%s", loan_id)
    channel_id = build_channel_id_from_auth(auth_ctx)

    try:
        ok = await service.delete(
            loan_id=loan_id,
            db=db,
            channel_id=channel_id,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[LoanRouter] delete error: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to delete loan",
        )

    if not ok:
        raise HTTPException(
            status_code=404,
            detail="Loan not found",
        )

    return {
        "message": f"Loan with ID {loan_id} deleted successfully"
    }


@router.post(
    "/apply-payment",
    response_model=Union[LoanDTO, Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Apply a payment into loan and discount from the bank",
)
@inject
async def apply_payment(
    payload: LoanApplyPaymentIn,
    db: AsyncSession = Depends(get_db),
    auth_ctx: AuthContext = Depends(get_auth_context),
    service: LoanService = Depends(
        Provide[ApplicationContainer.api_container.loan_service]
    ),
) -> Union[LoanDTO, Dict[str, Any]]:
    logger.info(
        "[LoanRouter] apply_payment loan_id=%s amount=%s bank_id=%s",
        payload.loan_id,
        payload.amount,
        payload.bank_id,
    )
    channel_id = build_channel_id_from_auth(auth_ctx)

    try:
        res = await service.apply_payment(
            payload=payload,
            db=db,
            channel_id=channel_id,
        )
        if res is None:
            return {
                "deleted": True,
                "loan_id": payload.loan_id,
            }
        return res
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "[LoanRouter] apply_payment error: %s",
            e,
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to apply loan payment",
        )