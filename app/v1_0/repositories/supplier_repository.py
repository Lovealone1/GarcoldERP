from typing import Optional, List, Tuple, Dict, Any
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.v1_0.models import Supplier
from app.v1_0.schemas import SupplierCreate
from .base_repository import BaseRepository

class SupplierRepository(BaseRepository[Supplier]):
    def __init__(self) -> None:
        super().__init__(Supplier)

    async def create_supplier(
        self,
        payload: SupplierCreate,
        session: AsyncSession
    ) -> Supplier:
        """
        Create a Supplier from input schema and flush to assign PK.
        """
        entity = Supplier(
            name=payload.name,
            tax_id=payload.tax_id,
            email=payload.email,
            phone=payload.phone,
            address=payload.address,
            city=payload.city,
            created_at=payload.created_at if getattr(payload, "created_at", None) else None,
        )
        await self.add(entity, session)
        return entity

    async def get_supplier_by_id(
        self,
        supplier_id: int,
        session: AsyncSession
    ) -> Optional[Supplier]:
        return await super().get_by_id(supplier_id, session)

    async def update_supplier(
        self,
        supplier_id: int,
        data: Dict[str, Any],
        session: AsyncSession
    ) -> Optional[Supplier]:
        """
        Partial update from a dict. Allowed fields are English-only.
        """
        entity = await self.get_supplier_by_id(supplier_id, session)
        if not entity:
            return None

        allowed_fields = {"name", "tax_id", "email", "phone", "address", "city"}
        for k, v in data.items():
            if k in allowed_fields:
                setattr(entity, k, v)

        await self.update(entity, session)
        return entity

    async def delete_supplier(
        self,
        supplier_id: int,
        session: AsyncSession
    ) -> bool:
        entity = await self.get_supplier_by_id(supplier_id, session)
        if not entity:
            return False
        await self.delete(entity, session)
        return True

    async def list_paginated(
    self, offset: int, limit: int, session: AsyncSession
    ) -> Tuple[List[Supplier], int]:
        stmt = (
            select(Supplier)
            .order_by(Supplier.id.asc())
            .offset(offset)
            .limit(limit)
        )

        result = await session.execute(stmt)
        items: List[Supplier] = list(result.scalars().all())   
        total: int = (await session.scalar(select(func.count(Supplier.id)))) or 0
        return items, total

    async def list_suppliers(
        self,
        session: AsyncSession
    ) -> List[Tuple[int, str]]:
        """
        Return ALL suppliers as (id, name), ordered by name ASC.
        """
        stmt = select(Supplier.id, Supplier.name).order_by(Supplier.name.asc())
        rows = await session.execute(stmt)
        return [(sid, name) for sid, name in rows.all()]