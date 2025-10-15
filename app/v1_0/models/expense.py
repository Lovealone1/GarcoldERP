from datetime import datetime
from sqlalchemy import Numeric, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base

class Expense(Base):
    __tablename__ = "expense"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    expense_category_id: Mapped[int] = mapped_column(
        ForeignKey("expense_category.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    amount: Mapped[float] = mapped_column(Numeric(14, 2, asdecimal=False),nullable=False)
    bank_id: Mapped[int] = mapped_column(
        ForeignKey("bank.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    expense_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    category = relationship("ExpenseCategory")
    bank = relationship("Bank")