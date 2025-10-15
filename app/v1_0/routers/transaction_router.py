from typing import Dict
from fastapi import APIRouter, HTTPException, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from dependency_injector.wiring import inject, Provide

from app.storage.database.db_connector import get_db
from app.app_containers import ApplicationContainer
from app.v1_0.schemas import TransactionCreate
from app.v1_0.entities import TransactionDTO, TransactionPageDTO
from app.v1_0.services.transaction_service import TransactionService

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
    service: TransactionService = Depends(
        Provide[ApplicationContainer.api_container.transaction_service]
    ),
) -> TransactionDTO:
    return await service.create(payload, db)

@router.delete(
    "/delete/{transaction_id}",
    response_model=Dict[str, str],
    summary="Delete a manual transaction and revert balance if applicable",
)
@inject
async def delete_transaction(
    transaction_id: int,
    db: AsyncSession = Depends(get_db),
    service: TransactionService = Depends(
        Provide[ApplicationContainer.api_container.transaction_service]
    ),
):
    ok = await service.delete_manual_transaction(transaction_id, db)
    if not ok:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return {"message": f"Transaction {transaction_id} deleted successfully"}

@router.get(
    "",
    response_model=TransactionPageDTO,
    summary="List manual transactions (paginated)",
)
@inject
async def list_transactions(
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    db: AsyncSession = Depends(get_db),
    service: TransactionService = Depends(
        Provide[ApplicationContainer.api_container.transaction_service]
    ),
) -> TransactionPageDTO:
    return await service.list_transactions(page, db)
