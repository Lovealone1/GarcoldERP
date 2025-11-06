from typing import Optional, List, Dict, Any, Tuple, Iterable, Mapping
from datetime import date, timedelta

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.v1_0.models import Product, SaleItem, Sale
from app.v1_0.schemas import ProductUpsert
from app.v1_0.entities import SaleProductsDTO  
from .base_repository import BaseRepository
from .paginated import list_paginated_keyset

class ProductRepository(BaseRepository[Product]):
    def __init__(self) -> None:
        super().__init__(Product)

    async def create_product(
        self,
        payload: ProductUpsert,
        session: AsyncSession
    ) -> Product:
        entity = Product(
            reference=payload.reference,
            description=payload.description,
            purchase_price=payload.purchase_price,
            sale_price=payload.sale_price,
            quantity=payload.quantity,
        )
        await self.add(entity, session)
        return entity

    async def get_product_by_id(
        self,
        product_id: int,
        session: AsyncSession
    ) -> Optional[Product]:
        return await super().get_by_id(product_id, session)

    async def update_product(
        self,
        product_id: int,
        payload: ProductUpsert,
        session: AsyncSession
    ) -> Optional[Product]:
        entity = await self.get_product_by_id(product_id, session)
        if not entity:
            return None

        data = payload.model_dump(exclude_unset=True)
        allowed = {"reference", "description", "purchase_price", "sale_price", "quantity"}
        for k, v in data.items():
            if k in allowed:
                setattr(entity, k, v)

        await self.update(entity, session)
        return entity

    async def delete_product(
        self,
        product_id: int,
        session: AsyncSession
    ) -> bool:
        entity = await self.get_product_by_id(product_id, session)
        if not entity:
            return False
        await self.delete(entity, session)
        return True

    async def increase_quantity(
        self,
        product_id: int,
        amount: int,
        session: AsyncSession
    ) -> Optional[Product]:
        entity = await self.get_product_by_id(product_id, session)
        if not entity:
            return None
        entity.quantity = (entity.quantity or 0) + amount
        await self.update(entity, session)
        return entity

    async def toggle_active(
        self,
        product_id: int,
        session: AsyncSession
    ) -> Optional[Product]:
        """Invierte el flag is_active de un Product y devuelve la entidad."""
        entity = await self.get_product_by_id(product_id, session)
        if not entity:
            return None
        entity.is_active = not bool(entity.is_active)
        await self.update(entity, session)
        return entity

    async def decrease_quantity(
        self,
        product_id: int,
        amount: int,
        session: AsyncSession
    ) -> Optional[Product]:
        entity = await self.get_product_by_id(product_id, session)
        if not entity or (entity.quantity or 0) < amount:
            return None
        entity.quantity -= amount
        await self.update(entity, session)
        return entity

    async def list_paginated(
        self, *, offset: int, limit: int, session: AsyncSession
    ) -> Tuple[List[Product], int, bool]:
        items, total, has_next = await list_paginated_keyset(
            session=session,
            model=Product,
            created_col=Product.created_at,  
            id_col=Product.id,
            limit=limit,
            offset=offset,
            base_filters=(),                  
            eager=(),                       
            pin_enabled=False,               
            pin_predicate=None,
        )
        return items, total, has_next

    async def list_products(self, session: AsyncSession) -> List[Product]:
        stmt = (
            select(Product)
            .where(Product.is_active.is_(True))
            .order_by(Product.id.asc())
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def top_products_by_quantity(
        self,
        session: AsyncSession,
        date_from: date,
        date_to: date,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Top products by summed quantity in range.
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
            .where(and_(Sale.created_at >= date_from, Sale.created_at < upper_exclusive))
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

    async def sold_products_in_range(
    self,
    db: AsyncSession,
    *,
    date_from: date,
    date_to: date,
    product_ids: List[int],
    ) -> List[SaleProductsDTO]:
        if date_from > date_to:
            date_from, date_to = date_to, date_from
        upper_exclusive = date_to + timedelta(days=1)

        qty_sum = func.coalesce(func.sum(SaleItem.quantity), 0)
        revenue_sum = func.coalesce(func.sum(SaleItem.unit_price * SaleItem.quantity), 0)
        avg_unit_price = revenue_sum / func.nullif(qty_sum, 0)

        stmt = (
            select(
                Product.id.label("id"),
                Product.reference.label("reference"),
                Product.description.label("description"),
                qty_sum.label("quantity_sold"),
                Product.purchase_price.label("purchase_price"),
                func.coalesce(avg_unit_price, 0).label("sale_price"),  # ← desde sale_item.unit_price
            )
            .join(SaleItem, SaleItem.product_id == Product.id)
            .join(Sale, Sale.id == SaleItem.sale_id)
            .where(and_(Sale.created_at >= date_from, Sale.created_at < upper_exclusive))
            .where(Product.id.in_(product_ids))
            .group_by(
                Product.id,
                Product.reference,
                Product.description,
                Product.purchase_price,
            )
            .order_by(qty_sum.desc())
        )

        rows = (await db.execute(stmt)).mappings().all()

        return [
            SaleProductsDTO(
                id=r["id"],
                reference=r["reference"],
                description=r["description"],
                sold_quanity=int(r["quantity_sold"] or 0),
                purchase_price=float(r["purchase_price"] or 0),
                sale_price=float(r["sale_price"] or 0),
            )
            for r in rows
        ]

    async def insert_many(
        self,
        rows: Iterable[Mapping[str, object]],
        session: AsyncSession,
        *,
        chunk_size: int = 100,
    ) -> int:
        """
        Inserta masivamente (sin upsert) en product.
        Omite PK y created_at. Respeta defaults de la DB.
        Retorna la cantidad insertada.
        """
        from sqlalchemy import insert

        insertable = {
            c.name
            for c in Product.__table__.columns
            if not c.primary_key and c.name not in {"created_at"}
        }

        total = 0
        batch: list[dict] = []

        for r in rows:
            m = {k: r.get(k) for k in insertable if r.get(k) is not None}
            if not m:
                continue
            batch.append(m)

            if len(batch) >= chunk_size:
                await session.execute(insert(Product), batch)
                total += len(batch)
                batch.clear()

        if batch:
            await session.execute(insert(Product), batch)
            total += len(batch)

        return total