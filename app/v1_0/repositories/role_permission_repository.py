from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert
from app.v1_0.models import RolePermission, Permission

class RolePermissionRepository:
    async def permission_by_code(self, db: AsyncSession, code: str) -> Permission | None:
        return await db.scalar(
            select(Permission).where(Permission.code == code, Permission.is_active.is_(True))
        )

    async def set_active(self, db: AsyncSession, role_id: int, permission_id: int, active: bool) -> None:
        stmt = (
            pg_insert(RolePermission)
            .values(role_id=role_id, permission_id=permission_id, is_active=active)
            .on_conflict_do_update(
                index_elements=[RolePermission.role_id, RolePermission.permission_id],
                set_={"is_active": active, **({"updated_at": func.now()} if hasattr(RolePermission, "updated_at") else {})},
            )
        )
        await db.execute(stmt)

    async def list_by_role(self, db: AsyncSession, role_id: int) -> list[dict]:
        stmt = (
            select(
                Permission.code,
                Permission.description,
                func.coalesce(RolePermission.is_active, False).label("active"),
            )
            .select_from(Permission)
            .join(
                RolePermission,
                (RolePermission.permission_id == Permission.id) & (RolePermission.role_id == role_id),
                isouter=True,
            )
            .where(Permission.is_active.is_(True))
            .order_by(Permission.code)
        )
        rows = await db.execute(stmt)
        return [{"code": c, "description": d, "active": a} for c, d, a in rows.all()]

    async def list_effective_codes(self, db: AsyncSession, role_id: int) -> list[str]:
        stmt = (
            select(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .where(
                RolePermission.role_id == role_id,
                RolePermission.is_active.is_(True),
                Permission.is_active.is_(True),
            )
            .order_by(Permission.code)
        )
        rows = await db.execute(stmt)
        return [r[0] for r in rows.all()]
