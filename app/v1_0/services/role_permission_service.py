from typing import Sequence

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.v1_0.models import Role
from app.v1_0.repositories import RolePermissionRepository, RoleRepository
from app.v1_0.schemas import PermissionDTO, RoleDTO


class RolePermissionService:
    """Application service for managing role-permission relationships."""

    def __init__(
        self,
        role_permission_repository: RolePermissionRepository,
        role_repository: RoleRepository,
    ) -> None:
        """Inject repositories."""
        self.repo = role_permission_repository
        self.role_repository = role_repository

    async def set_state(
        self,
        db: AsyncSession,
        role_id: int,
        code: str,
        active: bool,
    ) -> None:
        """
        Enable or disable a permission (by code) for a role.

        Raises:
            HTTPException: 404 if the permission code does not exist.
        """
        perm = await self.repo.permission_by_code(db, code)
        if not perm:
            raise HTTPException(status_code=404, detail="permission_not_found")
        await self.repo.set_active(db, role_id, perm.id, active)

    async def bulk_set(
        self,
        db: AsyncSession,
        role_id: int,
        codes: list[str],
        active: bool = True,
    ) -> None:
        """
        Set multiple permissions for a role in one call.

        Idempotent. Fails if any provided code does not exist.

        Raises:
            HTTPException: 400 with {"missing_permissions": [...]} if some codes are unknown.
        """
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

    async def bulk_assign(
        self,
        db: AsyncSession,
        role_id: int,
        codes: list[str],
    ) -> None:
        """Grant multiple permissions to a role. Shortcut for bulk_set(..., active=True)."""
        await self.bulk_set(db, role_id, codes, active=True)

    async def list_for_role(self, db: AsyncSession, role_id: int) -> list[dict]:
        """
        List all permissions for a role including their active state.

        Returns:
            A list of dicts shaped by the repository (permission + link state).
        """
        return await self.repo.list_by_role(db, role_id)

    async def list_effective_codes(self, db: AsyncSession, role_id: int) -> list[str]:
        """
        List effective permission codes for a role.

        Effective means permission.is_active AND role_permission_link.is_active.
        """
        return await self.repo.list_effective_codes(db, role_id)

    async def list_roles(self, db: AsyncSession) -> list[RoleDTO]:
        """Return all roles as DTOs."""
        rows: Sequence[Role] = await self.role_repository.list_all(db)
        return [RoleDTO(id=r.id, code=r.code) for r in rows]

    async def list_permissions(self, db: AsyncSession) -> list[PermissionDTO]:
        """Return all permissions as DTOs."""
        rows = await self.repo.list_permissions(db)
        return [
            PermissionDTO(code=p.code, description=p.description, is_active=p.is_active)
            for p in rows
        ]
