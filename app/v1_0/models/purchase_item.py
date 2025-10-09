from sqlalchemy import Integer, Numeric, DateTime, ForeignKey, func, Computed
from sqlalchemy.orm import relationship, mapped_column
from .base import Base

class PurchaseItem(Base):
    __tablename__ = "purchase_item"

    id = mapped_column(primary_key=True, autoincrement=True)
    product_id = mapped_column(ForeignKey("product.id", ondelete="RESTRICT"), nullable=False, index=True)
    quantity = mapped_column(Integer, nullable=False, default=1)
    unit_price = mapped_column(Numeric(14, 2), nullable=False)
    total = mapped_column(Numeric(14, 2), Computed("quantity * unit_price", persisted=True), nullable=False)
    purchase_id = mapped_column(ForeignKey("purchase.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now())

    product = relationship("Product")
    purchase = relationship("Purchase", back_populates="items")