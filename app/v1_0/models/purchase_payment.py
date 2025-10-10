from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, func, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base

class PurchasePayment(Base):
    __tablename__ = "purchase_payment"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    purchase_id: Mapped[int] = mapped_column(ForeignKey("purchase.id", ondelete="CASCADE"), nullable=False, index=True)
    bank_id: Mapped[int] = mapped_column(ForeignKey("bank.id", ondelete="RESTRICT"), nullable=False, index=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    purchase= relationship("Purchase", back_populates="payments")
    bank= relationship("Bank")