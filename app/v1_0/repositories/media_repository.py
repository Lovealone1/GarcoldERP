from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.v1_0.models import Media

class MediaRepository:
    async def get_by_id(self, db: AsyncSession, media_id: int) -> Media | None:
        return await db.scalar(select(Media).where(Media.id == media_id))

    async def get_user_avatar(self, db: AsyncSession, user_id: int) -> Media | None:
        return await db.scalar(select(Media).where(Media.kind=='AVATAR', Media.user_id==user_id))

    async def count_product_images(self, db: AsyncSession, product_id: int) -> int:
        return await db.scalar(select(func.count()).select_from(Media).where(Media.kind=='PRODUCT', Media.product_id==product_id)) or 0

    async def insert(self, db: AsyncSession, row: Media) -> Media:
        db.add(row); await db.flush(); return row

    async def delete(self, db: AsyncSession, media_id: int) -> None:
        await db.execute(delete(Media).where(Media.id == media_id))
