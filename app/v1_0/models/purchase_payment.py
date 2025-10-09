from sqlalchemy import Numeric, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship, mapped_column
from .base import Base

class PurchasePayment(Base):
    __tablename__ = "purchase_payment"

    id = mapped_column(primary_key=True, autoincrement=True)
    purchase_id = mapped_column(ForeignKey("purchase.id", ondelete="CASCADE"), nullable=False, index=True)
    bank_id = mapped_column(ForeignKey("bank.id", ondelete="RESTRICT"), nullable=False, index=True)
    amount = mapped_column(Numeric(14, 2), nullable=False)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now())

    purchase = relationship("Purchase", back_populates="payments")
    bank = relationship("Bank")