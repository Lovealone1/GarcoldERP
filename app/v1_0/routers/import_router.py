from typing import Optional
from fastapi import (
    APIRouter, HTTPException, Depends, status, UploadFile, File, Query
)
from dependency_injector.wiring import inject, Provide
from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.database.db_connector import get_db
from app.app_containers import ApplicationContainer
from app.core.logger import logger
from app.v1_0.services import ImportService
from app.v1_0.helper.io import ImportOptions, Entity  

router = APIRouter(prefix="/io", tags=["Import"])

MAX_MB = 10
MAX_BYTES = MAX_MB * 1024 * 1024
CSV_XLSX_CT = {
    "text/csv",
    "application/csv",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}

def _ext(name: str) -> str:
    return name.rsplit(".", 1)[-1].lower() if "." in name else ""

@router.post(
    "/import",
    status_code=status.HTTP_200_OK,
    summary="Massive import of customers, suppliers or products",
)
@inject
async def import_insert_endpoint(
    entity: Entity = Query(..., description="customers | suppliers | products"),
    dry_run: bool = Query(True),
    delimiter: Optional[str] = Query(None, description="Ej: ',' ';' o 'tab'"),
    sheet: Optional[str] = Query(None, description="Nombre de hoja para .xlsx"),
    header_row: int = Query(1, ge=1),
    file: UploadFile = File(..., description=".csv o .xlsx"),
    db: AsyncSession = Depends(get_db),
    svc: ImportService = Depends(Provide[ApplicationContainer.api_container.import_service]),
):
    if not file.filename:
        raise HTTPException(400, "filename requerido")
    if _ext(file.filename) not in {"csv", "xlsx"}:
        raise HTTPException(415, "Solo .csv o .xlsx")

    peek = await file.read()
    if not peek:
        raise HTTPException(400, "archivo vacío")
    if len(peek) > MAX_BYTES:
        raise HTTPException(413, f"archivo excede {MAX_MB}MB")
    file.file.seek(0)

    ct = (file.content_type or "").split(";")[0].strip().lower()
    if ct and ct not in CSV_XLSX_CT:
        logger.debug(f"[IO Import] content-type atípico: {ct} (continuando por extensión)")

    opts = ImportOptions(
        entity=entity,
        dry_run=dry_run,
        delimiter={None: None, "tab": "\t"}.get(delimiter, delimiter),
        sheet=sheet,
        header_row=header_row,
    )

    try:
        result = await svc.import_insert(file=file, opts=opts, db=db)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[IO Import] fallo inesperado: {e}", exc_info=True)
        raise HTTPException(500, "fallo en importación")
