from typing import Dict, List
from fastapi import APIRouter, HTTPException, Depends, Body, status
from sqlalchemy.ext.asyncio import AsyncSession
from dependency_injector.wiring import inject, Provide

from app.storage.database.db_connector import get_db
from app.app_containers import ApplicationContainer
from app.core.logger import logger

from app.v1_0.schemas import BankCreate
from app.v1_0.entities import BankDTO
from app.v1_0.services.bank_service import BankService

router = APIRouter(prefix="/banks", tags=["Banks"])


@router.post(
    "/create",
    response_model=BankDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new bank",
)
@inject
async def create_bank(
    request: BankCreate,
    db: AsyncSession = Depends(get_db),
    bank_service: BankService = Depends(
        Provide[ApplicationContainer.api_container.bank_service]
    ),
):
    logger.info(f"[BankRouter] create_bank payload={request.model_dump()}")
    try:
        created = await bank_service.create_bank(request, db)
    except ValueError as e:
        logger.warning(f"[BankRouter] create_bank validation_error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[BankRouter] create_bank error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create bank")

    return BankDTO(
        id=created.id,
        name=created.name,
        balance=created.balance, 
        created_at=created.created_at,
        updated_at=created.updated_at,
        account_number=created.account_number
    )


@router.get(
    "/",
    response_model=List[BankDTO],
    summary="List all banks",
)
@inject
async def list_banks(
    db: AsyncSession = Depends(get_db),
    bank_service: BankService = Depends(
        Provide[ApplicationContainer.api_container.bank_service]
    ),
) -> List[BankDTO]:
    logger.debug("[BankRouter] list_banks")
    try:
        banks = await bank_service.get_all_banks(db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[BankRouter] list_banks error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list banks")

    return [
        BankDTO(
        id=b.id,
        name=b.name,
        balance=b.balance, 
        created_at=b.created_at,
        updated_at=b.updated_at,
        account_number=b.account_number
        )
        for b in banks
    ]


@router.patch(
    "/balance/{bank_id}",
    response_model=BankDTO,
    summary="Update bank balance only",
)
@inject
async def update_bank_balance(
    bank_id: int,
    new_balance: float = Body(..., embed=True, description="New balance"),
    db: AsyncSession = Depends(get_db),
    bank_service: BankService = Depends(
        Provide[ApplicationContainer.api_container.bank_service]
    ),
):
    logger.info(f"[BankRouter] update_bank_balance id={bank_id} new_balance={new_balance}")
    try:
        bank = await bank_service.update_balance(bank_id, new_balance, db)
        if not bank:
            raise HTTPException(status_code=404, detail="Bank not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[BankRouter] update_bank_balance error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update balance")

    return BankDTO(
        id=bank.id,
        name=bank.name if hasattr(bank, "name") else bank.name,
        balance=bank.balance if hasattr(bank, "balance") else bank.balance,
        created_at=bank.created_at,
        updated_at=bank.updated_at,
        account_number=bank.account_number
    )

@router.delete(
    "/{bank_id}",
    response_model=Dict[str, str],
    summary="Delete a bank",
)
@inject
async def delete_bank(
    bank_id: int,
    db: AsyncSession = Depends(get_db),
    bank_service: BankService = Depends(
        Provide[ApplicationContainer.api_container.bank_service]
    ),
):
    logger.warning(f"[BankRouter] delete_bank id={bank_id}")
    try:
        ok = await bank_service.delete_bank(bank_id, db)
    except ValueError as e:
        logger.warning(f"[BankRouter] delete_bank blocked: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[BankRouter] delete_bank error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete bank")

    if not ok:
        raise HTTPException(status_code=404, detail="Bank not found")

    return {"message": f"Bank with ID {bank_id} deleted successfully"}