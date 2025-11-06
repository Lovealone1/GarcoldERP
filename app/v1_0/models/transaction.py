from datetime import datetime
from sqlalchemy import String, Float, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .transaction_type import TransactionType
    from .bank import Bank
    
class Transaction(Base):
    __tablename__ = "bank_transaction"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    bank_id: Mapped[int] = mapped_column(
        ForeignKey("bank.id", name="bank_transaction_bank_id_fkey"),
        index=True, nullable=False
    )
    type_id: Mapped[int] = mapped_column(
        ForeignKey("transaction_type.id", name="bank_transaction_type_id_fkey"),
        index=True, nullable=False
    )

    amount: Mapped[float] = mapped_column(Float, nullable=False)
    description: Mapped[str | None] = mapped_column(String(300))
    is_auto: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped["datetime"] = mapped_column(DateTime(timezone=True), index=True, nullable=False)

    bank: Mapped["Bank"] = relationship("Bank", back_populates="transactions", lazy="selectin")
    type: Mapped["TransactionType"] = relationship("TransactionType", back_populates="transactions", lazy="selectin")
