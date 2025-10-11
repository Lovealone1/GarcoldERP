from typing import Optional, List, Tuple
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