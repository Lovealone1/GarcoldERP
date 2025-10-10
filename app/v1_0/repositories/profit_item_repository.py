from typing import List
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.v1_0.models import SaleProfitDetail
from app.v1_0.schemas import SaleProfitDetailCreate
from .base_repository import BaseRepository


class SaleProfitDetailRepository(BaseRepository[SaleProfitDetail]):
    def __init__(self) -> None:
        super().__init__(SaleProfitDetail)

    async def create_detail(
        self,
        payload: SaleProfitDetailCreate,
        session: AsyncSession
    ) -> SaleProfitDetail:
        """
        Create a new SaleProfitDetail from input schema and flush.
        """
        detail = SaleProfitDetail(
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
    ) -> List[SaleProfitDetail]:
        """
        Return all profit detail records for a given sale.
        """
        stmt = select(SaleProfitDetail).where(SaleProfitDetail.sale_id == sale_id)
        result = await session.execute(stmt)
        return result.scalars().all()

    async def bulk_insert_details(
        self,
        payloads: List[SaleProfitDetailCreate],
        session: AsyncSession,
    ) -> List[SaleProfitDetail]:
        """
        Bulk insert multiple SaleProfitDetail records.
        """
        details = [
            SaleProfitDetail(
                sale_id=p.sale_id,
                product_id=p.product_id,
                reference=p.reference,
                description=p.description,
                quantity=p.quantity,
                purchase_price=p.purchase_price,
                sale_price=p.sale_price,
                total_profit=p.total_profit,
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
        stmt = delete(SaleProfitDetail).where(SaleProfitDetail.sale_id == sale_id)
        result = await session.execute(stmt)
        await session.flush()
        return int(result.rowcount or 0)
