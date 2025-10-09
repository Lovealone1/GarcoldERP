from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import mapped_column
from .base import Base

class Supplier(Base):
    __tablename__ = "supplier"

    id = mapped_column(primary_key=True, autoincrement=True)
    tax_id = mapped_column(String, nullable=True, index=True)
    name = mapped_column(String, nullable=False, index=True)
    address = mapped_column(String, nullable=True)
    city = mapped_column(String, nullable=True)
    phone = mapped_column(String, nullable=True)
    email = mapped_column(String, nullable=True)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now())