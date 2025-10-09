from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base

class ExpenseCategory(Base):
    __tablename__ = "expense_category"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False, index=True)