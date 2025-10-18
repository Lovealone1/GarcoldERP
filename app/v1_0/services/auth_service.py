from typing import Optional, List
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import logger
from app.v1_0.repositories import (
    UserRepository,
    RoleRepository,
    PermissionRepository,
)
from app.v1_0.entities import MeDTO  
from app.v1_0.models import User


class AuthService:
    def __init__(
        self,
        user_repository: UserRepository,
        role_repository: RoleRepository,
        permission_repository: PermissionRepository,
    ) -> None:
        self.user_repository = user_repository
        self.role_repository = role_repository
        self.permission_repository = permission_repository

    async def ensure_user(
        self,
        db: AsyncSession,
        *,
        sub: str,
        email: Optional[str],
        display_name: Optional[str],
    ) -> User:
        logger.debug("[AuthService] ensure_user sub=%s", sub)
        try:
            async with db.begin():
                u = await self.user_repository.get_by_sub(sub, db)
                if u:
                    return await self.user_repository.upsert_basics(u, email, display_name, db)

                await self.user_repository.advisory_xact_lock(db)

                u = await self.user_repository.get_by_sub(sub, db)
                if u:
                    return u

                total = await self.user_repository.count_all(db)
                role_code = "admin" if total == 0 else "user"
                rid = await self.role_repository.get_id_by_code(role_code, db)
                if not rid:
                    raise ValueError(f"role_not_found:{role_code}")

                return await self.user_repository.create_with_role(
                    sub=sub, email=email, name=display_name, role_id=rid, session=db
                )
        except HTTPException:
            raise
        except Exception as e:
            logger.error("[AuthService] ensure_user failed: %s", e, exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to ensure user")

    async def me(self, db: AsyncSession, *, sub: str) -> MeDTO:
        try:
            u = await self.user_repository.get_by_sub(sub, db)
            if not u:
                raise HTTPException(status_code=403, detail="user_not_provisioned")

            role_code: Optional[str] = None
            perms: List[str] = []

            if u.role_id:
                role_code = await self.role_repository.get_code_by_id(u.role_id, db)
                perms_set = await self.permission_repository.list_codes_by_role_id(u.role_id, db)  
                perms = sorted(list(perms_set))  
            return MeDTO(
                user_id=u.external_sub,
                email=u.email,
                display_name=u.display_name,
                role=role_code,
                permissions=perms,
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error("[AuthService] me failed: %s", e, exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to resolve identity")

    async def set_role(self, db: AsyncSession, *, sub: str, role_code: str) -> None:
        logger.debug("[AuthService] set_role sub=%s role=%s", sub, role_code)
        try:
            async with db.begin():
                rid = await self.role_repository.get_id_by_code(role_code, db)
                if not rid:
                    raise HTTPException(status_code=404, detail="role_not_found")
                await self.user_repository.set_role_by_sub(sub, rid, db)
        except HTTPException:
            raise
        except Exception as e:
            logger.error("[AuthService] set_role failed: %s", e, exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to set role")
