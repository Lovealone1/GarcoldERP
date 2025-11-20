from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.v1_0.models import TransactionType


MOCK_TRANSACTION_TYPES = [
    {"name": "Ingreso"},
    {"name": "Retiro"},
    {"name": "Ajuste"},
]


async def seed_transaction_types(db: AsyncSession):
    types_ = []

    for data in MOCK_TRANSACTION_TYPES:
        stmt = insert(TransactionType).values(**data).returning(TransactionType)
        res = await db.execute(stmt)
        types_.append(res.scalar_one())

    await db.commit()
    return types_
