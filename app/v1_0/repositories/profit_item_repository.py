from typing import List
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.v1_0.models import ProfitItem
from app.v1_0.schemas import ProfitCreate,SaleProfitDetailCreate
from .base_repository import BaseRepository


class ProfitItemRepository(BaseRepository[ProfitItem]):
    def __init__(self) -> None:
        super().__init__(ProfitItem)

    async def create_detail(
        self,
        payload: SaleProfitDetailCreate,
        session: AsyncSession
    ) -> ProfitItem:
        """
        Create a new ProfitItem from input schema and flush.
        """
        detail = ProfitItem(
                sale_id=payload.sale_id,
                product_id=payload.product_id,
                reference=payload.reference,
                description=payload.description,
                quantity=payload.quantity,
                purchase_price=payload.purchase_price,
                sale_price=payload.sale_price,
                total_profit=payload.total_profit,
            )
        await self.add(detail, session)
        return detail

    async def get_by_sale(
    self,
    sale_id: int,
    session: AsyncSession
    ) -> List[ProfitItem]:
        """
        Return all profit detail records for a given sale.
        """
        stmt = select(ProfitItem).where(ProfitItem.sale_id == sale_id)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def bulk_insert_details(
    self,
    payloads: List[SaleProfitDetailCreate],
    session: AsyncSession,
    ) -> List[ProfitItem]:
        """
        Bulk insert multiple ProfitItem records from SaleProfitDetailCreate payloads.
        """
        details = [
            ProfitItem(
                sale_id=p.sale_id,
                product_id=p.product_id,
                quantity=p.quantity,
                purchase_price=p.purchase_price,
                sale_price=p.sale_price,
            )
            for p in payloads
        ]
        session.add_all(details)
        await session.flush()
        return details

    async def delete_by_sale(
        self,
        sale_id: int,
        session: AsyncSession
    ) -> int:
        """
        Delete all profit detail records for the given sale_id.
        Return number of rows deleted.
        """
        stmt = delete(ProfitItem).where(ProfitItem.sale_id == sale_id)
        result = await session.execute(stmt)
        await session.flush()
        return int(result.rowcount or 0)
