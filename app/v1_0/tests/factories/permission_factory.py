from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.v1_0.models.permission import Permission


MOCK_PERMISSIONS = [
    {
        "code": "sales.view",
        "description": "Ver ventas",
        "meta": {"module": "sales", "scope": "read"},
    },
    {
        "code": "sales.create",
        "description": "Crear ventas",
        "meta": {"module": "sales", "scope": "write"},
    },
    {
        "code": "sales.update",
        "description": "Editar ventas",
        "meta": {"module": "sales", "scope": "write"},
    },
    {
        "code": "sales.delete",
        "description": "Eliminar ventas",
        "meta": {"module": "sales", "scope": "delete"},
    },

    {
        "code": "purchases.view",
        "description": "Ver compras",
        "meta": {"module": "purchases", "scope": "read"},
    },
    {
        "code": "purchases.create",
        "description": "Crear compras",
        "meta": {"module": "purchases", "scope": "write"},
    },
    {
        "code": "purchases.update",
        "description": "Editar compras",
        "meta": {"module": "purchases", "scope": "write"},
    },
    {
        "code": "purchases.delete",
        "description": "Eliminar compras",
        "meta": {"module": "purchases", "scope": "delete"},
    },

    {
        "code": "products.view",
        "description": "Ver productos",
        "meta": {"module": "products", "scope": "read"},
    },
    {
        "code": "products.manage",
        "description": "Crear y editar productos",
        "meta": {"module": "products", "scope": "write"},
    },

    {
        "code": "banks.view",
        "description": "Ver bancos",
        "meta": {"module": "banks", "scope": "read"},
    },
    {
        "code": "banks.manage",
        "description": "Gestionar bancos",
        "meta": {"module": "banks", "scope": "write"},
    },
    {
        "code": "transactions.view",
        "description": "Ver transacciones",
        "meta": {"module": "transactions", "scope": "read"},
    },
    {
        "code": "transactions.create_manual",
        "description": "Crear transacciones manuales",
        "meta": {"module": "transactions", "scope": "write"},
    },

    {
        "code": "customers.view",
        "description": "Ver clientes",
        "meta": {"module": "customers", "scope": "read"},
    },
    {
        "code": "customers.manage",
        "description": "Gestionar clientes",
        "meta": {"module": "customers", "scope": "write"},
    },
    {
        "code": "suppliers.view",
        "description": "Ver proveedores",
        "meta": {"module": "suppliers", "scope": "read"},
    },
    {
        "code": "suppliers.manage",
        "description": "Gestionar proveedores",
        "meta": {"module": "suppliers", "scope": "write"},
    },

    {
        "code": "settings.roles.manage",
        "description": "Gestionar roles y permisos",
        "meta": {"module": "settings", "scope": "admin"},
    },
]


async def seed_permissions(db: AsyncSession):
    permissions = []

    for data in MOCK_PERMISSIONS:
        stmt = (
            insert(Permission)
            .values(
                code=data["code"],
                description=data["description"],
                meta=data["meta"],
            )
            .returning(Permission)
        )
        res = await db.execute(stmt)
        permissions.append(res.scalar_one())

    await db.commit()
    return permissions
