from datetime import datetime
from sqlalchemy import Integer, Float, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base

class Sale(Base):
    __tablename__ = "sale"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customer.id", ondelete="RESTRICT"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    bank_id: Mapped[int] = mapped_column(ForeignKey("bank.id", ondelete="RESTRICT"), nullable=False, index=True)

    total: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    remaining_balance: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("status.id", name="sale_status_id_fkey", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    customer = relationship("Customer")
    bank = relationship("Bank")
    items = relationship("SaleItem", back_populates="sale", cascade="all, delete-orphan")
    profit = relationship("Profit", back_populates="sale", cascade="all, delete-orphan", uselist=False)
    payments = relationship("SalePayment", back_populates="sale")
    
    customer = relationship("Customer", lazy="selectin")
    bank = relationship("Bank", lazy="selectin")
    status = relationship("Status", lazy="selectin")

    items = relationship("SaleItem", back_populates="sale", cascade="all, delete-orphan", lazy="selectin")
    profit = relationship("Profit", back_populates="sale", cascade="all, delete-orphan", uselist=False, lazy="selectin")
    payments = relationship("SalePayment", back_populates="sale", lazy="selectin")