from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Body, status
from sqlalchemy.ext.asyncio import AsyncSession
from dependency_injector.wiring import inject, Provide

from app.utils.database.db_connector import get_db
from app.app_containers import ApplicationContainer
from app.core.logger import logger

from app.v1_0.schemas import ExpenseCategoryCreate
from app.v1_0.entities import ExpenseCategoryDTO
from app.v1_0.services.expense_category_service import ExpenseCategoryService

router = APIRouter(prefix="/expense-categories", tags=["Expense Categories"])

@router.post(
    "/create",
    response_model=ExpenseCategoryDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new expense category",
)
@inject
async def create_expense_category(
    request: ExpenseCategoryCreate,
    db: AsyncSession = Depends(get_db),
    service: ExpenseCategoryService = Depends(
        Provide[ApplicationContainer.api_container.expense_category_service]
    ),
):
    logger.info(f"[ExpenseCategoryRouter] create payload={request.model_dump()}")
    try:
        return await service.create(request, db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ExpenseCategoryRouter] create error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create expense category")

@router.get(
    "/by-id/{category_id}",
    response_model=ExpenseCategoryDTO,
    summary="Get expense category by ID",
)
@inject
async def get_expense_category(
    category_id: int,
    db: AsyncSession = Depends(get_db),
    service: ExpenseCategoryService = Depends(
        Provide[ApplicationContainer.api_container.expense_category_service]
    ),
):
    logger.debug(f"[ExpenseCategoryRouter] get id={category_id}")
    try:
        return await service.get(category_id, db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ExpenseCategoryRouter] get error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch expense category")

@router.get(
    "",
    response_model=List[ExpenseCategoryDTO],
    summary="List all expense categories",
)
@inject
async def list_expense_categories(
    db: AsyncSession = Depends(get_db),
    service: ExpenseCategoryService = Depends(
        Provide[ApplicationContainer.api_container.expense_category_service]
    ),
):
    logger.debug("[ExpenseCategoryRouter] list_all")
    try:
        return await service.list_all(db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ExpenseCategoryRouter] list_all error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list expense categories")

@router.delete(
    "/by-id/{category_id}",
    response_model=Dict[str, Any],
    summary="Delete an expense category",
)
@inject
async def delete_expense_category(
    category_id: int,
    db: AsyncSession = Depends(get_db),
    service: ExpenseCategoryService = Depends(
        Provide[ApplicationContainer.api_container.expense_category_service]
    ),
):
    logger.warning(f"[ExpenseCategoryRouter] delete id={category_id}")
    try:
        ok = await service.delete(category_id, db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ExpenseCategoryRouter] delete error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete expense category")

    if not ok:
        raise HTTPException(status_code=404, detail="Expense category not found")

    return {"message": f"Expense category with ID {category_id} deleted successfully"}
