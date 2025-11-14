from typing import List, Dict, Any, Optional
from math import ceil

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.v1_0.schemas import SupplierCreate
from app.v1_0.repositories import SupplierRepository
from app.v1_0.entities import SupplierDTO, SupplierPageDTO
from app.core.logger import logger
from app.core.realtime import publish_realtime_event

class SupplierService:
    def __init__(self, supplier_repository: SupplierRepository) -> None:
        self.supplier_repository = supplier_repository
        self.PAGE_SIZE = 8

    async def _require(
        self,
        supplier_id: int,
        db: AsyncSession,
    ):
        """
        Ensure that a supplier exists or raise an HTTP 404 error.

        Args:
            supplier_id: Identifier of the supplier to fetch.
            db: Active async database session.

        Returns:
            ORM supplier entity if found.

        Raises:
            HTTPException: If the supplier does not exist.
        """
        s = await self.supplier_repository.get_supplier_by_id(supplier_id, db)
        if not s:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Supplier not found.",
            )
        return s

    async def create(
        self,
        payload: SupplierCreate,
        db: AsyncSession,
        channel_id: Optional[str] = None,
    ) -> SupplierDTO:
        """
        Create a new supplier.

        Operations:
        - Persist supplier data.
        - Map to SupplierDTO.
        - Optionally emit a realtime "supplier:created" event.

        Args:
            payload: SupplierCreate data with supplier fields.
            db: Active async database session.
            channel_id: Optional realtime channel identifier for event publishing.

        Returns:
            SupplierDTO representing the created supplier.

        Raises:
            HTTPException: 500 if creation fails.
        """
        logger.info(
            "[SupplierService] Creating supplier: %s",
            payload.model_dump(),
        )

        async def _run() -> SupplierDTO:
            s = await self.supplier_repository.create_supplier(payload, db)
            logger.info(
                "[SupplierService] Supplier created ID=%s",
                s.id,
            )
            return SupplierDTO(
                id=s.id,
                name=s.name,
                tax_id=s.tax_id,
                email=s.email,
                phone=s.phone,
                address=s.address,
                city=s.city,
                created_at=s.created_at,
            )

        if not db.in_transaction():
            await db.begin()

        try:
            dto = await _run()
            await db.commit()
        except Exception as e:
            await db.rollback()
            logger.error(
                "[SupplierService] Create failed: %s",
                e,
                exc_info=True,
            )
            raise HTTPException(
                status_code=500,
                detail="Failed to create supplier",
            )

        if channel_id:
            try:
                await publish_realtime_event(
                    channel_id=channel_id,
                    resource="supplier",
                    action="created",
                    payload={"id": dto.id},
                )
                logger.info(
                    "[SupplierService] RT supplier created published: id=%s",
                    dto.id,
                )
            except Exception as e:
                logger.error(
                    "[SupplierService] RT publish failed (create): %s",
                    e,
                    exc_info=True,
                )

        return dto

    async def get(
        self,
        supplier_id: int,
        db: AsyncSession,
    ) -> SupplierDTO:
        """
        Retrieve a single supplier by its identifier.

        Args:
            supplier_id: Identifier of the supplier.
            db: Active async database session.

        Returns:
            SupplierDTO with supplier data.

        Raises:
            HTTPException:
                - 404 if not found.
                - 500 if an internal error occurs.
        """
        logger.debug(f"[SupplierService] Get supplier ID={supplier_id}")
        try:
            async with db.begin():
                s = await self._require(supplier_id, db)
            return SupplierDTO(
                id=s.id,
                name=s.name,
                tax_id=s.tax_id,
                email=s.email,
                phone=s.phone,
                address=s.address,
                city=s.city,
                created_at=s.created_at,
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(
                f"[SupplierService] Get failed ID={supplier_id}: {e}",
                exc_info=True,
            )
            raise HTTPException(
                status_code=500,
                detail="Failed to fetch supplier",
            )

    async def list_all(
        self,
        db: AsyncSession,
    ) -> List[SupplierDTO]:
        """
        List all suppliers without pagination.

        Args:
            db: Active async database session.

        Returns:
            List of SupplierDTO for all suppliers.

        Raises:
            HTTPException: 500 if the query fails.
        """
        logger.debug("[SupplierService] List all suppliers")
        try:
            async with db.begin():
                rows = await self.supplier_repository.list_all(db)
            return [
                SupplierDTO(
                    id=s.id,
                    name=s.name,
                    tax_id=s.tax_id,
                    email=s.email,
                    phone=s.phone,
                    address=s.address,
                    city=s.city,
                    created_at=s.created_at,
                )
                for s in rows
            ]
        except Exception as e:
            logger.error(
                "[SupplierService] List failed: %s",
                e,
                exc_info=True,
            )
            raise HTTPException(
                status_code=500,
                detail="Failed to list suppliers",
            )

    async def list_paginated(
        self,
        page: int,
        db: AsyncSession,
    ) -> SupplierPageDTO:
        """
        List suppliers in a paginated format.

        Uses PAGE_SIZE for page size and returns pagination metadata.

        Args:
            page: Page number to retrieve (1-based).
            db: Active async database session.

        Returns:
            SupplierPageDTO containing:
                - items: List of SupplierDTO.
                - page: Current page.
                - page_size: Items per page.
                - total: Total number of suppliers.
                - total_pages: Total number of pages.
                - has_next: Whether a next page exists.
                - has_prev: Whether a previous page exists.
        """
        page_size = self.PAGE_SIZE
        offset = max(page - 1, 0) * page_size

        items, total, *_ = await self.supplier_repository.list_paginated(
            offset=offset,
            limit=page_size,
            session=db,
        )

        view_items = [
            SupplierDTO(
                id=s.id,
                name=s.name,
                tax_id=s.tax_id,
                email=s.email,
                phone=s.phone,
                address=s.address,
                city=s.city,
                created_at=s.created_at,
            )
            for s in items
        ]

        total = int(total or 0)
        total_pages = max(1, ceil(total / page_size)) if total else 1

        return SupplierPageDTO(
            items=view_items,
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1,
        )

    async def update_partial(
        self,
        supplier_id: int,
        data: Dict[str, Any],
        db: AsyncSession,
        channel_id: Optional[str] = None,
    ) -> SupplierDTO:
        """
        Partially update an existing supplier (PATCH-style).

        Operations:
        - Apply only provided fields.
        - Map to SupplierDTO.
        - Optionally emit a realtime "supplier:updated" event.

        Args:
            supplier_id: Identifier of the supplier to update.
            data: Dictionary of fields to update.
            db: Active async database session.
            channel_id: Optional realtime channel identifier for event publishing.

        Returns:
            SupplierDTO representing the updated supplier.

        Raises:
            HTTPException:
                - 404 if supplier not found.
                - 500 if update fails.
        """
        logger.info(
            "[SupplierService] Update supplier ID=%s data=%s",
            supplier_id,
            data,
        )

        async def _run() -> SupplierDTO:
            s = await self.supplier_repository.update_supplier(
                supplier_id,
                data,
                db,
            )
            if not s:
                raise HTTPException(
                    status_code=404,
                    detail="Supplier not found.",
                )
            return SupplierDTO(
                id=s.id,
                name=s.name,
                tax_id=s.tax_id,
                email=s.email,
                phone=s.phone,
                address=s.address,
                city=s.city,
                created_at=s.created_at,
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
                "[SupplierService] Update failed ID=%s: %s",
                supplier_id,
                e,
                exc_info=True,
            )
            raise HTTPException(
                status_code=500,
                detail="Failed to update supplier",
            )

        if channel_id:
            try:
                await publish_realtime_event(
                    channel_id=channel_id,
                    resource="supplier",
                    action="updated",
                    payload={"id": dto.id},
                )
                logger.info(
                    "[SupplierService] RT supplier updated published: id=%s",
                    dto.id,
                )
            except Exception as e:
                logger.error(
                    "[SupplierService] RT publish failed (update): %s",
                    e,
                    exc_info=True,
                )

        return dto

    async def delete(
        self,
        supplier_id: int,
        db: AsyncSession,
        channel_id: Optional[str] = None,
    ) -> bool:
        """
        Delete a supplier by its identifier.

        Operations:
        - Delete via repository.
        - Optionally emit a realtime "supplier:deleted" event.

        Args:
            supplier_id: Identifier of the supplier to delete.
            db: Active async database session.
            channel_id: Optional realtime channel identifier for event publishing.

        Returns:
            True if the supplier was deleted.

        Raises:
            HTTPException:
                - 404 if supplier not found.
                - 500 if deletion fails.
        """
        logger.warning(
            "[SupplierService] Delete supplier ID=%s",
            supplier_id,
        )

        async def _run() -> bool:
            existed = await self.supplier_repository.delete_supplier(
                supplier_id,
                db,
            )
            if not existed:
                raise HTTPException(
                    status_code=404,
                    detail="Supplier not found.",
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
                "[SupplierService] Delete failed ID=%s: %s",
                supplier_id,
                e,
                exc_info=True,
            )
            raise HTTPException(
                status_code=500,
                detail="Failed to delete supplier",
            )

        if channel_id:
            try:
                await publish_realtime_event(
                    channel_id=channel_id,
                    resource="supplier",
                    action="deleted",
                    payload={"id": supplier_id},
                )
                logger.info(
                    "[SupplierService] RT supplier deleted published: id=%s",
                    supplier_id,
                )
            except Exception as e:
                logger.error(
                    "[SupplierService] RT publish failed (delete): %s",
                    e,
                    exc_info=True,
                )

        return True
