from sqlalchemy import DateTime, ForeignKey, func, Integer, Float
from sqlalchemy.orm import Mapped, relationship, mapped_column
from datetime import datetime
from .base import Base

class Profit(Base):
    __tablename__ = "profit"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sale_id: Mapped[int] = mapped_column(ForeignKey("sale.id"), nullable=False, index=True)
    profit: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    sale= relationship("Sale", back_populates="profit")

    details = relationship(
        "ProfitItem",
        primaryjoin="foreign(Profit.sale_id) == ProfitItem.sale_id",
        viewonly=True,
    )