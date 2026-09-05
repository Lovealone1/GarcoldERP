from datetime import datetime
from typing import Dict, List, Literal, Optional

from fastapi import APIRouter, HTTPException, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from dependency_injector.wiring import inject, Provide

from app.core.security.deps import AuthContext, get_auth_context
from app.core.security.realtime_auth import build_channel_id_from_auth
from app.core.logger import logger
from app.storage.database.db_connector import get_db

from app.app_containers import ApplicationContainer
from app.utils.date_utils import Period
from app.v1_0.schemas import TransactionCreate
from app.v1_0.entities import TransactionDTO, TransactionPageDTO
from app.v1_0.services import TransactionService
from .period_params import period_range

router = APIRouter(prefix="/transactions", tags=["Transactions"])

@router.post(
    "/create",
    response_model=TransactionDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Create a manual transaction",
)
@inject
async def create_transaction(
    payload: TransactionCreate,
    db: AsyncSession = Depends(get_db),
    auth_ctx: AuthContext = Depends(get_auth_context),
    service: TransactionService = Depends(
        Provide[ApplicationContainer.api_container.transaction_service]
    ),
) -> TransactionDTO:
    logger.info("[TransactionRouter] create payload=%s", payload.model_dump())
    channel_id = build_channel_id_from_auth(auth_ctx)

    try:
        return await service.create(
            payload=payload,
            db=db,
            channel_id=channel_id,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "[TransactionRouter] create error: %s",
            e,
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to create transaction",
        )


@router.delete(
    "/delete/{transaction_id}",
    response_model=Dict[str, str],
    summary="Delete a manual transaction and revert balance if applicable",
)
@inject
async def delete_transaction(
    transaction_id: int,
    db: AsyncSession = Depends(get_db),
    auth_ctx: AuthContext = Depends(get_auth_context),
    service: TransactionService = Depends(
        Provide[ApplicationContainer.api_container.transaction_service]
    ),
) -> Dict[str, str]:
    logger.info("[TransactionRouter] delete id=%s", transaction_id)
    channel_id = build_channel_id_from_auth(auth_ctx)

    try:
        ok = await service.delete_manual_transaction(
            transaction_id=transaction_id,
            db=db,
            channel_id=channel_id,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "[TransactionRouter] delete error: %s",
            e,
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to delete transaction",
        )

    if not ok:
        raise HTTPException(
            status_code=404,
            detail="Transaction not found",
        )

    return {
        "message": f"Transaction {transaction_id} deleted successfully"
    }

@router.get(
    "/filter-options",
    response_model=Dict[str, List[str]],
    summary="Distinct bank and type names present in transactions",
)
@inject
async def transaction_filter_options(
    db: AsyncSession = Depends(get_db),
    service: TransactionService = Depends(
        Provide[ApplicationContainer.api_container.transaction_service]
    ),
) -> Dict[str, List[str]]:
    """
    Feeds the screen's filter dropdowns.

    They used to be derived from whatever rows the client had downloaded, which
    only worked because it downloaded everything.
    """
    return await service.list_filter_options(db)


@router.get(
    "/summary",
    response_model=Dict[str, float],
    summary="Total amount per type for the current filter",
)
@inject
async def transaction_summary(
    q: Optional[str] = Query(None),
    bank: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    origin: Optional[Literal["all", "auto", "manual"]] = Query("all"),
    period: Period = Depends(period_range),
    db: AsyncSession = Depends(get_db),
    service: TransactionService = Depends(
        Provide[ApplicationContainer.api_container.transaction_service]
    ),
) -> Dict[str, float]:
    """
    Totals over the whole filtered set, not just the visible page.

    The extract panel used to sum the rows the client had downloaded, which
    only agreed with reality because the client downloaded every page.
    """
    return await service.summarize(
        db,
        q=q,
        bank=bank,
        type_name=type,
        origin=None if origin == "all" else origin,
        date_from=period.date_from,
        date_to=period.date_to,
    )


@router.get(
    "",
    response_model=TransactionPageDTO,
    summary="List transactions (paginated, filtered server-side)",
)
@inject
async def list_transactions(
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: Optional[int] = Query(None, ge=1, le=100),
    q: Optional[str] = Query(None, description="Matches id, description, bank or type"),
    bank: Optional[str] = Query(None, description="Exact bank name"),
    type: Optional[str] = Query(None, description="Exact transaction type name"),
    origin: Optional[Literal["all", "auto", "manual"]] = Query("all"),
    period: Period = Depends(period_range),
    db: AsyncSession = Depends(get_db),
    service: TransactionService = Depends(
        Provide[ApplicationContainer.api_container.transaction_service]
    ),
) -> TransactionPageDTO:
    """
    Filtering happens here rather than in the browser.

    The client previously walked every page to build a complete local copy and
    filtered that -- hundreds of sequential requests for a few visible rows.
    """
    return await service.list_transactions(
        page,
        db,
        page_size=page_size,
        q=q,
        bank=bank,
        type_name=type,
        origin=None if origin == "all" else origin,
        date_from=period.date_from,
        date_to=period.date_to,
    )
