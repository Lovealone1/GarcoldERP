from typing import Optional, List, Tuple, Iterable, Mapping
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.v1_0.models import Customer
from app.v1_0.schemas import CustomerCreate, CustomerUpdate
from .base_repository import BaseRepository

class CustomerRepository(BaseRepository[Customer]):
    def __init__(self):
        super().__init__(Customer)
    
    async def create_customer(self, payload: CustomerCreate, session: AsyncSession) -> Customer:
        c = Customer(
            name=payload.name,
            tax_id=payload.tax_id,
            email=payload.email,
            phone=payload.phone,
            address=payload.address,
            city=payload.city,
            balance=payload.balance,
        )
        await self.add(c, session)
        return c

    async def get_customer_by_id(self, customer_id: int, session: AsyncSession) -> Optional[Customer]:
        return await super().get_by_id(customer_id, session)
    
    async def get_by_name(self, name: str, session: AsyncSession) -> Optional[Customer]:
        stmt = select(Customer).where(func.trim(func.lower(Customer.name)) == func.trim(func.lower(name)))
        return (await session.execute(stmt)).scalars().first()
    
    async def update_customer(self, customer_id: int, payload: CustomerUpdate, session: AsyncSession) -> Optional[Customer]:
        c = await self.get_customer_by_id(customer_id, session)
        if not c:
            return None

        allowed_fields = {"name", "tax_id", "email", "phone", "address", "city"}
        data = payload.model_dump(exclude_unset=True)
        for field, value in data.items():
            if field in allowed_fields:
                setattr(c, field, value)

        await self.update(c, session)
        return c

    async def update_balance(self, customer_id: int, new_balance: float, session: AsyncSession) -> Optional[Customer]:
        c = await self.get_customer_by_id(customer_id, session)
        if not c:
            return None
        c.balance = new_balance
        await self.update(c, session)
        return c

    async def decrease_balance(self, customer_id: int, amount: float, session: AsyncSession) -> Optional[Customer]:
        """
        Decrease customer's balance by `amount` (floored at 0).
        """
        c = await self.get_customer_by_id(customer_id, session)
        if not c:
            return None
        current = float(c.balance or 0.0)
        c.balance = max(current - float(amount or 0.0), 0.0)
        await self.update(c, session)
        return c

    async def increase_balance(
    self,
    customer_id: int,
    amount: float,
    session: AsyncSession,
    ) -> Optional[Customer]:
        """
        Increase customer's balance by `amount` (treats None as 0).
        """
        c = await self.get_customer_by_id(customer_id, session)
        if not c:
            return None
        inc = max(float(amount or 0.0), 0.0)
        current = float(c.balance or 0.0)
        c.balance = current + inc
        await self.update(c, session)
        return c

    async def delete_customer(self, customer_id: int, session: AsyncSession) -> bool:
        c = await self.get_customer_by_id(customer_id, session)
        if not c:
            return False
        await self.delete(c, session)
        return True

    async def list_paginated(
    self, offset: int, limit: int, session: AsyncSession
    ) -> Tuple[List[Customer], int]:
        stmt = (
            select(Customer)
            .order_by(Customer.id.asc())
            .offset(offset)
            .limit(limit)
        )
        result = await session.execute(stmt)
        items: List[Customer] = list(result.scalars().all())
        total: int = (await session.scalar(select(func.count(Customer.id)))) or 0
        return items, total
    
    async def insert_many(
    self,
    rows: Iterable[Mapping[str, object]],
    session: AsyncSession,
    *,
    chunk_size: int = 100,
    ) -> int:
        from sqlalchemy import insert

        insertable = {
            c.name
            for c in Customer.__table__.columns
            if not c.primary_key and c.name not in {"created_at"}
        }

        total = 0
        batch: list[dict] = []

        for r in rows:
            m = {k: r.get(k) for k in insertable if r.get(k) is not None}
            if "balance" in insertable and m.get("balance") is None:
                m["balance"] = 0.0
            if not m:
                continue
            batch.append(m)

            if len(batch) >= chunk_size:
                await session.execute(insert(Customer), batch)
                total += len(batch)
                batch.clear()

        if batch:
            await session.execute(insert(Customer), batch)
            total += len(batch)

        return total