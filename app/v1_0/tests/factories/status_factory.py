from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.v1_0.models.status import Status


MOCK_STATUSES = [
    {"id": 1, "name": "Compra Contado"},
    {"id": 2, "name": "Venta Contado"},
    {"id": 3, "name": "Venta Cancelada"},
    {"id": 4, "name": "Compra Cancelada"},
    {"id": 5, "name": "Compra Credito"},
    {"id": 6, "name": "Venta Credito"},
]


async def seed_statuses(db: AsyncSession):
    statuses = []

    for data in MOCK_STATUSES:
        stmt = (
            insert(Status)
            .values(id=data["id"], name=data["name"])
            .returning(Status)
        )
        res = await db.execute(stmt)
        statuses.append(res.scalar_one())

    await db.commit()
    return statuses
