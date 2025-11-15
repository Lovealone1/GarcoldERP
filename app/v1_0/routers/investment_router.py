from typing import List, Dict, Any , Union
from fastapi import APIRouter, HTTPException, Depends, Body, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from dependency_injector.wiring import inject, Provide

from app.core.security.deps import AuthContext, get_auth_context
from app.core.security.realtime_auth import build_channel_id_from_auth
from app.storage.database.db_connector import get_db
from app.app_containers import ApplicationContainer
from app.core.logger import logger

from app.v1_0.schemas import InvestmentCreate, InvestmentAddBalanceIn, InvestmentWithdrawIn
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
    auth_ctx: AuthContext = Depends(get_auth_context),
    service: InvestmentService = Depends(
        Provide[ApplicationContainer.api_container.investment_service]
    ),
) -> InvestmentDTO:
    logger.info("[InvestmentRouter] create payload=%s", request.model_dump())
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
        logger.error(
            "[InvestmentRouter] create error: %s",
            e,
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to create investment",
        )



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
    auth_ctx: AuthContext = Depends(get_auth_context),
    service: InvestmentService = Depends(
        Provide[ApplicationContainer.api_container.investment_service]
    ),
) -> InvestmentDTO:
    logger.info(
        "[InvestmentRouter] update_balance id=%s new_balance=%s",
        investment_id,
        new_balance,
    )
    channel_id = build_channel_id_from_auth(auth_ctx)

    try:
        return await service.update_balance(
            investment_id=investment_id,
            new_balance=new_balance,
            db=db,
            channel_id=channel_id,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "[InvestmentRouter] update_balance error: %s",
            e,
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to update investment balance",
        )


@router.post(
    "/balance/add",
    status_code=status.HTTP_200_OK,
    response_model=InvestmentDTO,
    summary="Add values to investment as interest or topup",
)
@inject
async def add_investment_balance(
    payload: InvestmentAddBalanceIn,
    db: AsyncSession = Depends(get_db),
    auth_ctx: AuthContext = Depends(get_auth_context),
    service: InvestmentService = Depends(
        Provide[ApplicationContainer.api_container.investment_service]
    ),
) -> InvestmentDTO:
    logger.info(
        "[InvestmentRouter] add_balance investment_id=%s kind=%s amount=%s",
        payload.investment_id,
        payload.kind,
        payload.amount,
    )
    channel_id = build_channel_id_from_auth(auth_ctx)

    try:
        return await service.add_balance(
            payload=payload,
            db=db,
            channel_id=channel_id,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "[InvestmentRouter] add_balance error: %s",
            e,
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to add balance",
        )


@router.post(
    "/withdraw",
    response_model=Union[InvestmentDTO, Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Withdraw values partial or full, if balance is 0 the investment is eliminated",
)
@inject
async def withdraw_investment(
    payload: InvestmentWithdrawIn,
    db: AsyncSession = Depends(get_db),
    auth_ctx: AuthContext = Depends(get_auth_context),
    service: InvestmentService = Depends(
        Provide[ApplicationContainer.api_container.investment_service]
    ),
) -> Union[InvestmentDTO, Dict[str, Any]]:
    logger.info(
        "[InvestmentRouter] withdraw id=%s kind=%s amount=%s dest_bank=%s",
        payload.investment_id,
        payload.kind,
        getattr(payload, "amount", None),
        getattr(payload, "destination_bank_id", None),
    )
    channel_id = build_channel_id_from_auth(auth_ctx)

    try:
        res = await service.withdraw(
            payload=payload,
            db=db,
            channel_id=channel_id,
        )
        if res is None:
            return {
                "deleted": True,
                "investment_id": payload.investment_id,
            }
        return res
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "[InvestmentRouter] withdraw error: %s",
            e,
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to withdraw from investment",
        )


@router.delete(
    "/by-id/{investment_id}",
    response_model=Dict[str, str],
    summary="Delete investment",
)
@inject
async def delete_investment(
    investment_id: int,
    db: AsyncSession = Depends(get_db),
    auth_ctx: AuthContext = Depends(get_auth_context),
    service: InvestmentService = Depends(
        Provide[ApplicationContainer.api_container.investment_service]
    ),
) -> Dict[str, str]:
    logger.warning(
        "[InvestmentRouter] delete id=%s",
        investment_id,
    )
    channel_id = build_channel_id_from_auth(auth_ctx)

    try:
        ok = await service.delete(
            investment_id=investment_id,
            db=db,
            channel_id=channel_id,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "[InvestmentRouter] delete error: %s",
            e,
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to delete investment",
        )

    if not ok:
        raise HTTPException(
            status_code=404,
            detail="Investment not found",
        )

    return {
        "message": f"Investment with ID {investment_id} deleted successfully"
    }