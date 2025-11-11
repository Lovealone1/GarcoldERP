from typing import Optional, List, Dict, Any
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from math import ceil

from app.core.logger import logger 
from app.v1_0.repositories import (
    PurchaseRepository,
    PurchaseItemRepository,
    ProductRepository,
    SupplierRepository,
    StatusRepository,
    BankRepository,
    PurchasePaymentRepository,
)
from app.v1_0.services.transaction_service import TransactionService
from app.v1_0.entities import PurchaseItemDTO, PurchaseDTO, PurchasePageDTO, PurchaseItemViewDTO
from app.v1_0.schemas import PurchaseInsert, PurchaseItemCreate, TransactionCreate
from app.core.realtime import publish_realtime_event

class PurchaseService:
    def __init__(
        self,
        purchase_repository: PurchaseRepository,
        purchase_item_repository: PurchaseItemRepository,
        product_repository: ProductRepository,
        supplier_repository: SupplierRepository,
        status_repository: StatusRepository,
        bank_repository: BankRepository,
        purchase_payment_repository: PurchasePaymentRepository,
        transaction_service: TransactionService,
    ) -> None:
        self.purchase_repository = purchase_repository
        self.purchase_item_repository = purchase_item_repository    
        self.product_repository = product_repository
        self.supplier_repository = supplier_repository
        self.status_repository = status_repository
        self.bank_repository = bank_repository
        self.purchase_payment_repository = purchase_payment_repository
        self.transaction_service = transaction_service
        self.PAGE_SIZE = 8
        self._tx_type_pago_compra_id: Optional[int] = None
    
    async def finalize_purchase(
        self,
        supplier_id: int,
        bank_id: int,
        status_id: int,
        cart: list[dict],
        db: AsyncSession,
        purchase_date: Optional[datetime] = None,
        channel_id: Optional[str] = None,
    ) -> PurchaseDTO:
        """
        Create and finalize a purchase from a cart, updating inventory, balances, and transactions.

        Operations:
        - Resolve status to determine if purchase is credit or cash.
        - Create a purchase record with initial zero totals.
        - Normalize and validate cart items into PurchaseItemDTO list.
        - Validate referenced products and compute total amount.
        - Bulk insert purchase items.
        - Increase product stock according to purchased quantities.
        - For cash purchases:
            - Decrease bank balance.
            - Insert a "Pago compra" transaction record.
        - For credit purchases:
            - Set purchase balance equal to total.
        - Build and return a PurchaseDTO with resolved names.
        - Optionally publish a realtime "purchase created" event.

        Args:
            supplier_id: Identifier of the supplier for the purchase.
            bank_id: Identifier of the bank or payment account used.
            status_id: Identifier of the purchase status (e.g. cash or credit).
            cart: List of cart items with product_id, quantity, and unit_price.
            db: Active async database session.
            purchase_date: Optional explicit purchase datetime. Uses current time if not provided.
            channel_id: Optional realtime channel identifier to publish events.

        Returns:
            PurchaseDTO representing the created purchase.

        Raises:
            HTTPException: If any product is not found or cart is invalid.
            Exception: Propagated if database operations fail (after rollback).
        """
        async def _run() -> PurchaseDTO:
            status_row = await self.status_repository.get_by_id(
                status_id,
                session=db,
            )
            is_credit = bool(
                status_row and status_row.name.lower() == "compra credito"
            )

            purchase_stub = PurchaseInsert(
                supplier_id=supplier_id,
                bank_id=bank_id,
                status_id=status_id,
                total=0.0,
                balance=0.0,
                purchase_date=purchase_date or datetime.now(),
            )

            purchase = await self.purchase_repository.create_purchase(
                purchase_stub,
                session=db,
            )

            items: list[PurchaseItemDTO] = await self._build_items_from_cart(
                cart=cart,
                purchase_id=purchase.id,
            )

            total_amount = 0.0
            for it in items:
                product = await self.product_repository.get_by_id(
                    it.product_id,
                    session=db,
                )
                if not product:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Product {it.product_id} not found",
                    )
                total_amount += it.total

            rows = [
                PurchaseItemCreate(
                    purchase_id=purchase.id,
                    product_id=it.product_id,
                    quantity=it.quantity,
                    unit_price=it.unit_price,
                )
                for it in items
            ]
            await self.purchase_item_repository.bulk_insert_items(
                rows,
                session=db,
            )

            new_balance = total_amount if is_credit else 0.0
            purchase.total = total_amount
            purchase.balance = new_balance
            db.add(purchase)

            for it in items:
                await self.product_repository.increase_quantity(
                    it.product_id,
                    it.quantity,
                    session=db,
                )

            if not is_credit:
                bank = await self.bank_repository.get_by_id(
                    bank_id,
                    session=db,
                )
                if bank:
                    new_bank_balance = float(bank.balance or 0.0) - total_amount
                    await self.bank_repository.update_balance(
                        bank_id,
                        new_bank_balance,
                        session=db,
                    )

                    try:
                        tx_type_id = (
                            await self.transaction_service.type_repo.get_id_by_name(
                                "Pago compra",
                                session=db,
                            )
                        )
                    except Exception:
                        tx_type_id = None

                    await self.transaction_service.insert_transaction(
                        TransactionCreate(
                            bank_id=bank_id,
                            amount=total_amount,
                            type_id=tx_type_id,
                            description=f"Pago compra {purchase.id}",
                        ),
                        db=db,
                    )

            supplier = await self.supplier_repository.get_by_id(
                supplier_id,
                session=db,
            )
            bank = await self.bank_repository.get_by_id(
                bank_id,
                session=db,
            )

            status_name = status_row.name if status_row else "Desconocido"
            supplier_name = supplier.name if supplier else "Desconocido"
            bank_name = bank.name if bank else "Desconocido"

            return PurchaseDTO(
                id=purchase.id,
                supplier=supplier_name,
                bank=bank_name,
                status=status_name,
                total=total_amount,
                balance=new_balance,
                purchase_date=purchase.purchase_date,
            )

        if not db.in_transaction():
            await db.begin()

        try:
            dto = await _run()
            await db.commit()
        except Exception:
            await db.rollback()
            raise

        if channel_id:
            try:
                await publish_realtime_event(
                    channel_id=channel_id,
                    resource="purchase",
                    action="created",
                    payload={"id": dto.id},
                )
                logger.info(
                    "[PurchaseService] Realtime purchase created event published: purchase_id=%s",
                    dto.id,
                )
            except Exception as e:
                logger.error(
                    "[PurchaseService] realtime publish failed: %s",
                    e,
                    exc_info=True,
                )

        return dto
    
    async def _build_items_from_cart(
    self,
    cart: List[Dict[str, Any]],
    purchase_id: int,
    ) -> List[PurchaseItemDTO]:
        """
        Normalize and validate the purchase cart and build PurchaseItemDTOs.

        Ensures each item has valid types and positive quantity and unit_price.

        Args:
            cart: List of raw cart items with product_id, quantity, and unit_price.
            purchase_id: Identifier of the purchase to associate items with.

        Returns:
            List of PurchaseItemDTO with computed totals.

        Raises:
            HTTPException: If cart is empty or any item has invalid data.
        """
        if not cart:
            raise HTTPException(status_code=400, detail="Cart is empty")

        items: List[PurchaseItemDTO] = []
        for idx, raw in enumerate(cart, start=1):
            try:
                product_id = int(raw["product_id"])
                quantity = int(raw["quantity"])
                unit_price = float(raw["unit_price"])
            except Exception:
                raise HTTPException(
                    status_code=400,
                    detail=f"Item #{idx} has invalid types",
                )

            if quantity <= 0:
                raise HTTPException(
                    status_code=400,
                    detail=f"Item #{idx}: quantity must be > 0",
                )
            if unit_price <= 0:
                raise HTTPException(
                    status_code=400,
                    detail=f"Item #{idx}: unit_price must be > 0",
                )

            total = quantity * unit_price
            items.append(
                PurchaseItemDTO(
                    purchase_id=purchase_id,
                    product_id=product_id,
                    quantity=quantity,
                    unit_price=unit_price,
                    total=total,
                )
            )

        return items
    
    async def get_purchase(self, purchase_id: int, db: AsyncSession) -> PurchaseDTO:
        """
        Retrieve a single purchase with resolved supplier, bank, and status names.

        Args:
            purchase_id: Identifier of the purchase to retrieve.
            db: Active async database session.

        Returns:
            PurchaseDTO with purchase summary data.

        Raises:
            HTTPException: If the purchase does not exist.
        """
        p = await self.purchase_repository.get_by_id(purchase_id, session=db)
        if not p:
            raise HTTPException(status_code=404, detail="Purchase not found")

        supplier = await self.supplier_repository.get_by_id(p.supplier_id, session=db)
        bank = await self.bank_repository.get_by_id(p.bank_id, session=db)
        status_row = await self.status_repository.get_by_id(p.status_id, session=db)

        supplier_name = supplier.name if supplier else "Desconocido"
        bank_name = bank.name if bank else "Desconocido"
        status_name = status_row.name if status_row else "Desconocido"

        return PurchaseDTO(
            id=p.id,
            supplier=supplier_name,
            bank=bank_name,
            status=status_name,
            total=p.total,
            balance=p.balance,
            purchase_date=p.purchase_date,
        )
    
    async def delete_purchase(
        self,
        purchase_id: int,
        db: AsyncSession,
        channel_id: Optional[str] = None,
    ) -> None:
        """
        Delete a purchase and revert its inventory and financial effects.

        Operations:
        - Ensure the purchase exists.
        - Decrease product quantities to revert previously increased stock.
        - Inspect purchase status:
            - For credit-like statuses ("compra credito", "compra cancelada"):
                - For each payment, increase the related bank balance.
            - For cash ("compra contado"):
                - Increase the bank balance by the purchase total.
        - Delete related payments and purchase items.
        - Delete associated purchase transactions.
        - Delete the purchase record.
        - Optionally publish a realtime "purchase deleted" event.

        Args:
            purchase_id: Identifier of the purchase to delete.
            db: Active async database session.
            channel_id: Optional realtime channel identifier to publish events.

        Returns:
            None

        Raises:
            HTTPException: If the purchase does not exist.
            Exception: Propagated if database operations fail (after rollback).
        """
        async def _run() -> int:
            p = await self.purchase_repository.get_by_id(
                purchase_id,
                session=db,
            )
            if not p:
                raise HTTPException(
                    status_code=404,
                    detail="Purchase not found",
                )

            items = await self.purchase_item_repository.get_by_purchase_id(
                purchase_id,
                session=db,
            )
            for it in items:
                await self.product_repository.decrease_quantity(
                    it.product_id,
                    it.quantity,
                    session=db,
                )

            status_row = await self.status_repository.get_by_id(
                p.status_id,
                session=db,
            )
            status_name = (status_row.name or "").lower() if status_row else ""
            is_credit_like = status_name in (
                "compra credito",
                "compra cancelada",
            )
            is_cash = status_name == "compra contado"

            payments = await self.purchase_payment_repository.list_by_purchase(
                purchase_id,
                session=db,
            )

            if is_credit_like:
                for pay in payments:
                    await self.bank_repository.increase_balance(
                        pay.bank_id,
                        float(pay.amount or 0),
                        session=db,
                    )
            elif is_cash:
                await self.bank_repository.increase_balance(
                    p.bank_id,
                    float(p.total or 0),
                    session=db,
                )

            await self.purchase_payment_repository.delete_by_purchase(
                purchase_id,
                session=db,
            )
            await self.purchase_item_repository.delete_by_purchase(
                purchase_id,
                session=db,
            )
            await self.transaction_service.delete_purchase_transactions(
                purchase_id,
                db=db,
            )
            await self.purchase_repository.delete_purchase(
                purchase_id,
                session=db,
            )

            return p.id

        if not db.in_transaction():
            await db.begin()

        try:
            pid = await _run()
            await db.commit()
        except Exception:
            await db.rollback()
            raise

        if channel_id:
            try:
                await publish_realtime_event(
                    channel_id=channel_id,
                    resource="purchase",
                    action="deleted",
                    payload={"id": pid},
                )
                logger.info(
                    "[PurchaseService] Realtime purchase deleted event published: purchase_id=%s",
                    pid,
                )
            except Exception as e:
                logger.error(
                    "[PurchaseService] realtime publish failed: %s",
                    e,
                    exc_info=True,
                )

    async def list_purchases(self, page: int, db: AsyncSession) -> PurchasePageDTO:
        """
        List paginated purchases with resolved relation names.

        Uses PAGE_SIZE for page size and returns pagination metadata.

        Args:
            page: Page number to retrieve (1-based).
            db: Active async database session.

        Returns:
            PurchasePageDTO containing:
                - items: List of PurchaseDTO.
                - page: Current page.
                - page_size: Items per page.
                - total: Total number of purchases.
                - total_pages: Total number of pages.
                - has_next: True if there is a next page.
                - has_prev: True if there is a previous page.
        """
        page_size = self.PAGE_SIZE
        offset = max(page - 1, 0) * page_size

        items_raw, total, *_ = await self.purchase_repository.list_paginated(
            offset=offset, limit=page_size, session=db
        )

        view_items: List[PurchaseDTO] = [
            PurchaseDTO(
                id=p.id,
                supplier=(p.supplier.name if getattr(p, "supplier", None) else f"Supplier {p.supplier_id}"),
                bank=(p.bank.name if getattr(p, "bank", None) else f"Bank {p.bank_id}"),
                status=(p.status.name if getattr(p, "status", None) else "Desconocido"),
                total=float(p.total) if p.total is not None else 0.0,
                balance=float(p.balance) if p.balance is not None else 0.0,
                purchase_date=p.purchase_date,
            )
            for p in items_raw
        ]

        total = int(total or 0)
        total_pages = max(1, ceil(total / page_size)) if total else 1

        return PurchasePageDTO(
            items=view_items,
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1,
        )

    async def list_items(self, purchase_id: int, db: AsyncSession) -> List[PurchaseItemViewDTO]:
        """
        List items of a given purchase for visualization.

        Ensures the purchase exists, then returns items including:
        - Product reference.
        - Quantity.
        - Unit price.
        - Total.
        - Purchase identifier.

        Args:
            purchase_id: Identifier of the purchase whose items will be listed.
            db: Active async database session.

        Returns:
            List of PurchaseItemViewDTO representing the purchase items.

        Raises:
            HTTPException: If the purchase does not exist.
        """
        async with db.begin():
            p = await self.purchase_repository.get_by_id(purchase_id, session=db)
            if not p:
                raise HTTPException(status_code=404, detail="Purchase not found")

            details = await self.purchase_item_repository.get_by_purchase_id(purchase_id, session=db)

            out: List[PurchaseItemViewDTO] = []
            for d in details:
                prod = await self.product_repository.get_by_id(d.product_id, session=db)
                reference = getattr(prod, "reference", "Desconocido") if prod else "Desconocido"
                out.append(
                    PurchaseItemViewDTO(
                        purchase_id=purchase_id,
                        product_reference=reference,
                        quantity=d.quantity,
                        unit_price=d.unit_price,
                        total=d.total,
                    )
                )

        return out