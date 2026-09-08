"""Receivables must include every outstanding sale, regardless of its age."""

from datetime import datetime
from types import SimpleNamespace

from sqlalchemy import Date, create_engine, func, insert
from sqlalchemy.sql.elements import Cast
from sqlalchemy.sql.visitors import replacement_traverse

from app.v1_0.models import Sale
from app.v1_0.repositories.sale_repository import SaleRepository


async def test_receivables_include_more_than_ten_old_credits_and_exclude_paid_sales():
    engine = create_engine("sqlite://")
    try:
        Sale.__table__.create(engine)
        with engine.begin() as connection:
            connection.execute(
                insert(Sale.__table__),
                [
                    {
                        "id": sale_id,
                        "customer_id": sale_id,
                        "bank_id": 1,
                        "status_id": 6,
                        "created_at": datetime(2025, 10, 23),
                        "total": 1000.0,
                        "remaining_balance": 500.0 if sale_id <= 12 else 0.0,
                    }
                    for sale_id in range(1, 14)
                ],
            )

            def sqlite_date(expression):
                # PostgreSQL's timezone/date projection is the only dialect
                # adaptation; execute the real WHERE, ORDER BY and LIMIT.
                if isinstance(expression, Cast) and isinstance(expression.type, Date):
                    timestamp = list(expression.clause.clauses)[1]
                    return func.date(timestamp, type_=Date)
                return None

            async def execute(statement):
                return connection.execute(
                    replacement_traverse(statement, {}, sqlite_date)
                )

            rows = await SaleRepository().accounts_receivable(
                session=SimpleNamespace(execute=execute)
            )

        assert [row["customer_id"] for row in rows] == list(range(1, 13))
        assert sum(row["remaining_balance"] for row in rows) == 6000.0
        assert all(row["date"] == "2025-10-23" for row in rows)
    finally:
        engine.dispose()
