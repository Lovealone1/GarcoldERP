from typing import Optional, List, Dict, Any, Sequence
from datetime import date, timedelta

from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.v1_0.models import SaleItem, Sale
from app.v1_0.schemas import SaleItemCreate
from .base_repository import BaseRepository

class SaleItemRepository(BaseRepository[SaleItem]):
    def __init__(self) -> None:
        super().__init__(SaleItem)

    async def get_by_sale_id(
    self,
    sale_id: int,
    session: AsyncSession
    ) -> Sequence[SaleItem]:
        """
        Return all SaleItem rows linked to a sale_id.
        """
        stmt = select(SaleItem).where(SaleItem.sale_id == sale_id)
        result = await session.scalars(stmt)
        return result.all()

    async def delete_item(
        self,
        item_id: int,
        session: AsyncSession
    ) -> bool:
        """
        Delete a SaleItem by its ID. Return True if it existed.
        """
        item = await self.get_by_id(item_id, session)
        if not item:
            return False
        await self.delete(item, session)
        return True

    async def bulk_insert_items(
        self,
        payloads: list[SaleItemCreate],
        session: AsyncSession,
    ) -> list[SaleItem]:
        """
        Bulk insert SaleItem rows.
        """
        objects = [
            SaleItem(
                sale_id=p.sale_id,
                product_id=p.product_id,
                quantity=p.quantity,
                unit_price=p.unit_price,
            )
            for p in payloads
        ]
        session.add_all(objects)
        await session.flush()
        return objects

    async def delete_by_sale(
        self,
        sale_id: int,
        session: AsyncSession
    ) -> int:
        """
        Delete all SaleItem rows for a sale_id. Return affected rows.
        """
        stmt = delete(SaleItem).where(SaleItem.sale_id == sale_id)
        result = await session.execute(stmt)
        await session.flush()
        return int(result.rowcount or 0)

    async def items_by_date_range(
        self,
        session: AsyncSession,
        date_from: date,
        date_to: date,
    ) -> List[Dict[str, Any]]:
        """
        Raw rows within [date_from, date_to]:
        [{ "sale_id": int, "product_id": int, "quantity": int }, ...]
        Uses Sale.sale_date for filtering by day.
        """
        if date_from > date_to:
            date_from, date_to = date_to, date_from
        upper_exclusive = date_to + timedelta(days=1)

        stmt = (
            select(
                SaleItem.sale_id,
                SaleItem.product_id,
                SaleItem.quantity,
            )
            .join(Sale, Sale.id == SaleItem.sale_id)
            .where(Sale.created_at >= date_from)
            .where(Sale.created_at < upper_exclusive)
            .order_by(Sale.created_at.asc(), SaleItem.sale_id.asc())
        )
        rows = await session.execute(stmt)
        return [
            {
                "sale_id": r.sale_id,
                "product_id": r.product_id,
                "quantity": int(r.quantity or 0),
            }
            for r in rows
        ]

    async def top_products_by_quantity(
        self,
        session: AsyncSession,
        date_from: date,
        date_to: date,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Top-selling products by summed quantity in the range.
        Returns: [{ "product_id": int, "total_quantity": float }, ...]
        """
        if date_from > date_to:
            date_from, date_to = date_to, date_from
        upper_exclusive = date_to + timedelta(days=1)

        stmt = (
            select(
                SaleItem.product_id,
                func.coalesce(func.sum(SaleItem.quantity), 0).label("total_quantity"),
            )
            .join(Sale, Sale.id == SaleItem.sale_id)
            .where(Sale.created_at >= date_from)
            .where(Sale.created_at < upper_exclusive)
            .group_by(SaleItem.product_id)
            .order_by(func.sum(SaleItem.quantity).desc())
        )
        if limit:
            stmt = stmt.limit(limit)
        else:
            stmt = stmt.limit(10)

        rows = await session.execute(stmt)
        return [
            {"product_id": r.product_id, "total_quantity": float(r.total_quantity or 0.0)}
            for r in rows
        ]
