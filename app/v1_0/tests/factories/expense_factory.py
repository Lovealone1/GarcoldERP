from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
import random

from app.v1_0.models import Expense
from tests.factories import seed_banks, seed_expense_categories


AMOUNTS = [15000.00, 85000.50, 120000.00, 45000.75, 99900.25]

async def seed_expenses(db: AsyncSession):
    """
    Inserta 5 expenses usando categorías y bancos seed.
    """
    categories = await seed_expense_categories(db)
    category_ids = [c.id for c in categories]

    banks = await seed_banks(db)
    bank_ids = [b.id for b in banks]

    expenses = []

    for amount in AMOUNTS:
        stmt = (
            insert(Expense)
            .values(
                expense_category_id=random.choice(category_ids),
                amount=amount,
                bank_id=random.choice(bank_ids),
                expense_date=datetime.now() - timedelta(days=random.randint(0, 10)),
            )
            .returning(Expense)
        )
        res = await db.execute(stmt)
        expenses.append(res.scalar_one())

    await db.commit()
    return expenses
