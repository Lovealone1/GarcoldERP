from decimal import Decimal
from sqlalchemy import Integer, Numeric, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship, mapped_column
from .base import Base

class Purchase(Base):
    __tablename__ = "purchase"

    id = mapped_column(primary_key=True, autoincrement=True)
    purchase_date = mapped_column(DateTime(timezone=True), server_default=func.now())

    supplier_id = mapped_column(ForeignKey("supplier.id", ondelete="RESTRICT"), nullable=False, index=True)
    bank_id = mapped_column(ForeignKey("bank.id", ondelete="RESTRICT"), nullable=False, index=True)
    status_id = mapped_column(Integer, nullable=False, index=True)

    total = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    balance = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))

    supplier = relationship("Supplier")
    bank = relationship("Bank")
    items = relationship("PurchaseItem", back_populates="purchase", cascade="all, delete-orphan")
    payments = relationship("PurchasePayment", back_populates="purchase")