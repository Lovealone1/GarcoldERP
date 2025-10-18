from typing import Optional, List, Set
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.v1_0.models.permission import Permission
from .base_repository import BaseRepository

class PermissionRepository(BaseRepository[Permission]):
    """Repository for Permission model."""

    def __init__(self) -> None:
        super().__init__(Permission)

    async def create_permission(
        self,
        code: str,
        session: AsyncSession,
        description: str | None = None,
        meta: dict | None = None,
        is_active: bool = True,
    ) -> Permission:
        perm = Permission(code=code, description=description, meta=meta or {}, is_active=is_active)
        await self.add(perm, session)
        return perm

    async def get_by_code(self, code: str, session: AsyncSession) -> Optional[Permission]:
        return await session.scalar(select(Permission).where(Permission.code == code))

    async def list_permissions(self, session: AsyncSession) -> List[Permission]:
        res = await session.execute(select(Permission))
        return list(res.scalars().all())

    async def set_active(self, code: str, is_active: bool, session: AsyncSession) -> bool:
        p = await self.get_by_code(code, session)
        if not p:
            return False
        p.is_active = is_active
        await self.update(p, session)
        return True
    
    async def list_codes_by_role_id(self, role_id: int, session: AsyncSession) -> Set[str]:
        rows = (
            await session.execute(
                text(
                    """
                    select p.code
                    from role_permission rp
                    join permission p on p.id = rp.permission_id
                    where rp.role_id = :rid
                      and rp.is_active = true
                      and p.is_active  = true
                    """
                ),
                {"rid": role_id},
            )
        ).all()
        return {r[0] for r in rows}

    async def assign_to_role(self, role_code: str, perm_code: str, session: AsyncSession) -> None:
        await session.execute(
            text(
                """
                insert into role_permission(role_id, permission_id, is_active)
                select r.id, p.id, true
                from role r, permission p
                where r.code=:rc and p.code=:pc
                on conflict do nothing
                """
            ),
            {"rc": role_code, "pc": perm_code},
        )

    async def revoke_from_role(self, role_code: str, perm_code: str, session: AsyncSession) -> None:
        await session.execute(
            text(
                """
                delete from role_permission
                where role_id = (select id from role where code=:rc)
                  and permission_id = (select id from permission where code=:pc)
                """
            ),
            {"rc": role_code, "pc": perm_code},
        )
