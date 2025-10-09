from sqlalchemy import Numeric, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship, mapped_column
from .base import Base

class SalePayment(Base):
    __tablename__ = "sale_payment"

    id = mapped_column(primary_key=True, autoincrement=True)
    sale_id = mapped_column(ForeignKey("sale.id", ondelete="CASCADE"), nullable=False, index=True)
    bank_id = mapped_column(ForeignKey("bank.id", ondelete="RESTRICT"), nullable=False, index=True)
    amount = mapped_column(Numeric(14, 2), nullable=False)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now())

    sale = relationship("Sale", back_populates="payments")
    bank = relationship("Bank")