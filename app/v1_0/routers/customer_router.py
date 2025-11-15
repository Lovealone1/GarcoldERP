from typing import Dict, List
from fastapi import APIRouter, HTTPException, Depends, Body, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from dependency_injector.wiring import inject, Provide

from app.core.security.deps import AuthContext, get_auth_context
from app.core.security.realtime_auth import build_channel_id_from_auth
from app.storage.database.db_connector import get_db
from app.app_containers import ApplicationContainer
from app.core.logger import logger

from app.v1_0.schemas import CustomerCreate, CustomerUpdate, StandalonePaymentIn
from app.v1_0.entities import CustomerDTO, CustomerPageDTO
from app.v1_0.services import CustomerService

router = APIRouter(prefix="/customers", tags=["Customers"])

@router.post(
    "/create",
    response_model=CustomerDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new customer",
)
@inject
async def create_customer(
    request: CustomerCreate,
    db: AsyncSession = Depends(get_db),
    auth_ctx: AuthContext = Depends(get_auth_context),
    service: CustomerService = Depends(
        Provide[ApplicationContainer.api_container.customer_service]
    ),
) -> CustomerDTO:
    logger.info(
        "[CustomerRouter] create payload=%s",
        request.model_dump(),
    )
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
            "[CustomerRouter] create error: %s",
            e,
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to create customer",
        )

@router.get(
    "/by-id/{customer_id}",
    response_model=CustomerDTO,
    summary="Get customer by ID",
)
@inject
async def get_customer(
    customer_id: int,
    db: AsyncSession = Depends(get_db),
    service: CustomerService = Depends(
        Provide[ApplicationContainer.api_container.customer_service]
    ),
):
    logger.debug(f"[CustomerRouter] get id={customer_id}")
    try:
        return await service.get(customer_id, db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[CustomerRouter] get error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch customer")

@router.get(
    "",
    response_model=List[CustomerDTO],
    summary="List all customers",
)
@inject
async def list_customers(
    db: AsyncSession = Depends(get_db),
    service: CustomerService = Depends(
        Provide[ApplicationContainer.api_container.customer_service]
    ),
):
    logger.debug("[CustomerRouter] list_all")
    try:
        return await service.list_all(db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[CustomerRouter] list_all error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list customers")

@router.get(
    "/page",
    response_model=CustomerPageDTO,
    summary="List customers paginated",
)
@inject
async def list_customers_paginated(
    page: int = Query(1, ge=1),
    db: AsyncSession = Depends(get_db),
    service: CustomerService = Depends(
        Provide[ApplicationContainer.api_container.customer_service]
    ),
):
    logger.debug(f"[CustomerRouter] list_paginated page={page}")
    try:
        return await service.list_paginated(page, db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[CustomerRouter] list_paginated error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list customers")

@router.patch(
    "/by-id/{customer_id}",
    response_model=CustomerDTO,
    summary="Update customer",
)
@inject
async def update_customer(
    customer_id: int,
    data: CustomerUpdate,
    db: AsyncSession = Depends(get_db),
    auth_ctx: AuthContext = Depends(get_auth_context),
    service: CustomerService = Depends(
        Provide[ApplicationContainer.api_container.customer_service]
    ),
) -> CustomerDTO:
    logger.info(
        "[CustomerRouter] update id=%s data=%s",
        customer_id,
        data.model_dump(exclude_unset=True),
    )
    channel_id = build_channel_id_from_auth(auth_ctx)

    try:
        return await service.update_partial(
            customer_id=customer_id,
            payload=data,
            db=db,
            channel_id=channel_id,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "[CustomerRouter] update error: %s",
            e,
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to update customer",
        )

@router.patch(
    "/by-id/{customer_id}/balance",
    response_model=CustomerDTO,
    summary="Update customer balance",
)
@inject
async def update_customer_balance(
    customer_id: int,
    new_balance: float = Body(..., embed=True, description="New balance"),
    db: AsyncSession = Depends(get_db),
    auth_ctx: AuthContext = Depends(get_auth_context),
    service: CustomerService = Depends(
        Provide[ApplicationContainer.api_container.customer_service]
    ),
) -> CustomerDTO:
    logger.info(
        "[CustomerRouter] update_balance id=%s new_balance=%s",
        customer_id,
        new_balance,
    )
    channel_id = build_channel_id_from_auth(auth_ctx)

    try:
        return await service.update_balance(
            customer_id=customer_id,
            new_balance=new_balance,
            db=db,
            channel_id=channel_id,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "[CustomerRouter] update_balance error: %s",
            e,
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to update balance",
        )

@router.delete(
    "/by-id/{customer_id}",
    response_model=Dict[str, str],
    summary="Delete a customer",
)
@inject
async def delete_customer(
    customer_id: int,
    db: AsyncSession = Depends(get_db),
    auth_ctx: AuthContext = Depends(get_auth_context),
    service: CustomerService = Depends(
        Provide[ApplicationContainer.api_container.customer_service]
    ),
) -> Dict[str, str]:
    logger.warning(
        "[CustomerRouter] delete id=%s",
        customer_id,
    )
    channel_id = build_channel_id_from_auth(auth_ctx)

    try:
        ok = await service.delete(
            customer_id=customer_id,
            db=db,
            channel_id=channel_id,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "[CustomerRouter] delete error: %s",
            e,
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to delete customer",
        )

    if not ok:
        raise HTTPException(
            status_code=404,
            detail="Customer not found",
        )

    return {
        "message": f"Customer with ID {customer_id} deleted successfully"
    }


@router.post(
    "/by-id/{customer_id}/payments/simple",
    response_model=bool,
    summary="Register independent payment on the customer's balance",
)
@inject
async def create_simple_payment(
    customer_id: int,
    payload: StandalonePaymentIn,
    db: AsyncSession = Depends(get_db),
    auth_ctx: AuthContext = Depends(get_auth_context),
    service: CustomerService = Depends(
        Provide[ApplicationContainer.api_container.customer_service]
    ),
) -> bool:
    logger.info(
        "[CustomerRouter] simple_payment id=%s bank_id=%s amount=%s",
        customer_id,
        payload.bank_id,
        payload.amount,
    )
    channel_id = build_channel_id_from_auth(auth_ctx)

    try:
        ok = await service.register_simple_balance_payment(
            customer_id=customer_id,
            bank_id=payload.bank_id,
            amount=payload.amount,
            description=payload.description,
            db=db,
            channel_id=channel_id,
        )
        return ok
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "[CustomerRouter] simple_payment error: %s",
            e,
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to register payment",
        )