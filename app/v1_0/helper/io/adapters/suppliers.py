from typing import List, Dict, Tuple
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.v1_0.helper.io.schemas import SUPPLIER_SCHEMA
from app.v1_0.models.supplier import Supplier

ALLOW_FIELDS = set(SUPPLIER_SCHEMA.field_names)

class SupplierAdapter:
    schema = SUPPLIER_SCHEMA

    async def upsert(self, s: AsyncSession, rows: List[Dict]) -> Tuple[int, int]:
        docs = [r.get("tax_id") for r in rows if r.get("tax_id")]
        emails = [r.get("email") for r in rows if r.get("email")]

        existing: Dict[Tuple[str | None, str | None], int] = {}
        if docs or emails:
            q = select(Supplier.id, Supplier.tax_id, Supplier.email)
            if docs and emails:
                q = q.where(or_(Supplier.tax_id.in_(docs), Supplier.email.in_(emails)))
            elif docs:
                q = q.where(Supplier.tax_id.in_(docs))
            else:
                q = q.where(Supplier.email.in_(emails))
            for _id, dn, em in (await s.execute(q)).all():
                existing[(dn, em)] = _id
                if dn:
                    existing[(dn, None)] = _id
                if em:
                    existing[(None, em)] = _id

        to_insert, to_update = [], []
        for r in rows:
            key = (r.get("tax_id"), r.get("email"))
            if key in existing:
                to_update.append((existing[key], r))
            else:
                to_insert.append(r)

        for m in to_insert:
            payload = {k: m.get(k) for k in ALLOW_FIELDS if k in m}
            s.add(Supplier(**payload))

        updated = 0
        for obj_id, m in to_update:
            obj = await s.get(Supplier, obj_id)
            if not obj:
                continue
            for k in ALLOW_FIELDS:
                if k in m and m[k] is not None:
                    setattr(obj, k, m[k])
            updated += 1

        return len(to_insert), updated

    async def query_rows(self, s: AsyncSession, query: str | None) -> List[Dict]:
        q = select(Supplier)
        if query and ":" in query:
            field, term = query.split(":", 1)
            if hasattr(Supplier, field):
                q = q.where(getattr(Supplier, field).ilike(f"%{term}%"))
        data = (await s.execute(q)).scalars().all()
        return [
            {
                "name": x.name,
                "tax_id": x.tax_id,
                "email": x.email,
                "phone": x.phone,
                "address": x.address,
                "city": x.city,
            }
            for x in data
        ]
