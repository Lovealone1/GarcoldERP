from datetime import datetime
from sqlalchemy import Integer, Float, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base

class Purchase(Base):
    __tablename__ = "purchase"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    purchase_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    supplier_id: Mapped[int] = mapped_column(ForeignKey("supplier.id", ondelete="RESTRICT"), nullable=False, index=True)
    bank_id: Mapped[int] = mapped_column(ForeignKey("bank.id", ondelete="RESTRICT"), nullable=False, index=True)
    status_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    total: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    balance: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    supplier = relationship("Supplier")
    bank = relationship("Bank")
    items = relationship("PurchaseItem", back_populates="purchase", cascade="all, delete-orphan")
    payments = relationship("PurchasePayment", back_populates="purchase")