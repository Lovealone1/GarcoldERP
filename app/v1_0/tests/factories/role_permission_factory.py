from typing import List

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.v1_0.models import RolePermission, Role, Permission

ROLE_CODES = ["admin", "manager", "user"]

PERMISSION_CODES = [
    "sales.view",
    "sales.create",
    "sales.update",
    "sales.delete",
    "purchases.view",
    "purchases.create",
    "purchases.update",
    "purchases.delete",
    "products.view",
    "products.manage",
    "banks.view",
    "banks.manage",
    "transactions.view",
    "transactions.create_manual",
    "customers.view",
    "customers.manage",
    "suppliers.view",
    "suppliers.manage",
    "settings.roles.manage",
]


async def seed_role_permissions(db: AsyncSession) -> List[RolePermission]:
    # 1) Asegurar roles
    roles_result = await db.execute(select(Role))
    roles = roles_result.scalars().all()

    if not roles:
        for code in ROLE_CODES:
            stmt = insert(Role).values(code=code)
            await db.execute(stmt)
        await db.commit()
        roles_result = await db.execute(select(Role))
        roles = roles_result.scalars().all()

    perms_result = await db.execute(select(Permission))
    permissions = perms_result.scalars().all()

    if not permissions:
        for code in PERMISSION_CODES:
            stmt = insert(Permission).values(code=code)
            await db.execute(stmt)
        await db.commit()
        perms_result = await db.execute(select(Permission))
        permissions = perms_result.scalars().all()

    if not roles or not permissions:
        return []

    created: List[RolePermission] = []

    max_roles = min(len(roles), 5)
    max_perms = min(len(permissions), 20)

    for role in roles[:max_roles]:
        for perm in permissions[:max_perms]:
            stmt = (
                insert(RolePermission)
                .values(
                    role_id=role.id,
                    permission_id=perm.id,
                    is_active=True,
                )
                .returning(RolePermission)
            )
            res = await db.execute(stmt)
            created.append(res.scalar_one())

    await db.commit()
    return created
