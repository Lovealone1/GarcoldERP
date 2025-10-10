from decimal import Decimal
from sqlalchemy import String, Numeric, DateTime, Boolean, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base

class Transaction(Base):
    __tablename__ = "bank_transaction"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    bank_id: Mapped[int] = mapped_column(ForeignKey("bank.id", ondelete="CASCADE"), index=True, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    type_id: Mapped[int | None] = mapped_column(index=True)
    created_at: Mapped[None] = mapped_column(DateTime(timezone=True), server_default=func.now())
    description: Mapped[str | None] = mapped_column(String)
    is_auto: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    bank = relationship("Bank")
