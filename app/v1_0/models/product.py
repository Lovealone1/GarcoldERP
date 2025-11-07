from datetime import datetime
from sqlalchemy import String, Numeric, Integer, Boolean, DateTime, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base

class Product(Base):
    __tablename__ = "product"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    reference: Mapped[str] = mapped_column(String, nullable=False, index=True)
    description: Mapped[str] = mapped_column(String)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    purchase_price: Mapped[float] = mapped_column(
    Numeric(14, 2, asdecimal=False),
    nullable=False,
    server_default=text("0.00"),
    )
    sale_price: Mapped[float] = mapped_column(
        Numeric(14, 2, asdecimal=False),
        nullable=False,
        server_default=text("0.00"),
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    barcode: Mapped[str | None] = mapped_column(String(64), nullable=True)
    barcode_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    
    items = relationship("SaleItem", back_populates="product", cascade="all, delete-orphan")
