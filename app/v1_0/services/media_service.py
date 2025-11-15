from typing import Dict, List, Optional

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.cloud_storage.service import CloudStorageService
from app.v1_0.models import Media
from app.v1_0.repositories import MediaRepository


class MediaService:
    """Service layer for confirming, listing, and deleting media files."""

    def __init__(self, media_repository: MediaRepository, storage: CloudStorageService) -> None:
        self.repo = media_repository
        self.storage = storage

    async def confirm_product_image(
        self,
        db: AsyncSession,
        product_id: int,
        *,
        key: str,
        content_type: str,
        bytes: int | None,
        checksum: str | None,
    ) -> Media:
        """
        Persist a newly uploaded product image and enforce a max of 3 images per product.

        On overflow the just-uploaded object is deleted from storage and a 409 is raised.

        Args:
            db: Active async DB session.
            product_id: Product identifier.
            key: Storage key returned by the uploader.
            content_type: MIME type.
            bytes: Object size in bytes.
            checksum: Optional checksum provided by the client or storage.

        Returns:
            The persisted Media ORM row.

        Raises:
            HTTPException: 409 if the product already has 3 images.
        """
        cnt = await self.repo.count_product_images(db, product_id)
        if cnt >= 3:
            try:
                self.storage.delete(key)
            except Exception:
                pass
            raise HTTPException(status.HTTP_409_CONFLICT, "máximo 3 imágenes por producto")

        row = Media(
            kind="PRODUCT",
            product_id=product_id,
            key=key,
            public_url=self.storage.view_url(key),
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
        content_type: str,
        bytes: int | None,
        checksum: str | None,
    ) -> Media:
        """
        Persist a newly uploaded purchase invoice image or PDF.

        Args:
            db: Active async DB session.
            purchase_id: Purchase identifier.
            key: Storage key returned by the uploader.
            content_type: MIME type.
            bytes: Object size in bytes.
            checksum: Optional checksum provided by the client or storage.

        Returns:
            The persisted Media ORM row.
        """
        row = Media(
            kind="INVOICE",
            purchase_id=purchase_id,
            key=key,
            public_url=self.storage.view_url(key),
            content_type=content_type,
            bytes=bytes,
            checksum=checksum,
        )
        await self.repo.insert(db, row)
        await db.commit()
        await db.refresh(row)
        return row

    async def delete_media(self, db: AsyncSession, media_id: int) -> None:
        """
        Delete a media record and attempt to remove the underlying object from storage.

        Args:
            db: Active async DB session.
            media_id: Media identifier.

        Raises:
            HTTPException: 404 if the media does not exist.
        """
        row = await self.repo.get_by_id(db, media_id)
        if not row:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "no existe")
        await self.repo.delete(db, media_id)
        await db.commit()
        try:
            self.storage.delete(row.key)
        except Exception:
            pass

    async def list_product_images(self, db: AsyncSession, product_id: int) -> List[Media]:
        """
        List Media rows for a given product.

        Args:
            db: Active async DB session.
            product_id: Product identifier.

        Returns:
            List of Media ORM rows.
        """
        return await self.repo.list_by_product(db, product_id)

    async def list_product_image_urls(self, db: AsyncSession, product_id: int) -> List[Dict[str, str]]:
        """
        List public URLs and metadata for a product's images.

        Args:
            db: Active async DB session.
            product_id: Product identifier.

        Returns:
            List of dicts with id, key, url, and content_type.
        """
        rows = await self.repo.list_by_product(db, product_id)
        return [
            {
                "id": str(r.id),
                "key": r.key,
                "url": self.storage.view_url(r.key),
                "content_type": r.content_type,
            }
            for r in rows
        ]

    async def list_purchase_invoices(self, db: AsyncSession, purchase_id: int) -> List[Media]:
        """
        List Media rows for a given purchase's invoices.

        Args:
            db: Active async DB session.
            purchase_id: Purchase identifier.

        Returns:
            List of Media ORM rows.
        """
        return await self.repo.list_by_purchase(db, purchase_id)

    async def list_purchase_invoice_urls(self, db: AsyncSession, purchase_id: int) -> List[Dict[str, str]]:
        """
        List public URLs and metadata for a purchase's invoice media.

        Args:
            db: Active async DB session.
            purchase_id: Purchase identifier.

        Returns:
            List of dicts with id, key, url, and content_type.
        """
        rows = await self.repo.list_by_purchase(db, purchase_id)
        return [
            {
                "id": str(r.id),
                "key": r.key,
                "url": self.storage.view_url(r.key),
                "content_type": r.content_type,
            }
            for r in rows
        ]
