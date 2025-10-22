from sqlalchemy import Boolean, ForeignKey, PrimaryKeyConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base

class RolePermission(Base):
    __tablename__ = "role_permission"
    role_id: Mapped[int] = mapped_column(ForeignKey("role.id", ondelete="CASCADE"))
    permission_id: Mapped[int] = mapped_column(ForeignKey("permission.id", ondelete="CASCADE"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("role_id", "permission_id", name="pk_role_permission"),
    )
