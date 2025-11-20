from datetime import date, timedelta
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.v1_0.models import Investment
from tests.factories import seed_banks


MOCK_INVESTMENTS = [
    {
        "name": "CDT Corto Plazo",
        "balance": 5_000_000.00,
        "days_to_maturity": 30,
    },
    {
        "name": "CDT Mediano Plazo",
        "balance": 12_500_000.00,
        "days_to_maturity": 90,
    },
    {
        "name": "Fondo de Inversión Conservador",
        "balance": 3_200_000.00,
        "days_to_maturity": 180,
    },
    {
        "name": "Fondo de Inversión Dinámico",
        "balance": 8_750_000.00,
        "days_to_maturity": 365,
    },
    {
        "name": "CDT Empresa Aliada",
        "balance": 20_000_000.00,
        "days_to_maturity": 730,
    },
]


async def seed_investments(db: AsyncSession):
    """
    Crea 5 inversiones asociadas a bancos existentes (sembrados con seed_banks).
    """
    banks = await seed_banks(db)
    bank_ids = [b.id for b in banks]

    today = date.today()
    investments = []

    for idx, data in enumerate(MOCK_INVESTMENTS):
        maturity = today + timedelta(days=data["days_to_maturity"])
        stmt = (
            insert(Investment)
            .values(
                name=data["name"],
                balance=data["balance"],
                bank_id=bank_ids[idx % len(bank_ids)],
                maturity_date=maturity,
            )
            .returning(Investment)
        )
        res = await db.execute(stmt)
        investments.append(res.scalar_one())

    await db.commit()
    return investments
