import uuid
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.v1_0.models import User, Role


MOCK_USERS = [
    {
        "display_name": "Daniel García",
        "email": "daniel@example.com",
    },
    {
        "display_name": "María Jiménez",
        "email": "maria@example.com",
    },
    {
        "display_name": "Carlos Pérez",
        "email": "carlos@example.com",
    },
    {
        "display_name": "Ana Torres",
        "email": "ana@example.com",
    },
    {
        "display_name": "Usuario Genérico",
        "email": "generic@example.com",
    },
]


async def seed_users(db: AsyncSession):

    roles_result = await db.execute(select(Role))
    roles = roles_result.scalars().all()
    role_ids = [r.id for r in roles]

    users = []

    for data in MOCK_USERS:
        stmt = (
            insert(User)
            .values(
                external_sub=str(uuid.uuid4()),
                email=data["email"],
                display_name=data["display_name"],
                role_id=role_ids[0] if role_ids else None,
            )
            .returning(User)
        )
        res = await db.execute(stmt)
        users.append(res.scalar_one())

    await db.commit()
    return users