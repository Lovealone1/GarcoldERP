from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.v1_0.models import Customer


MOCK_CUSTOMERS = [
    {
        "tax_id": "900123456",
        "name": "Juan Pérez",
        "address": "Calle 12 #34-56",
        "city": "Medellín",
        "phone": "3001234567",
        "email": "juan.perez@example.com",
        "balance": 0.00,
    },
    {
        "tax_id": "901987654",
        "name": "María Gómez",
        "address": "Cra 45 #78-90",
        "city": "Bogotá",
        "phone": "3109876543",
        "email": "maria.gomez@example.com",
        "balance": 15000.50,
    },
    {
        "tax_id": None,
        "name": "Pedro López",
        "address": "Av. Santander 123",
        "city": "Cali",
        "phone": "3151112233",
        "email": "pedro.lopez@example.com",
        "balance": 5000.00,
    },
    {
        "tax_id": "902334455",
        "name": "Ana Rodríguez",
        "address": "Transv 23 #45-67",
        "city": "Bucaramanga",
        "phone": "3209988776",
        "email": "ana.rod@example.com",
        "balance": 200000.00,
    },
    {
        "tax_id": None,
        "name": "Cliente Genérico",
        "address": None,
        "city": "Medellín",
        "phone": None,
        "email": None,
        "balance": 0.00,
    },
]


async def seed_customers(db: AsyncSession):
    customers = []

    for data in MOCK_CUSTOMERS:
        stmt = insert(Customer).values(**data).returning(Customer)
        res = await db.execute(stmt)
        customers.append(res.scalar_one())

    await db.commit()
    return customers
