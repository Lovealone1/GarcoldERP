from datetime import datetime
from sqlalchemy import BigInteger, Integer, Text, CheckConstraint, ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import ENUM as PGEnum
from .base import Base

MediaKind = PGEnum('AVATAR','PRODUCT','INVOICE', name='media_kind', create_type=False)

class Media(Base):
    __tablename__ = "media"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(MediaKind, nullable=False)

    product_id:  Mapped[int | None] = mapped_column(ForeignKey("product.id",  ondelete="CASCADE"))
    purchase_id: Mapped[int | None] = mapped_column(ForeignKey("purchase.id", ondelete="CASCADE"))
    user_id:     Mapped[int | None] = mapped_column(ForeignKey("users.id",    ondelete="CASCADE"))

    key:          Mapped[str] = mapped_column(Text, nullable=False)
    public_url:   Mapped[str] = mapped_column(Text, nullable=False)
    bytes:        Mapped[int | None] = mapped_column(Integer)
    checksum:     Mapped[str | None] = mapped_column(Text)
    content_type: Mapped[str] = mapped_column(Text, nullable=False)
    created_at:   Mapped[datetime] = mapped_column(server_default=text("now()"))

    __table_args__ = (
        CheckConstraint(
            "(kind='AVATAR'  AND user_id IS NOT NULL AND product_id IS NULL AND purchase_id IS NULL) OR "
            "(kind='PRODUCT' AND product_id IS NOT NULL AND user_id IS NULL AND purchase_id IS NULL) OR "
            "(kind='INVOICE' AND purchase_id IS NOT NULL AND user_id IS NULL AND product_id IS NULL)",
            name="media_kind_fk_check",
        ),
    )
