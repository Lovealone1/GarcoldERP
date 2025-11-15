from typing import List, Dict, Any, Optional
from math import ceil
from datetime import date
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import logger
from app.v1_0.repositories import ProductRepository
from app.v1_0.schemas import ProductUpsert
from app.v1_0.entities import ProductDTO, ProductPageDTO, SaleProductsDTO
from app.core.realtime import publish_realtime_event

class ProductService:
    def __init__(self, product_repository: ProductRepository) -> None:
        self.product_repository = product_repository
        self.PAGE_SIZE = 8

    async def _require(self, product_id: int, db: AsyncSession):
        """
        Ensure that a product exists or raise an HTTP 404 error.

        Args:
            product_id: Identifier of the product to fetch.
            db: Active async database session.

        Returns:
            The ORM product entity if found.

        Raises:
            HTTPException: If the product does not exist.
        """
        p = await self.product_repository.get_product_by_id(product_id, db)
        if not p:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found.")
        return p

    async def create(
        self,
        payload: ProductUpsert,
        db: AsyncSession,
        channel_id: Optional[str] = None,
    ) -> ProductDTO:
        """
        Create a new product with optional barcode uniqueness validation.

        Operations:
        - Validate that the barcode, if provided, is not already used.
        - Persist the product.
        - Map to ProductDTO.
        - On success, optionally emit a realtime "product:created" event.

        Args:
            payload: ProductUpsert data with product fields.
            db: Active async database session.
            channel_id: Optional realtime channel identifier for event publishing.

        Returns:
            ProductDTO representing the created product.

        Raises:
            HTTPException:
                - 409 if the barcode is already in use.
                - 500 if creation fails unexpectedly.
        """
        logger.info("[ProductService] Creating product: %s", payload.model_dump())

        async def _run() -> ProductDTO:
            if payload.barcode:
                existing = await self.product_repository.get_by_barcode(
                    payload.barcode,
                    db,
                )
                if existing:
                    raise HTTPException(
                        status_code=409,
                        detail="Barcode already in use for another product",
                    )

            p = await self.product_repository.create_product(payload, db)

            logger.info("[ProductService] Product created ID=%s", p.id)

            return ProductDTO(
                id=p.id,
                reference=p.reference,
                description=p.description,
                quantity=p.quantity,
                purchase_price=p.purchase_price,
                sale_price=p.sale_price,
                is_active=p.is_active,
                created_at=p.created_at,
                barcode=p.barcode,
                barcode_type=p.barcode_type,
            )

        if not db.in_transaction():
            await db.begin()

        try:
            dto = await _run()
            await db.commit()
        except HTTPException:
            await db.rollback()
            raise
        except Exception as e:
            await db.rollback()
            logger.error("[ProductService] Create failed: %s", e, exc_info=True)
            raise HTTPException(
                status_code=500,
                detail="Failed to create product",
            )

        if channel_id:
            try:
                await publish_realtime_event(
                    channel_id=channel_id,
                    resource="product",
                    action="created",
                    payload={"id": dto.id},
                )
                logger.info(
                    "[ProductService] Realtime product created event published: product_id=%s",
                    dto.id,
                )
            except Exception as e:
                logger.error(
                    "[ProductService] realtime publish failed (create): %s",
                    e,
                    exc_info=True,
                )

        return dto

    async def get(self, product_id: int, db: AsyncSession) -> ProductDTO:
        """
        Retrieve a single product by its identifier.

        Args:
            product_id: Identifier of the product.
            db: Active async database session.

        Returns:
            ProductDTO with product data.

        Raises:
            HTTPException:
                - 404 if not found.
                - 500 if an internal error occurs.
        """
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
                barcode=p.barcode,
                barcode_type=p.barcode_type,
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"[ProductService] Get failed ID={product_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to fetch product")

    async def list_all(self, db: AsyncSession) -> List[ProductDTO]:
        """
        List all products without pagination.

        Args:
            db: Active async database session.

        Returns:
            List of ProductDTO for all products.

        Raises:
            HTTPException: 500 if the query fails.
        """
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
        """
        List products in a paginated format.

        Uses PAGE_SIZE for page size and returns pagination metadata.

        Args:
            page: Page number to retrieve (1-based).
            db: Active async database session.

        Returns:
            ProductPageDTO containing:
                - items: List of ProductDTO.
                - page: Current page.
                - page_size: Items per page.
                - total: Total number of products.
                - total_pages: Total number of pages.
                - has_next: Whether a next page exists.
                - has_prev: Whether a previous page exists.
        """
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
                barcode=p.barcode,
                barcode_type=p.barcode_type
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
        
    async def update(
        self,
        product_id: int,
        payload: ProductUpsert,
        db: AsyncSession,
        channel_id: Optional[str] = None,
    ) -> ProductDTO:
        """
        Update an existing product with new data.

        Operations:
        - Validate barcode uniqueness if provided.
        - Update the product.
        - Map to ProductDTO.
        - On success, optionally emit a realtime "product:updated" event.

        Args:
            product_id: Identifier of the product to update.
            payload: ProductUpsert data with updated fields.
            db: Active async database session.
            channel_id: Optional realtime channel identifier for event publishing.

        Returns:
            ProductDTO representing the updated product.

        Raises:
            HTTPException:
                - 404 if product does not exist.
                - 409 if barcode is already used by another product.
                - 500 if update fails unexpectedly.
        """
        logger.info("[ProductService] Update product ID=%s", product_id)

        async def _run() -> ProductDTO:
            if payload.barcode:
                existing = await self.product_repository.get_by_barcode(
                    payload.barcode,
                    db,
                )
                if existing and existing.id != product_id:
                    raise HTTPException(
                        status_code=409,
                        detail="Barcode already in use for another product",
                    )

            p = await self.product_repository.update_product(
                product_id,
                payload,
                db,
            )
            if not p:
                raise HTTPException(
                    status_code=404,
                    detail="Product not found.",
                )

            return ProductDTO(
                id=p.id,
                reference=p.reference,
                description=p.description,
                quantity=p.quantity,
                purchase_price=p.purchase_price,
                sale_price=p.sale_price,
                is_active=p.is_active,
                created_at=p.created_at,
                barcode=p.barcode,
                barcode_type=p.barcode_type,
            )

        if not db.in_transaction():
            await db.begin()

        try:
            dto = await _run()
            await db.commit()
        except HTTPException:
            await db.rollback()
            raise
        except Exception as e:
            await db.rollback()
            logger.error(
                "[ProductService] Update failed ID=%s: %s",
                product_id,
                e,
                exc_info=True,
            )
            raise HTTPException(
                status_code=500,
                detail="Failed to update product",
            )

        if channel_id:
            try:
                await publish_realtime_event(
                    channel_id=channel_id,
                    resource="product",
                    action="updated",
                    payload={"id": dto.id},
                )
                logger.info(
                    "[ProductService] Realtime product updated event published: product_id=%s",
                    dto.id,
                )
            except Exception as e:
                logger.error(
                    "[ProductService] realtime publish failed (update): %s",
                    e,
                    exc_info=True,
                )

        return dto

    async def delete(
        self,
        product_id: int,
        db: AsyncSession,
        channel_id: Optional[str] = None,
    ) -> bool:
        """
        Delete a product by its identifier.

        Operations:
        - Attempt delete via repository.
        - On success, optionally emit a realtime "product:deleted" event.

        Args:
            product_id: Identifier of the product to delete.
            db: Active async database session.
            channel_id: Optional realtime channel identifier for event publishing.

        Returns:
            True if the product was deleted.

        Raises:
            HTTPException:
                - 404 if product is not found.
                - 500 if deletion fails unexpectedly.
        """
        logger.warning("[ProductService] Delete product ID=%s", product_id)

        async def _run() -> bool:
            ok = await self.product_repository.delete_product(product_id, db)
            if not ok:
                raise HTTPException(
                    status_code=404,
                    detail="Product not found.",
                )
            return True

        if not db.in_transaction():
            await db.begin()

        try:
            ok = await _run()
            await db.commit()
        except HTTPException:
            await db.rollback()
            raise
        except Exception as e:
            await db.rollback()
            logger.error(
                "[ProductService] Delete failed ID=%s: %s",
                product_id,
                e,
                exc_info=True,
            )
            raise HTTPException(
                status_code=500,
                detail="Failed to delete product",
            )

        if channel_id:
            try:
                await publish_realtime_event(
                    channel_id=channel_id,
                    resource="product",
                    action="deleted",
                    payload={"id": product_id},
                )
                logger.info(
                    "[ProductService] Realtime product deleted event published: product_id=%s",
                    product_id,
                )
            except Exception as e:
                logger.error(
                    "[ProductService] realtime publish failed (delete): %s",
                    e,
                    exc_info=True,
                )

        return ok

    async def toggle_active(
        self,
        product_id: int,
        db: AsyncSession,
        channel_id: Optional[str] = None,
    ) -> ProductDTO:
        """
        Toggle the active state of a product.

        Operations:
        - Flip is_active for the product.
        - Map to ProductDTO.
        - On success, optionally emit a realtime "product:updated" event.

        Args:
            product_id: Identifier of the product to toggle.
            db: Active async database session.
            channel_id: Optional realtime channel identifier for event publishing.

        Returns:
            ProductDTO representing the updated product.

        Raises:
            HTTPException:
                - 404 if product not found.
                - 500 if toggle operation fails.
        """
        logger.info("[ProductService] Toggle active ID=%s", product_id)

        async def _run() -> ProductDTO:
            p = await self.product_repository.toggle_active(product_id, db)
            if not p:
                raise HTTPException(
                    status_code=404,
                    detail="Product not found.",
                )
            return ProductDTO(
                id=p.id,
                reference=p.reference,
                description=p.description,
                quantity=p.quantity,
                purchase_price=p.purchase_price,
                sale_price=p.sale_price,
                is_active=p.is_active,
                created_at=p.created_at,
                barcode=p.barcode,
                barcode_type=p.barcode_type,
            )

        if not db.in_transaction():
            await db.begin()

        try:
            dto = await _run()
            await db.commit()
        except HTTPException:
            await db.rollback()
            raise
        except Exception as e:
            await db.rollback()
            logger.error(
                "[ProductService] Toggle active failed ID=%s: %s",
                product_id,
                e,
                exc_info=True,
            )
            raise HTTPException(
                status_code=500,
                detail="Failed to toggle product state",
            )

        if channel_id:
            try:
                await publish_realtime_event(
                    channel_id=channel_id,
                    resource="product",
                    action="updated",  # toggle = cambio de estado
                    payload={"id": dto.id},
                )
                logger.info(
                    "[ProductService] Realtime product toggled event published: product_id=%s",
                    dto.id,
                )
            except Exception as e:
                logger.error(
                    "[ProductService] realtime publish failed (toggle): %s",
                    e,
                    exc_info=True,
                )

        return dto

    async def increase_quantity(self, product_id: int, amount: int, db: AsyncSession) -> ProductDTO:
        """
        Increase product quantity by a positive amount.

        Args:
            product_id: Identifier of the product.
            amount: Quantity to add (must be greater than zero).
            db: Active async database session.

        Returns:
            ProductDTO with updated quantity.

        Raises:
            HTTPException:
                - 400 if amount is not positive.
                - 404 if product not found.
                - 500 if the operation fails.
        """
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
        """
        Decrease product quantity by a positive amount, enforcing non-negative stock.

        Args:
            product_id: Identifier of the product.
            amount: Quantity to subtract (must be greater than zero).
            db: Active async database session.

        Returns:
            ProductDTO with updated quantity.

        Raises:
            HTTPException:
                - 400 if amount is not positive or exceeds available quantity.
                - 404 if product not found.
                - 500 if the operation fails.
        """
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
        """
        Get the top sold products by quantity in a date range.

        Delegates the aggregation to the ProductRepository.

        Args:
            date_from: Start date of the range (inclusive).
            date_to: End date of the range (inclusive).
            db: Active async database session.
            limit: Optional maximum number of results.

        Returns:
            List of dictionaries containing aggregated top product data.

        Raises:
            HTTPException: 500 if the query fails.
        """
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
        """
        Get sold quantity and related info for specific products in a date range.

        Delegates aggregation to the ProductRepository.

        Args:
            db: Active async database session.
            date_from: Start date of the range (inclusive).
            date_to: End date of the range (inclusive).
            product_ids: List of product IDs to filter.

        Returns:
            List of SaleProductsDTO with aggregated sales per product.

        Raises:
            HTTPException: 500 if the query fails.
        """
        logger.debug(f"[ProductService] Sold products in range {date_from}..{date_to} ids={product_ids}")
        try:
            async with db.begin():
                return await self.product_repository.sold_products_in_range(
                    db, date_from=date_from, date_to=date_to, product_ids=product_ids
                )
        except Exception as e:
            logger.error(f"[ProductService] Sold products failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to fetch sold products")

    async def get_by_barcode(self, barcode: str, db: AsyncSession) -> ProductDTO | None:
        """
        Retrieve a product by its barcode.

        Args:
            barcode: Barcode string to search.
            db: Active async database session.

        Returns:
            ProductDTO if a product with the given barcode exists, otherwise None.
        """
        p = await self.product_repository.get_by_barcode(barcode, db)
        if not p:
            return None
        return ProductDTO(
            id=p.id,
            reference=p.reference,
            barcode=p.barcode,
            barcode_type=p.barcode_type,
            description=p.description,
            quantity=p.quantity,
            purchase_price=p.purchase_price,
            sale_price=p.sale_price,
            is_active=p.is_active,
            created_at=p.created_at,
        )