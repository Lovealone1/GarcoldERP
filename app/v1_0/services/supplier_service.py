from typing import List, Dict, Any
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from math import ceil

from app.v1_0.schemas import SupplierCreate
from app.v1_0.repositories import SupplierRepository
from app.v1_0.entities import SupplierDTO, SupplierPageDTO  
from app.core.logger import logger

class SupplierService:
    def __init__(self, supplier_repository: SupplierRepository) -> None:
        self.supplier_repository = supplier_repository
        self.PAGE_SIZE = 10

    async def _require(self, supplier_id: int, db: AsyncSession):
        s = await self.supplier_repository.get_supplier_by_id(supplier_id, db)
        if not s:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found.")
        return s

    async def create(self, payload: SupplierCreate, db: AsyncSession) -> SupplierDTO:
        logger.info(f"[SupplierService] Creating supplier: {payload.model_dump()}")
        try:
            async with db.begin():
                s = await self.supplier_repository.create_supplier(payload, db)
            logger.info(f"[SupplierService] Supplier created ID={s.id}")
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
        except Exception as e:
            logger.error(f"[SupplierService] Create failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to create supplier")

    async def get(self, supplier_id: int, db: AsyncSession) -> SupplierDTO:
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
            logger.error(f"[SupplierService] Get failed ID={supplier_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to fetch supplier")

    async def list_all(self, db: AsyncSession) -> List[SupplierDTO]:
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
            logger.error(f"[SupplierService] List failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to list suppliers")

    async def list_paginated(self, page: int, db: AsyncSession) -> SupplierPageDTO:
        page_size = self.PAGE_SIZE
        offset = max(page - 1, 0) * page_size

        items, total, *_ = await self.supplier_repository.list_paginated(
            offset=offset, limit=page_size, session=db
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
        
    async def update_partial(self, supplier_id: int, data: Dict[str, Any], db: AsyncSession) -> SupplierDTO:
        logger.info(f"[SupplierService] Update supplier ID={supplier_id} data={data}")
        try:
            async with db.begin():
                s = await self.supplier_repository.update_supplier(supplier_id, data, db)
            if not s:
                raise HTTPException(status_code=404, detail="Supplier not found.")
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
            logger.error(f"[SupplierService] Update failed ID={supplier_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to update supplier")

    async def delete(self, supplier_id: int, db: AsyncSession) -> bool:
        logger.warning(f"[SupplierService] Delete supplier ID={supplier_id}")
        try:
            async with db.begin():
                existed = await self.supplier_repository.delete_supplier(supplier_id, db)
            if not existed:
                raise HTTPException(status_code=404, detail="Supplier not found.")
            return True
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"[SupplierService] Delete failed ID={supplier_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to delete supplier")
