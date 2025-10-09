from sqlalchemy import Integer, Numeric, ForeignKey
from sqlalchemy.orm import relationship, mapped_column
from .base import Base

class ProfitItem(Base):
    __tablename__ = "profit_item"

    id = mapped_column(primary_key=True, autoincrement=True)
    sale_id = mapped_column(ForeignKey("sale.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = mapped_column(ForeignKey("product.id", ondelete="RESTRICT"), nullable=False, index=True)

    quantity = mapped_column(Integer, nullable=False, default=1)
    purchase_price = mapped_column(Numeric(14, 2), nullable=False)
    sale_price = mapped_column(Numeric(14, 2), nullable=False)
    profit_total = mapped_column(Numeric(14, 2), nullable=False)

    sale = relationship("Sale")
    product = relationship("Product")