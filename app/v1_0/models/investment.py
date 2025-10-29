from datetime import date
from sqlalchemy import String, Numeric, Date, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base

class Investment(Base):
    __tablename__ = "investment"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    balance: Mapped[float] = mapped_column(
        Numeric(14, 2, asdecimal=False),
        nullable=False,
    )
    bank_id: Mapped[int] = mapped_column(
        ForeignKey("bank.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    maturity_date: Mapped[date] = mapped_column(Date)