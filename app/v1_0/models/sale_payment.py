from datetime import datetime
from sqlalchemy import Float, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base

class SalePayment(Base):
    __tablename__ = "sale_payment"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sale_id: Mapped[int] = mapped_column(ForeignKey("sale.id"), nullable=False, index=True)
    bank_id: Mapped[int] = mapped_column(ForeignKey("bank.id"), nullable=False, index=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    sale = relationship("Sale", back_populates="payments")
    bank = relationship("Bank")