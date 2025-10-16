from typing import Literal
from fastapi import APIRouter, Depends, Query, HTTPException
from dependency_injector.wiring import inject, Provide
from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.database.db_connector import get_db
from app.app_containers import ApplicationContainer
from app.v1_0.services import ExportService

Fmt = Literal["csv", "xlsx"]

router = APIRouter(
    prefix="/export",
    tags=["Export"],
    responses={200: {"content": {
        "text/csv": {},
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {}
    }}},
)

@router.get("", summary="Exporta customers/products/suppliers")
@inject
async def export_any(
    entity: Literal["customers","products","suppliers"] = Query(...),
    fmt: Fmt = Query("csv"),
    db: AsyncSession = Depends(get_db),
    svc: ExportService = Depends(Provide[ApplicationContainer.api_container.export_service]),
):
    if entity == "customers":
        return await svc.export_customers(db, fmt)
    if entity == "products":
        return await svc.export_products(db, fmt)
    if entity == "suppliers":
        return await svc.export_suppliers(db, fmt)
    raise HTTPException(status_code=400, detail="Entidad no soportada")

