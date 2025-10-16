from typing import Dict
from fastapi import APIRouter, HTTPException, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from dependency_injector.wiring import inject, Provide

from app.storage.database.db_connector import get_db
from app.app_containers import ApplicationContainer
from app.core.logger import logger

from app.v1_0.schemas import ExpenseCreate
from app.v1_0.entities import ExpenseDTO, ExpensePageDTO
from app.v1_0.services import ExpenseService

router = APIRouter(prefix="/expenses", tags=["Expenses"])

@router.post(
    "/create",
    response_model=ExpenseDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new expense",
)
@inject
async def create_expense(
    request: ExpenseCreate,
    db: AsyncSession = Depends(get_db),
    service: ExpenseService = Depends(
        Provide[ApplicationContainer.api_container.expense_service]
    ),
) -> ExpenseDTO:
    logger.info(f"[ExpenseRouter] create payload={request.model_dump()}")
    try:
        return await service.create(request, db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ExpenseRouter] create error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create expense")

@router.delete(
    "/by-id/{expense_id}",
    response_model=Dict[str, str],
    summary="Delete an expense and revert bank balance",
)
@inject
async def delete_expense(
    expense_id: int,
    db: AsyncSession = Depends(get_db),
    service: ExpenseService = Depends(
        Provide[ApplicationContainer.api_container.expense_service]
    ),
):
    logger.warning(f"[ExpenseRouter] delete id={expense_id}")
    try:
        ok = await service.delete(expense_id, db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ExpenseRouter] delete error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete expense")

    if not ok:
        raise HTTPException(status_code=404, detail="Expense not found")

    return {"message": f"Expense with ID {expense_id} deleted successfully"}

@router.get(
    "/page",
    response_model=ExpensePageDTO,
    summary="List expenses (paginated)",
)
@inject
async def list_expenses_paginated(
    page: int = Query(1, ge=1, description="1-based page number"),
    db: AsyncSession = Depends(get_db),
    service: ExpenseService = Depends(
        Provide[ApplicationContainer.api_container.expense_service]
    ),
) -> ExpensePageDTO:
    logger.debug(f"[ExpenseRouter] list_paginated page={page}")
    try:
        return await service.list_paginated(page, db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ExpenseRouter] list_paginated error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list expenses")
