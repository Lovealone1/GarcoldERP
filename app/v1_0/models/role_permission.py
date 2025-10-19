from sqlalchemy import Boolean, Column, ForeignKey, UniqueConstraint, Integer, text
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql.sqltypes import DateTime
from .base import Base

class RolePermission(Base):
    __tablename__ = "role_permission"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True) 
    role_id: Mapped[int] = mapped_column(ForeignKey("role.id", ondelete="CASCADE"), index=True)
    permission_id: Mapped[int] = mapped_column(ForeignKey("permission.id", ondelete="CASCADE"), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    __table_args__ = (UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),)

    role = relationship("Role")
    permission = relationship("Permission")
