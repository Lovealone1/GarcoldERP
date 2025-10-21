from typing import Any, Dict, List, cast
from fastapi import APIRouter, Depends, HTTPException, Query, status
from dependency_injector.wiring import inject, Provide
from app.app_containers import ApplicationContainer

from app.v1_0.schemas.auth_admin import (
    InviteUserIn,
    CreateUserIn,
    AdminUserOut,
    AdminUsersPage,
)
from app.v1_0.services import SupabaseAdminService

router = APIRouter(prefix="/admin", tags=["admin-users"])

@router.get(
    "",
    response_model=AdminUsersPage,
    status_code=status.HTTP_200_OK,
    summary="List Supabase users",
)
@inject
async def list_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    email: str | None = Query(None),
    service: SupabaseAdminService = Depends(Provide[ApplicationContainer.api_container.supabase_admin_service]),
):
    try:
        data: Dict[str, Any] = await service.list_users(page=page, per_page=per_page, email=email)
        items_raw = cast(List[Dict[str, Any]], data["items"])
        items = [AdminUserOut(**u) for u in items_raw]
        return AdminUsersPage(
            items=items,
            page=cast(int, data["page"]),
            per_page=cast(int, data["per_page"]),
            has_next=cast(bool, data["has_next"]),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

@router.post(
    "/invite",
    response_model=AdminUserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Invite a user via Supabase",
)
@inject
async def invite_user(
    body: InviteUserIn,
    service: SupabaseAdminService = Depends(Provide[ApplicationContainer.api_container.supabase_admin_service]),
):
    try:
        data = await service.invite(body)
        return AdminUserOut(**data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

@router.post(
    "/create",
    response_model=AdminUserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a user in Supabase",
)
@inject
async def create_user(
    body: CreateUserIn,
    service: SupabaseAdminService = Depends(Provide[ApplicationContainer.api_container.supabase_admin_service]),
):
    try:
        data = await service.create(body)
        return AdminUserOut(**data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a user in Supabase",
)
@inject
async def delete_user(
    user_id: str,
    service: SupabaseAdminService = Depends(Provide[ApplicationContainer.api_container.supabase_admin_service]),
):
    try:
        await service.delete(user_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
