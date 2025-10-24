from datetime import datetime
from sqlalchemy import String, Numeric, DateTime, func, text
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base

class Customer(Base):
    __tablename__ = "customer"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tax_id: Mapped[str | None] = mapped_column(String, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    address: Mapped[str | None] = mapped_column(String, nullable=True)
    city: Mapped[str | None] = mapped_column(String)
    phone: Mapped[str | None] = mapped_column(String)
    email: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    balance: Mapped[float] = mapped_column(
        Numeric(14, 2, asdecimal=False),
        nullable=False,
        server_default=text("0.00"),
    )