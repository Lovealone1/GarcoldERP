from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, func, Integer, Float, Numeric, Computed
from sqlalchemy.orm import Mapped, relationship, mapped_column

from .base import Base

class PurchaseItem(Base):
    __tablename__ = "purchase_item"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("product.id", ondelete="RESTRICT"), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False)
    total: Mapped[float] = mapped_column(
        Numeric(14, 2),
        Computed("quantity * unit_price", persisted=True),
        nullable=False,
    )
    purchase_id: Mapped[int] = mapped_column(ForeignKey("purchase.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    product = relationship("Product")
    purchase= relationship("Purchase", back_populates="items")