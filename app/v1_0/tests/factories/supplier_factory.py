from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.v1_0.models import Supplier


MOCK_SUPPLIERS = [
    {
        "tax_id": "900111222",
        "name": "Distribuidora Antioquia S.A.S.",
        "address": "Calle 10 #45-23",
        "city": "Medellín",
        "phone": "3001112233",
        "email": "contacto@dist-antioquia.com",
    },
    {
        "tax_id": "901333444",
        "name": "Proveedor Central de Alimentos",
        "address": "Cra 50 #20-15",
        "city": "Bogotá",
        "phone": "3103334455",
        "email": "ventas@centralalimentos.com",
    },
    {
        "tax_id": None,
        "name": "Mayorista Occidente",
        "address": "Av. 4N #25-60",
        "city": "Cali",
        "phone": "3154445566",
        "email": "info@mayoristaoccidente.com",
    },
    {
        "tax_id": "902555666",
        "name": "Proveedor Lácteos del Norte",
        "address": "Calle 30 #12-40",
        "city": "Bucaramanga",
        "phone": "3205556677",
        "email": "contacto@lacteosnorte.com",
    },
    {
        "tax_id": None,
        "name": "Proveedor Genérico",
        "address": None,
        "city": "Medellín",
        "phone": None,
        "email": None,
    },
]


async def seed_suppliers(db: AsyncSession):
    suppliers = []

    for data in MOCK_SUPPLIERS:
        stmt = insert(Supplier).values(**data).returning(Supplier)
        res = await db.execute(stmt)
        suppliers.append(res.scalar_one())

    await db.commit()
    return suppliers
