from typing import List, Dict, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.v1_0.helper.io.schemas import PRODUCT_SCHEMA
from app.v1_0.models.product import Product

ALLOW_FIELDS = set(PRODUCT_SCHEMA.field_names)

class ProductAdapter:
    schema = PRODUCT_SCHEMA

    async def upsert(self, s: AsyncSession, rows: List[Dict]) -> Tuple[int, int]:
        refs = [r.get("reference") for r in rows if r.get("reference")]
        existing: Dict[str, int] = {}
        if refs:
            for _id, ref in (await s.execute(
                select(Product.id, Product.reference).where(Product.reference.in_(refs))
            )).all():
                existing[ref] = _id

        to_insert, to_update = [], []
        for r in rows:
            ref = r.get("reference")
            if ref in existing:
                to_update.append((existing[ref], r))
            else:
                to_insert.append(r)

        for m in to_insert:
            payload = {k: m.get(k) for k in ALLOW_FIELDS if k in m}
            s.add(Product(**payload))

        updated = 0
        for obj_id, m in to_update:
            obj = await s.get(Product, obj_id)
            if not obj:
                continue
            for k in ALLOW_FIELDS:
                if k in m and m[k] is not None:
                    setattr(obj, k, m[k])
            updated += 1

        return len(to_insert), updated

    async def query_rows(self, s: AsyncSession, query: str | None) -> List[Dict]:
        q = select(Product)
        if query and ":" in query:
            field, term = query.split(":", 1)
            if hasattr(Product, field):
                q = q.where(getattr(Product, field).ilike(f"%{term}%"))
        data = (await s.execute(q)).scalars().all()
        return [
            {
                "reference": p.reference,
                "description": p.description,
                "quantity": p.quantity,
                "purchase_price": p.purchase_price,
                "sale_price": p.sale_price,
                "is_active": p.is_active,
            }
            for p in data
        ]
