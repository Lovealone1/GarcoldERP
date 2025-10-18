from typing import Dict
from fastapi import APIRouter, HTTPException, Depends, Header, status, Body
from sqlalchemy.ext.asyncio import AsyncSession
from dependency_injector.wiring import inject, Provide

from app.storage.database.db_connector import get_db
from app.app_containers import ApplicationContainer
from app.core.logger import logger

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
    logger.info(
        "[AuthRouter] sync_self: auth_header=%s payload_keys=%s",
        "present" if authorization else "missing",
        list(payload.keys()) if isinstance(payload, dict) else type(payload).__name__,
    )
    try:
        # 1) Validar token y obtener claims
        claims = await require_claims(authorization)
        logger.info(
            "[AuthRouter] claims: iss=%s sub=%s email=%s",
            claims.get("iss"),
            claims.get("sub"),
            claims.get("email"),
        )

        # 2) Asegurar usuario en DB
        user = await ensure_current_user(db, authorization, auth_service)
        logger.info(
            "[AuthRouter] ensured user: db_id=%s sub=%s role_id=%s email=%s",
            getattr(user, "id", None),
            getattr(user, "external_sub", None),
            getattr(user, "role_id", None),
            getattr(user, "email", None),
        )

        # 3) Aplicar metadatos opcionales del front
        dto = AuthSyncDTO.from_dict(payload if isinstance(payload, dict) else {})
        logger.debug(
            "[AuthRouter] sync dto: email=%s display_name=%s",
            dto.email,
            dto.display_name,
        )
        await auth_service.ensure_user(
            db,
            sub=user.external_sub,
            email=dto.email or user.email,
            display_name=dto.display_name or user.display_name,
        )

        # 4) Responder identidad consolidada
        sub = claims["sub"]
        me = await auth_service.me(db, sub=sub)
        logger.info(
            "[AuthRouter] sync_self OK: role=%s perms=%d",
            me.role,
            len(me.permissions or []),
        )
        return me

    except HTTPException:
        raise
    except Exception as e:
        logger.error("[AuthRouter] sync_self error: %s", e, exc_info=True)
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
    logger.debug("[AuthRouter] me: auth_header=%s", "present" if authorization else "missing")
    try:
        claims = await require_claims(authorization)
        sub = claims.get("sub")
        logger.debug("[AuthRouter] me claims: sub=%s", sub)

        if not isinstance(sub, str) or not sub:
            raise HTTPException(status_code=401, detail="sub missing")
        user = await ensure_current_user(db, authorization, auth_service)
        logger.debug(
            "[AuthRouter] me ensured: db_id=%s role_id=%s",
            getattr(user, "id", None),
            getattr(user, "role_id", None),
        )

        me_obj = await auth_service.me(db, sub=sub)
        logger.debug(
            "[AuthRouter] me OK: role=%s perms=%d",
            me_obj.role,
            len(me_obj.permissions or []),
        )
        return me_obj
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[AuthRouter] me error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to resolve identity")
