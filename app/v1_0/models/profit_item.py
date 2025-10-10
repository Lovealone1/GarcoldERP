from sqlalchemy import Integer, Numeric, DateTime, ForeignKey, func, Computed
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base

class ProfitItem(Base):
    __tablename__ = "profit_item"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sale_id: Mapped[int] = mapped_column(ForeignKey("sale.id", ondelete="CASCADE"), index=True, nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("product.id", ondelete="RESTRICT"), index=True, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    buy_price: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    sale_price: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    profit_total: Mapped[float] = mapped_column(
        Numeric(14, 2),
        Computed("(sale_price - buy_price) * quantity", persisted=True),
        nullable=False,
    )
    created_at: Mapped[None] = mapped_column(DateTime(timezone=True), server_default=func.now())

    sale= relationship("Sale")
    product = relationship("Product")