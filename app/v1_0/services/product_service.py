from typing import List, Dict, Any, Optional
from math import ceil
from datetime import date
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import logger
from app.v1_0.repositories import ProductRepository
from app.v1_0.schemas import ProductUpsert
from app.v1_0.entities import ProductDTO, ProductPageDTO, SaleProductsDTO


class ProductService:
    def __init__(self, product_repository: ProductRepository) -> None:
        self.product_repository = product_repository
        self.PAGE_SIZE = 8

    async def _require(self, product_id: int, db: AsyncSession):
        p = await self.product_repository.get_product_by_id(product_id, db)
        if not p:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found.")
        return p

    async def create(self, payload: ProductUpsert, db: AsyncSession) -> ProductDTO:
        logger.info(f"[ProductService] Creating product: {payload.model_dump()}")
        try:
            async with db.begin():
                p = await self.product_repository.create_product(payload, db)
            logger.info(f"[ProductService] Product created ID={p.id}")
            return ProductDTO(
                id=p.id,
                reference=p.reference,
                description=p.description,
                quantity=p.quantity,
                purchase_price=p.purchase_price,
                sale_price=p.sale_price,
                is_active=p.is_active,
                created_at=p.created_at,
            )
        except Exception as e:
            logger.error(f"[ProductService] Create failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to create product")

    async def get(self, product_id: int, db: AsyncSession) -> ProductDTO:
        logger.debug(f"[ProductService] Get product ID={product_id}")
        try:
            async with db.begin():
                p = await self._require(product_id, db)
            return ProductDTO(
                id=p.id,
                reference=p.reference,
                description=p.description,
                quantity=p.quantity,
                purchase_price=p.purchase_price,
                sale_price=p.sale_price,
                is_active=p.is_active,
                created_at=p.created_at,
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"[ProductService] Get failed ID={product_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to fetch product")

    async def list_all(self, db: AsyncSession) -> List[ProductDTO]:
        logger.debug("[ProductService] List all products")
        try:
            async with db.begin():
                rows = await self.product_repository.list_products(db)
            return [
                ProductDTO(
                    id=p.id,
                    reference=p.reference,
                    description=p.description,
                    quantity=p.quantity,
                    purchase_price=p.purchase_price,
                    sale_price=p.sale_price,
                    is_active=p.is_active,
                    created_at=p.created_at,
                )
                for p in rows
            ]
        except Exception as e:
            logger.error(f"[ProductService] List failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to list products")

    async def list_paginated(self, page: int, db: AsyncSession) -> ProductPageDTO:
        page_size = self.PAGE_SIZE
        offset = max(page - 1, 0) * page_size

        items, total, *_ = await self.product_repository.list_paginated(
            offset=offset, limit=page_size, session=db
        )

        view_items = [
            ProductDTO(
                id=p.id,
                reference=p.reference,
                description=p.description,
                quantity=p.quantity,
                purchase_price=p.purchase_price,
                sale_price=p.sale_price,
                is_active=p.is_active,
                created_at=p.created_at,
            )
            for p in items
        ]

        total = int(total or 0)
        total_pages = max(1, ceil(total / page_size)) if total else 1

        return ProductPageDTO(
            items=view_items,
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1,
        )
    async def update(self, product_id: int, payload: ProductUpsert, db: AsyncSession) -> ProductDTO:
        logger.info(f"[ProductService] Update product ID={product_id}")
        try:
            async with db.begin():
                p = await self.product_repository.update_product(product_id, payload, db)
            if not p:
                raise HTTPException(status_code=404, detail="Product not found.")
            return ProductDTO(
                id=p.id,
                reference=p.reference,
                description=p.description,
                quantity=p.quantity,
                purchase_price=p.purchase_price,
                sale_price=p.sale_price,
                is_active=p.is_active,
                created_at=p.created_at,
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"[ProductService] Update failed ID={product_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to update product")

    async def delete(self, product_id: int, db: AsyncSession) -> bool:
        logger.warning(f"[ProductService] Delete product ID={product_id}")
        try:
            async with db.begin():
                ok = await self.product_repository.delete_product(product_id, db)
            if not ok:
                raise HTTPException(status_code=404, detail="Product not found.")
            return True
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"[ProductService] Delete failed ID={product_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to delete product")

    async def toggle_active(self, product_id: int, db: AsyncSession) -> ProductDTO:
        logger.info(f"[ProductService] Toggle active ID={product_id}")
        try:
            async with db.begin():
                p = await self.product_repository.toggle_active(product_id, db)
            if not p:
                raise HTTPException(status_code=404, detail="Product not found.")
            return ProductDTO(
                id=p.id,
                reference=p.reference,
                description=p.description,
                quantity=p.quantity,
                purchase_price=p.purchase_price,
                sale_price=p.sale_price,
                is_active=p.is_active,
                created_at=p.created_at,
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"[ProductService] Toggle active failed ID={product_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to toggle product state")

    async def increase_quantity(self, product_id: int, amount: int, db: AsyncSession) -> ProductDTO:
        if amount <= 0:
            raise HTTPException(status_code=400, detail="Amount must be greater than zero.")
        logger.info(f"[ProductService] Increase quantity ID={product_id} by {amount}")
        try:
            async with db.begin():
                p = await self.product_repository.increase_quantity(product_id, amount, db)
            if not p:
                raise HTTPException(status_code=404, detail="Product not found.")
            return ProductDTO(
                id=p.id,
                reference=p.reference,
                description=p.description,
                quantity=p.quantity,
                purchase_price=p.purchase_price,
                sale_price=p.sale_price,
                is_active=p.is_active,
                created_at=p.created_at,
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"[ProductService] Increase quantity failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to increase quantity")

    async def decrease_quantity(self, product_id: int, amount: int, db: AsyncSession) -> ProductDTO:
        if amount <= 0:
            raise HTTPException(status_code=400, detail="Amount must be greater than zero.")
        logger.info(f"[ProductService] Decrease quantity ID={product_id} by {amount}")
        try:
            async with db.begin():
                p = await self._require(product_id, db)
                if (p.quantity or 0) < amount:
                    raise HTTPException(status_code=400, detail="Insufficient quantity.")
                p = await self.product_repository.decrease_quantity(product_id, amount, db)
            if not p:
                raise HTTPException(status_code=404, detail="Product not found.")
            return ProductDTO(
                id=p.id,
                reference=p.reference,
                description=p.description,
                quantity=p.quantity,
                purchase_price=p.purchase_price,
                sale_price=p.sale_price,
                is_active=p.is_active,
                created_at=p.created_at,
                )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"[ProductService] Decrease quantity failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to decrease quantity")

    async def top_products_by_quantity(
        self, *, date_from: date, date_to: date, db: AsyncSession, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        logger.debug(f"[ProductService] Top products {date_from}..{date_to} limit={limit}")
        try:
            async with db.begin():
                return await self.product_repository.top_products_by_quantity(
                    session=db, date_from=date_from, date_to=date_to, limit=limit
                )
        except Exception as e:
            logger.error(f"[ProductService] Top products failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to compute top products")

    async def sold_products_in_range(
        self,
        *,
        db: AsyncSession,
        date_from: date,
        date_to: date,
        product_ids: List[int],
    ) -> List[SaleProductsDTO]:
        logger.debug(f"[ProductService] Sold products in range {date_from}..{date_to} ids={product_ids}")
        try:
            async with db.begin():
                return await self.product_repository.sold_products_in_range(
                    db, date_from=date_from, date_to=date_to, product_ids=product_ids
                )
        except Exception as e:
            logger.error(f"[ProductService] Sold products failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to fetch sold products")
