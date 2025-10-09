from sqlalchemy import String
from sqlalchemy.orm import mapped_column
from .base import Base

class TransactionType(Base):
    __tablename__ = "transaction_type"

    id = mapped_column(primary_key=True, autoincrement=True)
    name = mapped_column(String, nullable=False, index=True)