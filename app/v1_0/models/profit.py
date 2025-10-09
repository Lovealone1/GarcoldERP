from decimal import Decimal
from sqlalchemy import Numeric, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship, mapped_column
from .base import Base

class Profit(Base):
    __tablename__ = "profit"

    id = mapped_column(primary_key=True, autoincrement=True)
    sale_id = mapped_column(ForeignKey("sale.id", ondelete="CASCADE"), nullable=False, index=True)
    profit = mapped_column(Numeric(14, 2), nullable=False)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now())

    sale = relationship("Sale")
    details = relationship(
        "ProfitItem",
        primaryjoin="foreign(Profit.sale_id) == ProfitItem.sale_id",
        viewonly=True,
    )