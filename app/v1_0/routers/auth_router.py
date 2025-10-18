from typing import Dict
from fastapi import APIRouter, HTTPException, Depends, Header, status, Body
from sqlalchemy.ext.asyncio import AsyncSession
from dependency_injector.wiring import inject, Provide

from app.storage.database.db_connector import get_db
from app.app_containers import ApplicationContainer

from app.v1_0.entities import MeDTO, AuthSyncDTO
from app.v1_0.services import AuthService
from app.core.security._auth_helpers import require_claims, ensure_current_user

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/sync-self",
    response_model=MeDTO,
    status_code=status.HTTP_200_OK,
    summary="Sincroniza el usuario autenticado con la DB (provisión perezosa)",
)
@inject
async def sync_self(
    payload: Dict = Body(...),
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
    auth_service: AuthService = Depends(
        Provide[ApplicationContainer.api_container.auth_service]
    ),
) -> MeDTO:

    try:
        claims = await require_claims(authorization)

        user = await ensure_current_user(db, authorization, auth_service)

        dto = AuthSyncDTO.from_dict(payload if isinstance(payload, dict) else {})

        await auth_service.ensure_user(
            db,
            sub=user.external_sub,
            email=dto.email or user.email,
            display_name=dto.display_name or user.display_name,
        )

        sub = claims["sub"]
        me = await auth_service.me(db, sub=sub)
        return me

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to sync user")


@router.get(
    "/me",
    response_model=MeDTO,
    summary="Identidad actual, rol y permisos",
)
@inject
async def me(
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
    auth_service: AuthService = Depends(
        Provide[ApplicationContainer.api_container.auth_service]
    ),
) -> MeDTO:
    try:
        claims = await require_claims(authorization)
        sub = claims.get("sub")

        if not isinstance(sub, str) or not sub:
            raise HTTPException(status_code=401, detail="sub missing")

        me_obj = await auth_service.me(db, sub=sub)
        return me_obj
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to resolve identity")
