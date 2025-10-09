from sqlalchemy import String, Boolean, DateTime, func
from sqlalchemy.orm import mapped_column
from .base import Base

class User(Base):
    __tablename__ = "user"

    id = mapped_column(primary_key=True, autoincrement=True)
    username = mapped_column(String, nullable=False, unique=True, index=True)
    password_hash = mapped_column(String, nullable=False)
    is_active = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now())