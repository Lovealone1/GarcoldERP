# app/v1_0/services/profit_service.py

from math import ceil
from typing import List
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.v1_0.repositories import (
    ProfitRepository,
    ProfitItemRepository,
    ProductRepository,
)
from app.v1_0.models import Profit
from app.v1_0.entities import (
    ProfitDTO,
    ProfitPageDTO,
    ProfitItemDTO,
)



class ProfitService:
    def __init__(
        self,
        profit_repository: ProfitRepository,
        profit_item_repository: ProfitItemRepository,
        product_repository: ProductRepository,
    ) -> None:
        self.profit_repository = profit_repository
        self.profit_item_repository = profit_item_repository
        self.product_repository = product_repository
        self.PAGE_SIZE = 16
    async def list_profits(self, page: int, db: AsyncSession) -> ProfitPageDTO:
        """
        Paginated list of profits ordered by id asc.
        """
        offset = (page - 1) * self.PAGE_SIZE
        async with db.begin():
            items, total = await self.profit_repository.list_paginated(
                offset=offset, limit=self.PAGE_SIZE, session=db
            )

        total = int(total or 0)
        total_pages = max(1, ceil(total / self.PAGE_SIZE)) if total else 1
        items=[
                ProfitDTO(
                    id=p.id,
                    sale_id=p.sale_id,
                    profit=float(p.profit),
                    created_at=p.created_at,
                )
                for p in items
            ]
        return ProfitPageDTO(
            items = items,
            page=page,
            page_size=self.PAGE_SIZE,
            total=total,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1,
        )

    async def get_by_sale_id(self, sale_id: int, db: AsyncSession) -> Profit:
        """
        Return the Profit record associated with a sale_id.
        Raises 404 if not found.
        """
        async with db.begin():
            profit = await self.profit_repository.get_by_sale(
                sale_id=sale_id, session=db
            )
            if not profit:
                raise HTTPException(status_code=404, detail="Profit not found for the given sale.")
            return profit

    async def get_details_by_sale(
        self,
        sale_id: int,
        db: AsyncSession,
    ) -> List[ProfitItemDTO]:
        """
        Return all ProfitItem rows for the sale, mapped to DTOs
        including product reference and description. If your DB stores
        profit_total as a generated column, we still compute it here to keep the DTO consistent.
        """
        async with db.begin():
            rows = await self.profit_item_repository.get_by_sale(
                sale_id=sale_id, session=db
            )

            dtos: List[ProfitItemDTO] = []
            for r in rows:
                prod = await self.product_repository.get_by_id(r.product_id, session=db)
                reference = getattr(prod, "reference", None) if prod else None
                description = getattr(prod, "description", None) if prod else None

                # Safe compute (works even if DB has generated column)
                try:
                    unit_profit = float(r.sale_price) - float(r.purchase_price)
                    total_profit = unit_profit * int(r.quantity)
                except Exception:
                    total_profit = float(getattr(r, "profit_total", 0.0) or 0.0)

                dtos.append(
                    ProfitItemDTO(
                        sale_id=r.sale_id,
                        product_id=r.product_id,
                        reference=reference,
                        description=description,
                        quantity=int(r.quantity),
                        purchase_price=float(r.purchase_price),
                        sale_price=float(r.sale_price),
                        profit_total=float(total_profit),
                    )
                )

        return dtos
