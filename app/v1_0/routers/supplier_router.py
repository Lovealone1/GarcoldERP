from typing import Dict, List, Any
from fastapi import APIRouter, HTTPException, Depends, Body, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from dependency_injector.wiring import inject, Provide

from app.storage.database.db_connector import get_db
from app.app_containers import ApplicationContainer
from app.core.logger import logger

from app.v1_0.schemas import SupplierCreate
from app.v1_0.entities import SupplierDTO, SupplierPageDTO
from app.v1_0.services import SupplierService

router = APIRouter(prefix="/suppliers", tags=["Suppliers"])

@router.post(
    "/create",
    response_model=SupplierDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new supplier",
)
@inject
async def create_supplier(
    request: SupplierCreate,
    db: AsyncSession = Depends(get_db),
    service: SupplierService = Depends(Provide[ApplicationContainer.api_container.supplier_service]),
):
    logger.info(f"[SupplierRouter] create payload={request.model_dump()}")
    try:
        return await service.create(request, db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[SupplierRouter] create error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create supplier")

@router.get(
    "/by-id/{supplier_id}",
    response_model=SupplierDTO,
    summary="Get supplier by ID",
)
@inject
async def get_supplier(
    supplier_id: int,
    db: AsyncSession = Depends(get_db),
    service: SupplierService = Depends(Provide[ApplicationContainer.api_container.supplier_service]),
):
    logger.debug(f"[SupplierRouter] get id={supplier_id}")
    try:
        return await service.get(supplier_id, db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[SupplierRouter] get error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch supplier")

@router.get(
    "",
    response_model=List[SupplierDTO],
    summary="List all suppliers",
)
@inject
async def list_suppliers(
    db: AsyncSession = Depends(get_db),
    service: SupplierService = Depends(Provide[ApplicationContainer.api_container.supplier_service]),
):
    logger.debug("[SupplierRouter] list_all")
    try:
        return await service.list_all(db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[SupplierRouter] list_all error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list suppliers")

@router.get(
    "/page",
    response_model=SupplierPageDTO,
    summary="List suppliers paginated",
)
@inject
async def list_suppliers_paginated(
    page: int = Query(1, ge=1),
    db: AsyncSession = Depends(get_db),
    service: SupplierService = Depends(Provide[ApplicationContainer.api_container.supplier_service]),
):
    logger.debug(f"[SupplierRouter] list_paginated page={page}")
    try:
        return await service.list_paginated(page, db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[SupplierRouter] list_paginated error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list suppliers")

@router.patch(
    "/by-id/{supplier_id}",
    response_model=SupplierDTO,
    summary="Update supplier (partial)",
)
@inject
async def update_supplier(
    supplier_id: int,
    data: Dict[str, Any] = Body(..., description="Partial fields to update"),
    db: AsyncSession = Depends(get_db),
    service: SupplierService = Depends(Provide[ApplicationContainer.api_container.supplier_service]),
):
    logger.info(f"[SupplierRouter] update id={supplier_id} data={data}")
    try:
        return await service.update_partial(supplier_id, data, db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[SupplierRouter] update error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update supplier")

@router.delete(
    "/by-id/{supplier_id}",
    response_model=Dict[str, str],
    summary="Delete a supplier",
)
@inject
async def delete_supplier(
    supplier_id: int,
    db: AsyncSession = Depends(get_db),
    service: SupplierService = Depends(Provide[ApplicationContainer.api_container.supplier_service]),
):
    logger.warning(f"[SupplierRouter] delete id={supplier_id}")
    try:
        ok = await service.delete(supplier_id, db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[SupplierRouter] delete error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete supplier")

    if not ok:
        raise HTTPException(status_code=404, detail="Supplier not found")

    return {"message": f"Supplier with ID {supplier_id} deleted successfully"}
