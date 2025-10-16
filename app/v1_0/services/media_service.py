from typing import List, Dict
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.v1_0.models import Media
from app.v1_0.repositories import MediaRepository
from app.storage.cloud_storage.service import CloudStorageService

class MediaService:
    def __init__(self, media_repository: MediaRepository, storage: CloudStorageService) -> None:
        self.repo = media_repository
        self.storage = storage

    async def confirm_product_image(
        self, db: AsyncSession, product_id: int, *, key: str, content_type: str,
        bytes: int | None, checksum: str | None,
    ) -> Media:
        cnt = await self.repo.count_product_images(db, product_id)
        if cnt >= 3:
            try: self.storage.delete(key)
            except Exception: pass
            raise HTTPException(409, "máximo 3 imágenes por producto")

        row = Media(
            kind="PRODUCT",
            product_id=product_id,
            key=key,
            public_url=self.storage.view_url(key),
            content_type=content_type,
            bytes=bytes,
            checksum=checksum,
        )
        await self.repo.insert(db, row); await db.commit(); await db.refresh(row)
        return row

    async def confirm_purchase_invoice(
        self, db: AsyncSession, purchase_id: int, *, key: str, content_type: str,
        bytes: int | None, checksum: str | None,
    ) -> Media:
        row = Media(
            kind="INVOICE",
            purchase_id=purchase_id,
            key=key,
            public_url=self.storage.view_url(key),
            content_type=content_type,
            bytes=bytes,
            checksum=checksum,
        )
        await self.repo.insert(db, row); await db.commit(); await db.refresh(row)
        return row

    async def delete_media(self, db: AsyncSession, media_id: int) -> None:
        row = await self.repo.get_by_id(db, media_id)
        if not row: raise HTTPException(404, "no existe")
        await self.repo.delete(db, media_id); await db.commit()
        try: self.storage.delete(row.key)
        except Exception: pass

    async def list_product_images(self, db: AsyncSession, product_id: int) -> List[Media]:
        return await self.repo.list_by_product(db, product_id)

    async def list_product_image_urls(self, db: AsyncSession, product_id: int) -> List[Dict[str, str]]:
        rows = await self.repo.list_by_product(db, product_id)
        return [{"id": str(r.id), "key": r.key, "url": self.storage.view_url(r.key), "content_type": r.content_type} for r in rows]

    async def list_purchase_invoices(self, db: AsyncSession, purchase_id: int) -> List[Media]:
        return await self.repo.list_by_purchase(db, purchase_id)

    async def list_purchase_invoice_urls(self, db: AsyncSession, purchase_id: int) -> List[Dict[str, str]]:
        rows = await self.repo.list_by_purchase(db, purchase_id)
        return [{"id": str(r.id), "key": r.key, "url": self.storage.view_url(r.key), "content_type": r.content_type} for r in rows]

