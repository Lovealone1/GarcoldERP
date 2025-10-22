from typing import Any, Dict, List, cast
from fastapi import (
    APIRouter, 
    Depends, 
    HTTPException, 
    Query, 
    status, 
    Path, 
    Body
    )
from dependency_injector.wiring import inject, Provide
from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.database.db_connector import get_db
from app.app_containers import ApplicationContainer
from app.v1_0.schemas.auth_admin import (
    InviteUserIn,
    CreateUserIn,
    AdminUserOut,
    AdminUsersPage,
    SetUserRoleIn, 
    UpdateUserIn, 
    SetUserActiveIn
)
from app.v1_0.services import SupabaseAdminService, UserService
from app.v1_0.entities import UserDTO
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
    
@router.patch("/users/{sub}/role", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def set_user_role_by_sub(
    body: SetUserRoleIn,
    sub: str = Path(..., description="external_sub del usuario"),
    db: AsyncSession = Depends(get_db),
    svc: UserService = Depends(Provide[ApplicationContainer.api_container.user_service]),
):
    try:
        await svc.set_role_by_sub(sub=sub, role_id=body.role_id, db=db)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

@router.put(
    "/{user_id}",
    response_model=AdminUserOut,
    status_code=status.HTTP_200_OK,
    summary="Update a Supabase user and sync Neon",
)
@inject
async def update_user(
    user_id: str,
    body: UpdateUserIn = Body(...),
    supa: SupabaseAdminService = Depends(Provide[ApplicationContainer.api_container.supabase_admin_service]),
    db: AsyncSession = Depends(get_db),
    user_svc: UserService = Depends(Provide[ApplicationContainer.api_container.user_service]),
):
    try:
        if body.full_name is not None and body.name is None:
            body.name = body.full_name
        elif body.name is not None and body.full_name is None:
            body.full_name = body.name

        updated: Dict[str, Any] = await supa.update(user_id, body)

        if body.email is not None or body.name is not None or body.full_name is not None:
            name_for_local = body.full_name or body.name
            email_for_local = body.email or updated.get("email")
            await user_svc.upsert_basics_by_sub(
                sub=user_id, email=email_for_local, name=name_for_local, db=db
            )

        return AdminUserOut(**updated)
    except HTTPException:
        raise
    except Exception as e:
        try: await db.rollback()
        except: pass
        raise HTTPException(status_code=502, detail=str(e))

@router.get(
    "/users/local",
    response_model=List[UserDTO],
    status_code=status.HTTP_200_OK,
    summary="Listar usuarios locales (Neon) con rol resuelto",
)
@inject
async def list_local_users(
    db: AsyncSession = Depends(get_db),
    svc: UserService = Depends(Provide[ApplicationContainer.api_container.user_service]),
):
    try:
        return await svc.list_users_full(db=db)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get(
    "/users/{sub}",
    response_model=UserDTO,
    status_code=status.HTTP_200_OK,
    summary="Obtener usuario local por external_sub",
)
@inject
async def get_user_by_sub(
    sub: str = Path(..., description="external_sub del usuario"),
    db: AsyncSession = Depends(get_db),
    svc: UserService = Depends(Provide[ApplicationContainer.api_container.user_service]),
):
    try:
        return await svc.get_user_full_by_sub(sub=sub, db=db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.patch(
    "/users/{sub}/active",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Actualizar estado is_active del usuario local",
)
@inject
async def set_user_active(
    body: SetUserActiveIn,
    sub: str = Path(..., description="external_sub del usuario"),
    db: AsyncSession = Depends(get_db),
    svc: UserService = Depends(Provide[ApplicationContainer.api_container.user_service]),
):
    try:
        await svc.set_active_by_sub(sub=sub, is_active=body.is_active, db=db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))