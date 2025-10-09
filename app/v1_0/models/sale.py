from decimal import Decimal
from sqlalchemy import Integer, Numeric, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship, mapped_column
from .base import Base

class Sale(Base):
    __tablename__ = "sale"

    id = mapped_column(primary_key=True, autoincrement=True)
    customer_id = mapped_column(ForeignKey("customer.id", ondelete="RESTRICT"), nullable=False, index=True)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now())
    bank_id = mapped_column(ForeignKey("bank.id", ondelete="RESTRICT"), nullable=False, index=True)

    total = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    remaining_balance = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    status_id = mapped_column(Integer, nullable=False, index=True)

    customer = relationship("Customer")
    bank = relationship("Bank")
    items = relationship("SaleItem", back_populates="sale", cascade="all, delete-orphan")
    profit = relationship("Profit", back_populates="sale", cascade="all, delete-orphan", uselist=False)
    payments = relationship("SalePayment", back_populates="sale")