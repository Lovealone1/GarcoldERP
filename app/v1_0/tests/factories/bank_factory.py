from sqlalchemy import insert
from app.v1_0.models import Bank

MOCK_BANKS = [
    {
        "name": "Banco Nacional",
        "balance": 250000.00,
        "account_number": "4587321902",
    },
    {
        "name": "Financiera del Norte",
        "balance": 89200.50,
        "account_number": "9834527781",
    },
    {
        "name": "Banco de la Costa",
        "balance": 1205000.00,
        "account_number": "7719345620",
    },
    {
        "name": "Giro Express",
        "balance": 35000.75,
        "account_number": "6658290147",
    },
    {
        "name": "CrediColombia",
        "balance": 478900.30,
        "account_number": "9021765433",
    },
]

async def seed_banks(db):
    banks = []
    for data in MOCK_BANKS:
        stmt = insert(Bank).values(**data).returning(Bank)
        res = await db.execute(stmt)
        banks.append(res.scalar_one())
    await db.commit()
    return banks