from typing import List, Optional, Dict, Any
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.v1_0.models import PurchaseItem
from app.v1_0.schemas import PurchaseItemCreate
from .base_repository import BaseRepository

class PurchaseItemRepository(BaseRepository[PurchaseItem]):
    def __init__(self) -> None:
        super().__init__(PurchaseItem)

    async def create_item(
        self,
        payload: PurchaseItemCreate,
        session: AsyncSession
    ) -> PurchaseItem:
        """
        Create a PurchaseItem from input schema and flush.
        Note: `total` is computed by DB.
        """
        item = PurchaseItem(
            purchase_id=payload.purchase_id,
            product_id=payload.product_id,
            quantity=payload.quantity,
            unit_price=payload.unit_price,
        )
        await self.add(item, session)
        return item

    async def get_by_id(
        self,
        item_id: int,
        session: AsyncSession
    ) -> Optional[PurchaseItem]:
        return await super().get_by_id(item_id, session)

    async def get_by_purchase_id(
        self,
        purchase_id: int,
        session: AsyncSession
    ) -> List[PurchaseItem]:
        """
        Return all items for a purchase.
        """
        stmt = select(PurchaseItem).where(PurchaseItem.purchase_id == purchase_id)
        return (await session.execute(stmt)).scalars().all()

    async def update_item(
        self,
        item_id: int,
        data: Dict[str, Any],
        session: AsyncSession
    ) -> Optional[PurchaseItem]:
        """
        Partial update from a dict. Allowed: product_id, quantity, unit_price, purchase_id.
        """
        item = await self.get_by_id(item_id, session)
        if not item:
            return None

        allowed = {"product_id", "quantity", "unit_price", "purchase_id"}
        for k, v in data.items():
            if k in allowed:
                setattr(item, k, v)

        await self.update(item, session)
        return item

    async def delete_item(
        self,
        item_id: int,
        session: AsyncSession
    ) -> bool:
        item = await self.get_by_id(item_id, session)
        if not item:
            return False
        await self.delete(item, session)
        return True

    async def bulk_insert_items(
        self,
        payloads: List[PurchaseItemCreate],
        session: AsyncSession,
    ) -> List[PurchaseItem]:
        """
        Bulk insert multiple PurchaseItems.
        """
        objects = [
            PurchaseItem(
                purchase_id=p.purchase_id,
                product_id=p.product_id,
                quantity=p.quantity,
                unit_price=p.unit_price,
            )
            for p in payloads
        ]
        session.add_all(objects)
        await session.flush()
        return objects

    async def delete_by_purchase(
        self,
        purchase_id: int,
        session: AsyncSession
    ) -> int:
        """
        Delete all items for a purchase. Return affected rows.
        """
        stmt = delete(PurchaseItem).where(PurchaseItem.purchase_id == purchase_id)
        result = await session.execute(stmt)
        await session.flush()
        return int(result.rowcount or 0)
