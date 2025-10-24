from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List

from app.core.logger import logger
from app.v1_0.repositories import UserRepository, RoleRepository
from app.v1_0.entities import UserDTO
from .supabase_admin import SupabaseAdminService
class UserService:
    def __init__(self, user_repository: UserRepository, role_repository: RoleRepository,supabase_admin: SupabaseAdminService,) -> None:
        self.user_repo = user_repository
        self.role_repo = role_repository
        self.supabase = supabase_admin
    async def set_role_by_sub(self, *, sub: str, role_id: int, db: AsyncSession) -> None:
        async with db.begin():
            await self.user_repo.set_role_by_sub(sub, role_id, db)

        try:
            role_code = await self.role_repo.get_code_by_id(role_id, db)
            await self.supabase.set_role_metadata_dynamic(
                user_id=sub,
                db=db,
                role_id=role_id,      
                role_code=role_code,
            )
        except Exception as e:
            logger.warning("supabase_role_sync_failed sub=%s role_id=%s err=%s", sub, role_id, e)

    async def upsert_basics_by_sub(
        self, *, sub: str, email: Optional[str], name: Optional[str], db: AsyncSession
    ) -> None:
        u = await self.user_repo.get_by_sub(sub, db)
        if not u:
            return
        await self.user_repo.upsert_basics(u, email=email, name=name, session=db)
        await db.commit() 
        
    async def list_users_full(self, *, db: AsyncSession) -> List[UserDTO]:
        users = await self.user_repo.list_all(db)
        roles = await self.role_repo.list_all(db)
        code_by_id: dict[int, str] = {r.id: r.code for r in roles}

        out: List[UserDTO] = []
        for u in users:
            rid: Optional[int] = u.role_id
            role_code: Optional[str] = code_by_id[rid] if rid is not None and rid in code_by_id else None
            out.append(
                UserDTO(
                    id=u.id,
                    external_sub=u.external_sub,
                    email=u.email,
                    display_name=u.display_name,
                    role=role_code,
                    is_active=u.is_active,
                    created_at=u.created_at,
                    updated_at=getattr(u, "updated_at", None),
                )
            )
        return out

    async def get_user_full_by_sub(self, *, sub: str, db: AsyncSession) -> UserDTO:
        u = await self.user_repo.get_by_sub(sub, db)
        if not u:
            raise ValueError("user_not_found")

        rid: Optional[int] = u.role_id
        role_code: Optional[str] = None
        if rid is not None:
            role_code = await self.role_repo.get_code_by_id(rid, db)

        return UserDTO(
            id=u.id,
            external_sub=u.external_sub,
            email=u.email,
            display_name=u.display_name,
            role=role_code,
            is_active=u.is_active,
            created_at=u.created_at,
            updated_at=getattr(u, "updated_at", None),
        )

    async def set_active_by_sub(self, *, sub: str, is_active: bool, db: AsyncSession) -> None:
        async with db.begin():
            await self.user_repo.set_active_by_sub(sub, is_active, db)
            
            