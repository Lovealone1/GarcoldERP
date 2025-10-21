from typing import Any, Dict
from fastapi import APIRouter, HTTPException, Depends, Body, status
from sqlalchemy.ext.asyncio import AsyncSession
from dependency_injector.wiring import inject, Provide

from app.storage.database.db_connector import get_db
from app.app_containers import ApplicationContainer
from app.core.logger import logger

from app.v1_0.entities import CompanyDTO
from app.v1_0.services import CompanyService

router = APIRouter(prefix="/company", tags=["Company"])


@router.get(
    "/",
    response_model=CompanyDTO,
    summary="Get company",
)
@inject
async def get_company(
    db: AsyncSession = Depends(get_db),
    company_service: CompanyService = Depends(
        Provide[ApplicationContainer.api_container.company_service]
    ),
) -> CompanyDTO:
    logger.debug("[CompanyRouter] get_company")
    try:
        dto = await company_service.get_company(db)
        if dto is None:
            raise HTTPException(status_code=404, detail="company_not_found")
        return dto
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[CompanyRouter] get_company error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get company")


@router.patch(
    "/",
    response_model=CompanyDTO,
    status_code=status.HTTP_200_OK,
    summary="Patch company",
)
@inject
async def patch_company(
    payload: Dict[str, Any] = Body(..., description="Partial company fields to update"),
    db: AsyncSession = Depends(get_db),
    company_service: CompanyService = Depends(
        Provide[ApplicationContainer.api_container.company_service]
    ),
) -> CompanyDTO:
    logger.info(f"[CompanyRouter] patch_company payload={payload}")
    try:
        dto = await company_service.patch_company(db, **payload)
        return dto
    except ValueError as e:
        # e.g., "company_not_found" o validaciones de dominio
        logger.warning(f"[CompanyRouter] patch_company validation_error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[CompanyRouter] patch_company error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to patch company")
