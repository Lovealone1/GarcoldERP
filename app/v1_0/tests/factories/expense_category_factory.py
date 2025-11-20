from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.v1_0.models import ExpenseCategory


MOCK_EXPENSE_CATEGORIES = [
    { "name": "Servicios públicos" },
    { "name": "Arriendo" },
    { "name": "Nómina" },
    { "name": "Transporte y logística" },
    { "name": "Mantenimiento y reparaciones" },
]


async def seed_expense_categories(db: AsyncSession):
    categories = []

    for data in MOCK_EXPENSE_CATEGORIES:
        stmt = insert(ExpenseCategory).values(**data).returning(ExpenseCategory)
        res = await db.execute(stmt)
        categories.append(res.scalar_one())

    await db.commit()
    return categories