from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.v1_0.repositories import RolePermissionRepository

class RolePermissionService:
    def __init__(self, role_permission_repository: RolePermissionRepository):
        self.repo = role_permission_repository

    async def set_state(self, db: AsyncSession, role_id: int, code: str, active: bool) -> None:
        """Activa/inhabilita un permiso por code para un rol."""
        perm = await self.repo.permission_by_code(db, code)
        if not perm:
            raise HTTPException(status_code=404, detail="permission_not_found")
        await self.repo.set_active(db, role_id, perm.id, active)

    async def bulk_set(self, db: AsyncSession, role_id: int, codes: list[str], active: bool = True) -> None:
        """Set en bloque. Idempotente. Error si algún code no existe."""
        if not codes:
            return
        missing: list[str] = []
        for code in codes:
            perm = await self.repo.permission_by_code(db, code)
            if not perm:
                missing.append(code)
                continue
            await self.repo.set_active(db, role_id, perm.id, active)
        if missing:
            raise HTTPException(status_code=400, detail={"missing_permissions": missing})

    async def bulk_assign(self, db: AsyncSession, role_id: int, codes: list[str]) -> None:
        """Otorga en bloque (equivalente a bulk_set(..., active=True))."""
        await self.bulk_set(db, role_id, codes, active=True)

    async def list_for_role(self, db: AsyncSession, role_id: int) -> list[dict]:
        """Lista todos los permisos con su estado para el rol."""
        return await self.repo.list_by_role(db, role_id)

    async def list_effective_codes(self, db: AsyncSession, role_id: int) -> list[str]:
        """Lista códigos efectivos (permission.is_active && link.is_active)."""
        return await self.repo.list_effective_codes(db, role_id)
