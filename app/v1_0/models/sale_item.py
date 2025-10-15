from datetime import datetime
from sqlalchemy import Integer, Float, Numeric, DateTime, ForeignKey, func, Computed
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base

class SaleItem(Base):
    __tablename__ = "sale_item"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("product.id", ondelete="RESTRICT"), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False)
    total: Mapped[float] = mapped_column(Numeric(14, 2), Computed("quantity * unit_price", persisted=True), nullable=False)
    sale_id: Mapped[int] = mapped_column(ForeignKey("sale.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    product = relationship("Product")
    sale = relationship("Sale", back_populates="items")