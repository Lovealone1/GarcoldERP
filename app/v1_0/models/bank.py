from decimal import Decimal
from sqlalchemy import String, Numeric, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base

class Bank(Base):
    __tablename__ = "bank"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    balance: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    created_at: Mapped[None] = mapped_column(DateTime(timezone=False), server_default=func.now())
    updated_at: Mapped[None] = mapped_column(DateTime(timezone=False), onupdate=func.now(), nullable=True)
    account_number: Mapped[str | None] = mapped_column(String(50))