from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.v1_0.models import Media

class MediaRepository:
    async def get_by_id(self, db: AsyncSession, media_id: int) -> Media | None:
        return await db.scalar(select(Media).where(Media.id == media_id))

    async def get_by_key(self, db: AsyncSession, key: str) -> Media | None:
        return await db.scalar(select(Media).where(Media.key == key))

    async def list_by_product(self, db: AsyncSession, product_id: int) -> list[Media]:
        q = select(Media).where(Media.kind == "PRODUCT", Media.product_id == product_id)
        res = await db.execute(q)
        return list(res.scalars().all())

    async def list_by_purchase(self, db: AsyncSession, purchase_id: int) -> list[Media]:
        q = select(Media).where(Media.kind == "INVOICE", Media.purchase_id == purchase_id)
        res = await db.execute(q)
        return list(res.scalars().all())

    async def count_product_images(self, db: AsyncSession, product_id: int) -> int:
        q = select(func.count()).select_from(Media).where(Media.kind == "PRODUCT", Media.product_id == product_id)
        return (await db.scalar(q)) or 0

    async def insert(self, db: AsyncSession, row: Media) -> Media:
        try:
            db.add(row)
            await db.flush()
            return row
        except IntegrityError:
            existing = await self.get_by_key(db, row.key)
            if existing:
                return existing
            raise  

    async def delete(self, db: AsyncSession, media_id: int) -> None:
        await db.execute(delete(Media).where(Media.id == media_id))
