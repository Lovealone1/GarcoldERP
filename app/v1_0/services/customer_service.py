from typing import List, Optional
from math import ceil
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import logger
from app.core.realtime import publish_realtime_event
from app.v1_0.schemas import CustomerCreate, CustomerUpdate, TransactionCreate
from app.v1_0.repositories import CustomerRepository, BankRepository
from app.v1_0.entities import CustomerDTO, CustomerPageDTO
from .transaction_service import TransactionService

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
        """
        Ensure a customer exists or raise an HTTP 404 error.

        Args:
            customer_id: Identifier of the customer to fetch.
            db: Active async database session.

        Returns:
            ORM customer entity if found.

        Raises:
            HTTPException: If the customer does not exist.
        """
        c = await self.customer_repository.get_customer_by_id(customer_id, db)
        if not c:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")
        return c

    async def create(
        self,
        payload: CustomerCreate,
        db: AsyncSession,
        channel_id: Optional[str] = None,
    ) -> CustomerDTO:
        """
        Create a new customer.

        Operations:
        - Persist customer data.
        - Map to CustomerDTO.
        - Optionally emit a realtime "customer:created" event.

        Args:
            payload: CustomerCreate data with customer fields.
            db: Active async database session.
            channel_id: Optional realtime channel identifier for event publishing.

        Returns:
            CustomerDTO representing the created customer.

        Raises:
            HTTPException: 500 if creation fails.
        """
        logger.info("[CustomerService] Creating customer: %s", payload.model_dump())

        async def _run() -> CustomerDTO:
            c = await self.customer_repository.create_customer(payload, db)
            logger.info("[CustomerService] Customer created ID=%s", c.id)
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

        if not db.in_transaction():
            await db.begin()
        try:
            dto = await _run()
            await db.commit()
        except Exception as e:
            await db.rollback()
            logger.error("[CustomerService] Create failed: %s", e, exc_info=True)
            raise HTTPException(
                status_code=500,
                detail="Failed to create customer",
            )

        if channel_id:
            try:
                await publish_realtime_event(
                    channel_id=channel_id,
                    resource="customer",
                    action="created",
                    payload={"id": dto.id},
                )
                logger.info(
                    "[CustomerService] RT customer created published: id=%s",
                    dto.id,
                )
            except Exception as e:
                logger.error(
                    "[CustomerService] RT publish failed (create): %s",
                    e,
                    exc_info=True,
                )

        return dto

    async def get(self, customer_id: int, db: AsyncSession) -> CustomerDTO:
        """
        Retrieve a single customer by its identifier.

        Args:
            customer_id: Identifier of the customer.
            db: Active async database session.

        Returns:
            CustomerDTO with customer data.

        Raises:
            HTTPException:
                - 404 if not found.
                - 500 if an internal error occurs.
        """
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
        """
        List all customers without pagination.

        Args:
            db: Active async database session.

        Returns:
            List of CustomerDTO for all customers.

        Raises:
            HTTPException: 500 if the query fails.
        """
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
        """
        List customers in a paginated format.

        Uses PAGE_SIZE as the page size and returns pagination metadata.

        Args:
            page: Page number to retrieve (1-based).
            db: Active async database session.

        Returns:
            CustomerPageDTO containing:
                - items: List of CustomerDTO.
                - page: Current page.
                - page_size: Items per page.
                - total: Total number of customers.
                - total_pages: Total number of pages.
                - has_next: Whether a next page exists.
                - has_prev: Whether a previous page exists.
        """
        page_size = self.PAGE_SIZE
        offset = max(page - 1, 0) * page_size

        items, total, *_ = await self.customer_repository.list_paginated(
            offset=offset, limit=page_size, session=db
        )

        view_items = [
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
        total_pages = max(1, ceil(total / page_size)) if total else 1

        return CustomerPageDTO(
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
        customer_id: int,
        payload: CustomerUpdate,
        db: AsyncSession,
        channel_id: Optional[str] = None,
    ) -> CustomerDTO:
        """
        Partially update an existing customer (PATCH-style).

        Operations:
        - Apply only provided fields.
        - Map to CustomerDTO.
        - Optionally emit a realtime "customer:updated" event.

        Args:
            customer_id: Identifier of the customer to update.
            payload: CustomerUpdate data with optional fields to modify.
            db: Active async database session.
            channel_id: Optional realtime channel identifier for event publishing.

        Returns:
            CustomerDTO representing the updated customer.

        Raises:
            HTTPException:
                - 404 if customer not found.
                - 500 if update fails.
        """
        logger.info(
            "[CustomerService] Update customer ID=%s data=%s",
            customer_id,
            payload.model_dump(exclude_unset=True),
        )

        async def _run() -> CustomerDTO:
            c = await self.customer_repository.update_customer(
                customer_id,
                payload,
                db,
            )
            if not c:
                raise HTTPException(
                    status_code=404,
                    detail="Customer not found.",
                )
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
                "[CustomerService] Update failed ID=%s: %s",
                customer_id,
                e,
                exc_info=True,
            )
            raise HTTPException(
                status_code=500,
                detail="Failed to update customer",
            )

        if channel_id:
            try:
                await publish_realtime_event(
                    channel_id=channel_id,
                    resource="customer",
                    action="updated",
                    payload={"id": dto.id},
                )
                logger.info(
                    "[CustomerService] RT customer updated published: id=%s",
                    dto.id,
                )
            except Exception as e:
                logger.error(
                    "[CustomerService] RT publish failed (update_partial): %s",
                    e,
                    exc_info=True,
                )

        return dto

    async def update_balance(
        self,
        customer_id: int,
        new_balance: float,
        db: AsyncSession,
        channel_id: Optional[str] = None,
    ) -> CustomerDTO:
        """
        Update a customer's balance to an explicit value.

        Typically used by internal logic; prefer higher-level flows where possible.

        Args:
            customer_id: Identifier of the customer.
            new_balance: New balance value to set.
            db: Active async database session.
            channel_id: Optional realtime channel identifier for event publishing.

        Returns:
            CustomerDTO with the updated balance.

        Raises:
            HTTPException:
                - 404 if customer not found.
                - 500 if update fails.
        """
        logger.info(
            "[CustomerService] Update balance ID=%s -> %s",
            customer_id,
            new_balance,
        )

        async def _run() -> CustomerDTO:
            c = await self.customer_repository.update_balance(
                customer_id,
                new_balance,
                db,
            )
            if not c:
                raise HTTPException(
                    status_code=404,
                    detail="Customer not found.",
                )
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
                "[CustomerService] Update balance failed ID=%s: %s",
                customer_id,
                e,
                exc_info=True,
            )
            raise HTTPException(
                status_code=500,
                detail="Failed to update balance",
            )

        if channel_id:
            try:
                await publish_realtime_event(
                    channel_id=channel_id,
                    resource="customer",
                    action="updated",
                    payload={"id": dto.id},
                )
                logger.info(
                    "[CustomerService] RT customer balance update published: id=%s",
                    dto.id,
                )
            except Exception as e:
                logger.error(
                    "[CustomerService] RT publish failed (update_balance): %s",
                    e,
                    exc_info=True,
                )

        return dto

    async def delete(
        self,
        customer_id: int,
        db: AsyncSession,
        channel_id: Optional[str] = None,
    ) -> bool:
        """
        Delete a customer by its identifier.

        Operations:
        - Delete via repository.
        - Optionally emit a realtime "customer:deleted" event.

        Args:
            customer_id: Identifier of the customer to delete.
            db: Active async database session.
            channel_id: Optional realtime channel identifier for event publishing.

        Returns:
            True if the customer was deleted.

        Raises:
            HTTPException:
                - 404 if customer not found.
                - 500 if deletion fails.
        """
        logger.warning("[CustomerService] Delete customer ID=%s", customer_id)

        async def _run() -> bool:
            ok = await self.customer_repository.delete_customer(
                customer_id,
                db,
            )
            if not ok:
                raise HTTPException(
                    status_code=404,
                    detail="Customer not found.",
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
                "[CustomerService] Delete failed ID=%s: %s",
                customer_id,
                e,
                exc_info=True,
            )
            raise HTTPException(
                status_code=500,
                detail="Failed to delete customer",
            )

        if channel_id:
            try:
                await publish_realtime_event(
                    channel_id=channel_id,
                    resource="customer",
                    action="deleted",
                    payload={"id": customer_id},
                )
                logger.info(
                    "[CustomerService] RT customer deleted published: id=%s",
                    customer_id,
                )
            except Exception as e:
                logger.error(
                    "[CustomerService] RT publish failed (delete): %s",
                    e,
                    exc_info=True,
                )

        return True

    async def register_simple_balance_payment(
        self,
        *,
        customer_id: int,
        bank_id: int,
        amount: float,
        description: str | None,
        db: AsyncSession,
        channel_id: Optional[str] = None,
    ) -> bool:
        """
        Register a simple manual payment against a customer's outstanding balance.

        Operations:
        - Validate positive amount.
        - Validate customer and bank existence.
        - Validate that amount does not exceed customer's balance.
        - Decrease customer balance by amount.
        - Increase bank balance by amount.
        - Insert a corresponding transaction (manual payment).
        - Optionally emit realtime events:
          - customer_payment:created
          - customer:updated

        Args:
            customer_id: Identifier of the customer whose balance is being reduced.
            bank_id: Identifier of the bank receiving the payment.
            amount: Payment amount (must be > 0 and <= current balance).
            description: Optional payment description.
            db: Active async database session.
            channel_id: Optional realtime channel identifier for event publishing.

        Returns:
            True if the payment was registered successfully.

        Raises:
            HTTPException:
                - 400 if amount is not valid.
                - 404 if customer or bank not found.
                - 422 if amount exceeds current balance.
                - 500 if processing fails.
        """
        if amount <= 0:
            raise HTTPException(
                status_code=400,
                detail="Amount must be > 0",
            )

        customer = await self.customer_repository.get_by_id(
            customer_id,
            session=db,
        )
        if not customer:
            raise HTTPException(
                status_code=404,
                detail="Customer not found",
            )

        bank = await self.bank_repository.get_by_id(
            bank_id,
            session=db,
        )
        if not bank:
            raise HTTPException(
                status_code=404,
                detail="Bank not found",
            )

        current_balance = float(customer.balance or 0.0)
        if amount > current_balance:
            raise HTTPException(
                status_code=422,
                detail=f"Exceeds balance ({current_balance:.2f})",
            )

        async def _run() -> bool:
            await self.customer_repository.update_balance(
                customer_id,
                current_balance - amount,
                db,
            )
            await self.bank_repository.update_balance(
                bank_id,
                float(bank.balance or 0.0) + amount,
                session=db,
            )
            await self.transaction_service.insert_transaction(
                TransactionCreate(
                    bank_id=bank_id,
                    amount=amount,
                    type_id=2,
                    description=description or f"Abono saldo {customer.name}",
                    is_auto=False,
                ),
                db=db,
            )
            return True

        if not db.in_transaction():
            await db.begin()
        try:
            ok = await _run()
            await db.commit()
        except Exception as e:
            await db.rollback()
            logger.error(
                "[CustomerService] register_simple_balance_payment failed: %s",
                e,
                exc_info=True,
            )
            raise HTTPException(
                status_code=500,
                detail="Failed to register balance payment",
            )

        if not ok:
            return False

        if channel_id:
            try:
                # Evento específico opcional + actualización de cliente
                await publish_realtime_event(
                    channel_id=channel_id,
                    resource="customer_payment",
                    action="created",
                    payload={
                        "customer_id": customer_id,
                        "bank_id": bank_id,
                        "amount": amount,
                    },
                )
                await publish_realtime_event(
                    channel_id=channel_id,
                    resource="customer",
                    action="updated",
                    payload={"id": customer_id},
                )
                logger.info(
                    "[CustomerService] RT simple balance payment published: customer_id=%s",
                    customer_id,
                )
            except Exception as e:
                logger.error(
                    "[CustomerService] RT publish failed (simple_payment): %s",
                    e,
                    exc_info=True,
                )

        return True