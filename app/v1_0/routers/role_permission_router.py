from typing import List, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from dependency_injector.wiring import inject, Provide

from app.storage.database.db_connector import get_db
from app.app_containers import ApplicationContainer
from app.core.logger import logger

from app.v1_0.schemas import (
    RolePermissionOut, RolePermissionStateIn, RolePermissionsBulkIn,
)
from app.v1_0.services.role_permission_service import RolePermissionService

router = APIRouter(prefix="/roles", tags=["Roles:Permissions"])

@router.get(
    "/{role_id}/permissions",
    response_model=List[RolePermissionOut],
    summary="List role permissions with state",
)
@inject
async def list_role_permissions(
    role_id: int,
    db: AsyncSession = Depends(get_db),
    svc: RolePermissionService = Depends(
        Provide[ApplicationContainer.api_container.role_permission_service]
    ),
):
    logger.debug(f"[RolePermRouter] list role_id={role_id}")
    try:
        return await svc.list_for_role(db, role_id)
    except Exception as e:
        logger.error(f"[RolePermRouter] list error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list permissions")

@router.patch(
    "/{role_id}/permissions/{code}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Activate/Deactivate a permission for a role",
)
@inject
async def set_permission_state(
    role_id: int,
    code: str,
    body: RolePermissionStateIn,
    db: AsyncSession = Depends(get_db),
    svc: RolePermissionService = Depends(
        Provide[ApplicationContainer.api_container.role_permission_service]
    ),
):
    logger.info(f"[RolePermRouter] set_state role_id={role_id} code={code} active={body.active}")
    try:
        await svc.set_state(db, role_id, code, body.active)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[RolePermRouter] set_state error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update state")

@router.post(
    "/{role_id}/permissions:bulk-set",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Bulk set permissions state for a role",
)
@inject
async def bulk_set_permissions(
    role_id: int,
    body: RolePermissionsBulkIn,
    db: AsyncSession = Depends(get_db),
    svc: RolePermissionService = Depends(
        Provide[ApplicationContainer.api_container.role_permission_service]
    ),
):
    logger.info(f"[RolePermRouter] bulk_set role_id={role_id} n={len(body.codes)} active={body.active}")
    try:
        await svc.bulk_set(db, role_id, body.codes, body.active)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[RolePermRouter] bulk_set error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to bulk set")
