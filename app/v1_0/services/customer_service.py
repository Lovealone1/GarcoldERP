from typing import List
from math import ceil
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.v1_0.schemas import CustomerCreate, CustomerUpdate, TransactionCreate
from app.v1_0.repositories import CustomerRepository, BankRepository
from .transaction_service import TransactionService
from app.v1_0.entities import CustomerDTO, CustomerPageDTO
from app.core.logger import logger

class CustomerService:
    def __init__(self, 
            customer_repository: CustomerRepository, 
            bank_repository: BankRepository,
            transaction_service:TransactionService ) -> None:
        self.customer_repository = customer_repository
        self.bank_repository = bank_repository
        self.transaction_service = transaction_service
        self.PAGE_SIZE = 10

    async def _require(self, customer_id: int, db: AsyncSession):
        c = await self.customer_repository.get_customer_by_id(customer_id, db)
        if not c:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")
        return c

    async def create(self, payload: CustomerCreate, db: AsyncSession) -> CustomerDTO:
        logger.info(f"[CustomerService] Creating customer: {payload.model_dump()}")
        try:
            async with db.begin():
                c = await self.customer_repository.create_customer(payload, db)
            logger.info(f"[CustomerService] Customer created ID={c.id}")
            return CustomerDTO(
                id=c.id, 
                tax_id=c.tax_id, 
                name=c.name, 
                address=c.address,
                city=c.city, 
                phone=c.phone, 
                email=c.email,
                created_at=c.created_at,
                balance=c.balance,
            )
        except Exception as e:
            logger.error(f"[CustomerService] Create failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to create customer")

    async def get(self, customer_id: int, db: AsyncSession) -> CustomerDTO:
        logger.debug(f"[CustomerService] Get customer ID={customer_id}")
        try:
            async with db.begin():
                c = await self._require(customer_id, db)
            return CustomerDTO(
                id=c.id, 
                tax_id=c.tax_id, 
                name=c.name, 
                address=c.address,
                city=c.city, 
                phone=c.phone, 
                email=c.email,
                created_at=c.created_at, 
                balance=c.balance,
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"[CustomerService] Get failed ID={customer_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to fetch customer")

    async def list_all(self, db: AsyncSession) -> List[CustomerDTO]:
        logger.debug("[CustomerService] List all customers")
        try:
            async with db.begin():
                rows = await self.customer_repository.list_all(db)
            return [
                CustomerDTO(
                    id=c.id, 
                    tax_id=c.tax_id,
                    name=c.name,
                    address=c.address,
                    city=c.city,
                    phone=c.phone, 
                    email=c.email,
                    created_at=c.created_at, 
                    balance=c.balance,
                )
                for c in rows
            ]
        except Exception as e:
            logger.error(f"[CustomerService] List failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to list customers")

    async def list_paginated(self, page: int, db: AsyncSession) -> CustomerPageDTO:
        offset = max(page - 1, 0) * self.PAGE_SIZE
        async with db.begin():
            items, total = await self.customer_repository.list_paginated(
                offset=offset, limit=self.PAGE_SIZE, session=db
            )

        items_dto = [
            CustomerDTO(
                id=c.id, 
                tax_id=c.tax_id, 
                name=c.name, 
                address=c.address,
                city=c.city, 
                phone=c.phone, 
                email=c.email,
                created_at=c.created_at, 
                balance=c.balance,
            )
            for c in items
        ]
        total = int(total or 0)
        total_pages = max(1, ceil(total / self.PAGE_SIZE)) if total else 1
        return CustomerPageDTO(
            items=items_dto,
            page=page,
            page_size=self.PAGE_SIZE,
            total=total,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1,
        )

    async def update_partial(self, customer_id: int, payload: CustomerUpdate, db: AsyncSession) -> CustomerDTO:
        logger.info(f"[CustomerService] Update customer ID={customer_id} data={payload.model_dump(exclude_unset=True)}")
        try:
            async with db.begin():
                c = await self.customer_repository.update_customer(customer_id, payload, db)
            if not c:
                raise HTTPException(status_code=404, detail="Customer not found.")
            return CustomerDTO(
                id=c.id, 
                tax_id=c.tax_id, 
                name=c.name, 
                address=c.address,
                city=c.city, 
                phone=c.phone, 
                email=c.email,
                created_at=c.created_at, 
                balance=c.balance,
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"[CustomerService] Update failed ID={customer_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to update customer")

    async def update_balance(self, customer_id: int, new_balance: float, db: AsyncSession) -> CustomerDTO:
        logger.info(f"[CustomerService] Update balance ID={customer_id} -> {new_balance}")
        try:
            async with db.begin():
                c = await self.customer_repository.update_balance(customer_id, new_balance, db)
            if not c:
                raise HTTPException(status_code=404, detail="Customer not found.")
            return CustomerDTO(
                id=c.id, 
                tax_id=c.tax_id, 
                name=c.name, 
                address=c.address,
                city=c.city, 
                phone=c.phone, 
                email=c.email,
                created_at=c.created_at, 
                balance=c.balance,
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"[CustomerService] Update balance failed ID={customer_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to update balance")

    async def delete(self, customer_id: int, db: AsyncSession) -> bool:
        logger.warning(f"[CustomerService] Delete customer ID={customer_id}")
        try:
            async with db.begin():
                ok = await self.customer_repository.delete_customer(customer_id, db)
            if not ok:
                raise HTTPException(status_code=404, detail="Customer not found.")
            return True
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"[CustomerService] Delete failed ID={customer_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to delete customer")

    async def register_simple_balance_payment(
    self, *, customer_id: int, bank_id: int, amount: float,
    description: str | None, db: AsyncSession
    ) -> bool:
        if amount <= 0:
            raise HTTPException(status_code=400, detail="Amount must be > 0")

        customer = await self.customer_repository.get_by_id(customer_id, session=db)
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")

        bank = await self.bank_repository.get_by_id(bank_id, session=db)
        if not bank:
            raise HTTPException(status_code=404, detail="Bank not found")

        current_balance = float(customer.balance or 0.0)
        if amount > current_balance:
            raise HTTPException(status_code=422, detail=f"Exceeds balance ({current_balance:.2f})")

        try:
            # 1) Descuenta saldo del cliente
            await self.customer_repository.update_balance(customer_id, current_balance - amount, db)
            # 2) Aumenta saldo del banco  (usa el mismo parámetro `db`)
            await self.bank_repository.update_balance(bank_id, float(bank.balance or 0.0) + amount, session=db)
            # 3) Transacción bancaria
            await self.transaction_service.insert_transaction(
                TransactionCreate(
                    bank_id=bank_id,
                    amount=amount,
                    type_id=4,
                    description=description or f"Abono saldo {customer.name}",
                    is_auto=False,
                ),
                db=db,
            )
            await db.commit()
            return True
        except Exception:
            await db.rollback()
            raise