from sqlalchemy import Integer, String, literal_column
from sqlalchemy.orm import Mapped, mapped_column, relationship, foreign
from .base import Base
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .transaction import Transaction
    
class TransactionType(Base):
    __tablename__ = "transaction_type"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    transactions: Mapped[list["Transaction"]] = relationship(
        "Transaction", back_populates="type", lazy="selectin"
    )
