# app/v1_0/models/users.py
from sqlalchemy import BigInteger, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import text as sa_text
from datetime import datetime
from .base import Base

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    external_sub: Mapped[str] = mapped_column(Text, nullable=False, unique=True, index=True)
    email: Mapped[str | None] = mapped_column(Text, unique=True)
    display_name: Mapped[str | None] = mapped_column(Text)

    role_id: Mapped[int | None] = mapped_column(ForeignKey("role.id"))
    role = relationship("Role", lazy="joined")

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa_text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=sa_text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=sa_text("now()"), server_onupdate=sa_text("now()"))
