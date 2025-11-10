from typing import Optional, Any
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import logger
from app.v1_0.repositories import (
    UserRepository,
    RoleRepository,
    PermissionRepository,
)
from .supabase_admin import SupabaseAdminService
from app.v1_0.entities import MeDTO, RoleOut



class AuthService:
    def __init__(
        self,
        user_repository: UserRepository,
        role_repository: RoleRepository,
        permission_repository: PermissionRepository,
        supabase_admin: SupabaseAdminService
    ) -> None:
        self.user_repository = user_repository
        self.role_repository = role_repository
        self.permission_repository = permission_repository
        self.supabase = supabase_admin
        
    async def ensure_user(
    self,
    db: AsyncSession,
    *,
    sub: str,
    email: Optional[str],
    display_name: Optional[str],
    ):
        logger.debug("[AuthService] ensure_user sub=%s", sub)

        async def _upsert() -> tuple[Any, Optional[int]]:
            u = await self.user_repository.get_by_sub(sub, db)
            if u:
                out = await self.user_repository.upsert_basics(u, email, display_name, db)
                rid = out.role_id
            else:
                await self.user_repository.advisory_xact_lock(db)

                u = await self.user_repository.get_by_sub(sub, db)
                if u:
                    out = u
                    rid = out.role_id
                else:
                    total = await self.user_repository.count_all(db)
                    default_role = "admin" if total == 0 else "user"
                    rid = await self.role_repository.get_id_by_code(default_role, db)
                    if not rid:
                        raise ValueError(f"role_not_found:{default_role}")

                    out = await self.user_repository.create_with_role(
                        sub=sub, email=email, name=display_name, role_id=rid, session=db
                    )
            return out, rid

        try:
            if db.in_transaction():
                out, rid = await _upsert()
            else:
                async with db.begin():
                    out, rid = await _upsert()

            try:
                sb = await self.supabase._get_user_raw(sub)
                am = (sb.get("app_metadata") or {})
                sb_role = am.get("role")
                sb_role_id = am.get("role_id")

                role_code = await self.role_repository.get_code_by_id(rid, db) if rid else None
                need_sync = (sb_role != role_code) or (sb_role_id != rid)

                if need_sync:
                    await self.supabase.set_role_metadata_dynamic(user_id=sub, db=db, role_id=rid)
            except Exception as e:
                logger.warning("[AuthService] supabase_role_sync_skip sub=%s err=%s", sub, e)

            return out

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

            role_obj: RoleOut | None = None
            perms: list[str] = []

            if u.role_id is not None:
                role_code = await self.role_repository.get_code_by_id(u.role_id, db)
                if role_code:
                    role_obj = RoleOut(id=u.role_id, code=role_code)
                    perms = sorted(await self.permission_repository.list_codes_by_role_id(u.role_id, db))

            return MeDTO(
                user_id=u.external_sub,
                email=u.email,
                display_name=u.display_name,
                role=role_obj,
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
