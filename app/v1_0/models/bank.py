from sqlalchemy import String, Numeric, DateTime, text, func
from datetime import datetime 
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .transaction import Transaction

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
    DateTime(timezone=True),
    server_default=func.now(),
    server_onupdate=func.now(),
    nullable=False,
    )
    account_number: Mapped[str | None] = mapped_column(String(50))
    transactions: Mapped[list["Transaction"]] = relationship(
        "Transaction", back_populates="bank", lazy="selectin"
    )