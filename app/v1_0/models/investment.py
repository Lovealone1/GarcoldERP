from decimal import Decimal
from datetime import date
from sqlalchemy import String, Numeric, Date
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base

class Investment(Base):
    __tablename__ = "investment"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    balance: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    maturity_date: Mapped[date | None] = mapped_column(Date)