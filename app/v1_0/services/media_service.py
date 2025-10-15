from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.v1_0.models import Media
from app.v1_0.repositories import MediaRepository
from app.storage.cloud_storage.service import CloudStorageService


class MediaService:
    def __init__(self, media_repository: MediaRepository, storage: CloudStorageService) -> None:
        self.repo = media_repository
        self.storage = storage  # CloudStorageService debe exponer delete(key: str)

    async def confirm_user_avatar(
        self,
        db: AsyncSession,
        user_id: int,
        *,
        key: str,
        public_url: str,
        content_type: str,
        bytes: int | None,
        checksum: str | None,
    ) -> Media:
        prev = await self.repo.get_user_avatar(db, user_id)
        if prev:
            await self.repo.delete(db, prev.id)
            try:
                self.storage.delete(prev.key)
            except Exception:
                pass

        row = Media(
            kind="AVATAR",
            user_id=user_id,
            key=key,
            public_url=public_url,
            content_type=content_type,
            bytes=bytes,
            checksum=checksum,
        )
        await self.repo.insert(db, row)
        await db.commit()
        await db.refresh(row)
        return row

    async def confirm_product_image(
        self,
        db: AsyncSession,
        product_id: int,
        *,
        key: str,
        public_url: str,
        content_type: str,
        bytes: int | None,
        checksum: str | None,
    ) -> Media:
        cnt = await self.repo.count_product_images(db, product_id)
        if cnt >= 3:
            try:
                self.storage.delete(key)
            except Exception:
                pass
            raise HTTPException(409, "máximo 3 imágenes por producto")

        row = Media(
            kind="PRODUCT",
            product_id=product_id,
            key=key,
            public_url=public_url,
            content_type=content_type,
            bytes=bytes,
            checksum=checksum,
        )
        await self.repo.insert(db, row)
        await db.commit()
        await db.refresh(row)
        return row

    async def confirm_purchase_invoice(
        self,
        db: AsyncSession,
        purchase_id: int,
        *,
        key: str,
        public_url: str,
        content_type: str,
        bytes: int | None,
        checksum: str | None,
    ) -> Media:
        row = Media(
            kind="INVOICE",
            purchase_id=purchase_id,
            key=key,
            public_url=public_url,
            content_type=content_type,
            bytes=bytes,
            checksum=checksum,
        )
        await self.repo.insert(db, row)
        await db.commit()
        await db.refresh(row)
        return row

    async def delete_media(self, db: AsyncSession, media_id: int) -> None:
        row = await self.repo.get_by_id(db, media_id)
        if not row:
            raise HTTPException(404, "no existe")

        await self.repo.delete(db, media_id)
        await db.commit()

        try:
            self.storage.delete(row.key)
        except Exception:
            pass
