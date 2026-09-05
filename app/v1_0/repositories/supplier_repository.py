from typing import Optional, List, Tuple, Dict, Any, Iterable, Mapping
from sqlalchemy import select, func, insert, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.v1_0.models import Supplier
from app.v1_0.schemas import SupplierCreate
from .base_repository import BaseRepository
from .paginated import list_paginated_keyset

def _clean(value):
    """A field holding only whitespace means "no filter"."""
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


def build_supplier_filters(*, q=None, cities=None):
    """Translate the suppliers screen's filters into SQL."""
    filters = []

    cleaned_cities = [c.strip() for c in (cities or []) if c and c.strip()]
    if cleaned_cities:
        filters.append(Supplier.city.in_(cleaned_cities))

    term = _clean(q)
    if term:
        like = f"%{term}%"
        conditions = [
            Supplier.name.ilike(like),
            Supplier.tax_id.ilike(like),
            Supplier.email.ilike(like),
            Supplier.phone.ilike(like),
            Supplier.city.ilike(like),
        ]
        if term.isdigit():
            conditions.append(Supplier.id == int(term))
        filters.append(or_(*conditions))

    return filters


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
        self,
        *,
        offset: int,
        limit: int,
        session: AsyncSession,
        q: Optional[str] = None,
        cities: Optional[List[str]] = None,
    ) -> Tuple[list[Supplier], int, bool]:
        items, total, has_next = await list_paginated_keyset(
            session=session,
            model=Supplier,
            created_col=Supplier.created_at,
            id_col=Supplier.id,
            limit=limit,
            offset=offset,
            base_filters=tuple(build_supplier_filters(q=q, cities=cities)),
            eager=(),
            pin_enabled=False,
            pin_predicate=None,
        )
        return items, total, has_next

    async def distinct_cities(self, *, session: AsyncSession) -> List[str]:
        """City names present in suppliers, for the screen's multi-select."""
        rows = (
            await session.execute(
                select(Supplier.city)
                .where(Supplier.city.is_not(None), func.trim(Supplier.city) != "")
                .distinct()
                .order_by(Supplier.city)
            )
        ).scalars().all()
        return list(rows)

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
    
    async def insert_many(
        self,
        rows: Iterable[Mapping[str, object]],
        session: AsyncSession,
        *,
        chunk_size: int = 100,
    ) -> int:
        """
        Inserta proveedores en lotes. No envía PK ni created_at.
        Retorna cantidad insertada. Lanza excepción de DB ante constraint violations.
        """
        cols = {
            c.name
            for c in Supplier.__table__.columns
            if not c.primary_key and c.name not in {"created_at"}
        }

        total = 0
        batch: list[dict] = []

        for r in rows:
            m = {k: r.get(k) for k in cols if r.get(k) is not None}
            if not m:
                continue
            batch.append(m)
            if len(batch) >= chunk_size:
                await session.execute(insert(Supplier), batch)
                total += len(batch)
                batch.clear()

        if batch:
            await session.execute(insert(Supplier), batch)
            total += len(batch)

        return total