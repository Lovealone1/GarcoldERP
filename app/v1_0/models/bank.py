from decimal import Decimal
from sqlalchemy import String, Numeric, DateTime, text
from datetime import datetime 
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base

class Bank(Base):
    __tablename__ = "bank"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    balance: Mapped[float] = mapped_column(
        Numeric(14, 2, asdecimal=False),
        nullable=False,
        server_default=text("0.00"),
    )
    created_at: Mapped[datetime] = mapped_column(
    DateTime(), server_default=text("now()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(), server_default=text("now()"),
        server_onupdate=text("now()"), nullable=False
    )
    account_number: Mapped[str | None] = mapped_column(String(50))