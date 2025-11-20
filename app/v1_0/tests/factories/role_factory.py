from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.v1_0.models import Role


MOCK_ROLES = [
    {"code": "admin"},
    {"code": "manager"},
    {"code": "user"},
]

async def seed_roles(db: AsyncSession):
    roles = []

    for data in MOCK_ROLES:
        stmt = insert(Role).values(**data).returning(Role)
        res = await db.execute(stmt)
        roles.append(res.scalar_one())

    await db.commit()
    return roles