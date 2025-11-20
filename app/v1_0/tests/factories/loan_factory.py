from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.v1_0.models import Loan


MOCK_LOANS = [
    {
        "name": "Préstamo Rápido",
        "amount": 1_500_000.00,
    },
    {
        "name": "Préstamo Comercial",
        "amount": 7_200_000.00,
    },
    {
        "name": "Préstamo de Expansión",
        "amount": 15_000_000.00,
    },
    {
        "name": "Préstamo Emergencia",
        "amount": 500_000.00,
    },
    {
        "name": "Préstamo Proveedor Aliado",
        "amount": 3_750_000.00,
    },
]


async def seed_loans(db: AsyncSession):
    loans = []

    for data in MOCK_LOANS:
        stmt = insert(Loan).values(**data).returning(Loan)
        res = await db.execute(stmt)
        loans.append(res.scalar_one())

    await db.commit()
    return loans
