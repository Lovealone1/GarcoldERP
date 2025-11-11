from datetime import datetime
from typing import List, Dict, Any, Sequence, Optional
from math import ceil
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import logger
from app.core.realtime import ConnectionManager
from app.v1_0.entities import (
    SaleDTO,
    SaleItemDTO,
    SalePageDTO, 
    SaleItemViewDTO
)
from app.v1_0.repositories import (
    SaleRepository,
    SaleItemRepository,
    ProductRepository,
    CustomerRepository,
    StatusRepository,
    ProfitItemRepository,
    ProfitRepository,
    BankRepository,
    SalePaymentRepository,
)
from app.v1_0.services import TransactionService
from app.core.realtime import publish_realtime_event
from app.v1_0.schemas import (
    SaleInsert,
    SaleItemCreate,
    TransactionCreate,
    ProfitCreate,
    SaleProfitDetailCreate,
)

class SaleService:
    def __init__(
        self,
        sale_repository: SaleRepository,
        sale_item_repository: SaleItemRepository,
        product_repository: ProductRepository,
        customer_repository: CustomerRepository,
        status_repository: StatusRepository,
        profit_item_repository: ProfitItemRepository,
        profit_repository: ProfitRepository,
        bank_repository: BankRepository,
        sale_payment_repository: SalePaymentRepository,
        transaction_service: TransactionService,
        realtime_manager: ConnectionManager,
    ) -> None:
        self.sale_repository = sale_repository
        self.sale_item_repository = sale_item_repository
        self.product_repository = product_repository
        self.customer_repository = customer_repository
        self.status_repository = status_repository
        self.profit_item_repository = profit_item_repository
        self.profit_repository = profit_repository
        self.bank_repository = bank_repository
        self.sale_payment_repository = sale_payment_repository
        self.transaction_service = transaction_service
        self._realtime_manager = realtime_manager
        self.PAGE_SIZE = 8
        self._tx_type_pago_venta_id: Optional[int] = None

    async def _get_pago_venta_type_id(self, db: AsyncSession) -> Optional[int]:
        """
        Resolve and cache the transaction type ID for "Pago venta".

        Args:
            db: Active async database session.

        Returns:
            The transaction type ID for "Pago venta" if found, otherwise None.
        """
        if self._tx_type_pago_venta_id is None:
            try:
                self._tx_type_pago_venta_id = await self.transaction_service.type_repo.get_id_by_name(
                    "Pago venta", session=db
                )
            except Exception as e:
                logger.warning("Lookup 'Pago venta' failed: %s", e, exc_info=True)
                self._tx_type_pago_venta_id = None
        return self._tx_type_pago_venta_id

    async def _is_credit_status(self, status_id: int, db: AsyncSession) -> bool:
        """
        Check if the given status corresponds to a credit sale.

        Args:
            status_id: Status identifier to evaluate.
            db: Active async database session.

        Returns:
            True if the status is "venta credito", otherwise False.
        """
        status_row = await self.status_repository.get_by_id(status_id, session=db)
        return bool(status_row and status_row.name.lower() == "venta credito")

    async def _build_items_from_cart(
        self,
        cart: List[Dict[str, Any]],
        sale_id: int,
    ) -> List[SaleItemDTO]:
        """
        Build a list of SaleItemDTO from the raw cart payload.

        Validates types and basic constraints for quantity and unit_price.

        Args:
            cart: List of cart item dictionaries with product_id, quantity, and unit_price.
            sale_id: Identifier of the sale to associate items with.

        Returns:
            List of SaleItemDTO representing the cart items.

        Raises:
            HTTPException: If the cart is empty or any item has invalid data.
        """
        if not cart:
            raise HTTPException(status_code=400, detail="Cart is empty")

        items: List[SaleItemDTO] = []
        for idx, raw in enumerate(cart, start=1):
            try:
                product_id = int(raw["product_id"])
                quantity = int(raw["quantity"])
                unit_price = float(raw["unit_price"])
            except Exception:
                raise HTTPException(status_code=400, detail=f"Item #{idx} has invalid types")

            if quantity <= 0:
                raise HTTPException(status_code=400, detail=f"Item #{idx}: quantity must be > 0")
            if unit_price <= 0:
                raise HTTPException(status_code=400, detail=f"Item #{idx}: unit_price must be > 0")

            total = quantity * unit_price
            items.append(
                SaleItemDTO(
                    sale_id=sale_id,
                    product_id=product_id,
                    quantity=quantity,
                    unit_price=unit_price,
                    total=total,
                )
            )
        return items

    async def _validate_stock_and_total(
        self, items: Sequence[SaleItemDTO], db: AsyncSession
    ) -> float:
        """
        Validate product stock for all items and compute the sale total.

        For each item, ensures the product exists and available quantity is sufficient.

        Args:
            items: Sequence of sale item DTOs to validate.
            db: Active async database session.

        Returns:
            Total sale amount as a float.

        Raises:
            HTTPException: If a product does not exist or stock is insufficient.
        """
        total = 0.0
        for it in items:
            product = await self.product_repository.get_by_id(it.product_id, session=db)
            if not product:
                raise HTTPException(status_code=404, detail=f"Product {it.product_id} not found")
            if (product.quantity or 0) < it.quantity:
                ref = getattr(product, "reference", it.product_id)
                raise HTTPException(status_code=400, detail=f"Insufficient stock for product {ref}")
            total += it.total
        return total

    async def _insert_items(self, sale_id: int, items: Sequence[SaleItemDTO], db: AsyncSession) -> None:
        """
        Persist sale items for a given sale.

        Args:
            sale_id: Identifier of the sale associated with the items.
            items: Sequence of SaleItemDTO to be inserted.
            db: Active async database session.

        Returns:
            None
        """
        rows = [
            SaleItemCreate(
                sale_id=sale_id,
                product_id=it.product_id,
                quantity=it.quantity,
                unit_price=it.unit_price,
            )
            for it in items
        ]
        await self.sale_item_repository.bulk_insert_items(rows, session=db)

    async def _decrease_inventory(self, items: Sequence[SaleItemDTO], db: AsyncSession) -> None:
        """
        Decrease product inventory based on sale items.

        Args:
            items: Sequence of SaleItemDTO representing sold items.
            db: Active async database session.

        Returns:
            None
        """
        for it in items:
            await self.product_repository.decrease_quantity(it.product_id, it.quantity, session=db)

    async def _adjust_balances_and_transaction(
        self, *, is_credit: bool, customer_id: int, bank_id: int, amount: float, sale_id: int, db: AsyncSession
    ) -> None:
        """
        Adjust customer or bank balances and create a transaction when applicable.

        For credit sales, increases the customer's outstanding balance.
        For cash sales, increases the bank balance and records a payment transaction.

        Args:
            is_credit: True if sale is credit-based, False if cash/paid.
            customer_id: Customer identifier associated with the sale.
            bank_id: Bank identifier used for the sale.
            amount: Total sale amount.
            sale_id: Identifier of the sale.
            db: Active async database session.

        Returns:
            None
        """
        if is_credit:
            customer = await self.customer_repository.get_by_id(customer_id, session=db)
            if customer:
                new_balance = float(customer.balance or 0.0) + amount
                await self.customer_repository.update_balance(customer_id, new_balance, session=db)
            return

        bank = await self.bank_repository.get_by_id(bank_id, session=db)
        if bank:
            new_bank_balance = float(bank.balance or 0.0) + amount
            await self.bank_repository.update_balance(bank_id, new_bank_balance, session=db)

            tx_type_id = await self._get_pago_venta_type_id(db)
            await self.transaction_service.insert_transaction(
                TransactionCreate(
                    bank_id=bank_id,
                    amount=amount,
                    type_id=tx_type_id,
                    description=f"Pago venta {sale_id}",
                ),
                db=db,
            )

    async def _compute_profit_items(
        self,
        sale_id: int,
        items: List[SaleItemDTO],
        session: AsyncSession,
    ) -> List[SaleProfitDetailCreate]:
        """
        Compute per-item profit details for a sale.

        Uses each product's purchase price and the sale item unit price
        to determine unit and total profit.

        Args:
            sale_id: Identifier of the sale.
            items: List of SaleItemDTO representing sale items.
            session: Active async database session.

        Returns:
            List of SaleProfitDetailCreate containing profit breakdown per item.

        Raises:
            HTTPException: If a referenced product does not exist.
        """
        profit_items: List[SaleProfitDetailCreate] = []
        for it in items:
            product = await self.product_repository.get_by_id(it.product_id, session=session)
            if not product:
                raise HTTPException(status_code=404, detail=f"Product {it.product_id} not found")

            unit_profit = it.unit_price - float(product.purchase_price or 0.0)
            total_profit = unit_profit * it.quantity

            profit_items.append(
                SaleProfitDetailCreate(
                    sale_id=sale_id,
                    product_id=it.product_id,
                    reference=getattr(product, "reference", None),
                    description=getattr(product, "description", None),
                    quantity=it.quantity,
                    purchase_price=float(product.purchase_price or 0.0),
                    sale_price=float(it.unit_price),
                    total_profit=float(total_profit),
                )
            )
        return profit_items

    async def finalize_sale(
        self,
        customer_id: int,
        bank_id: int,
        status_id: int,
        cart: List[Dict[str, Any]],
        db: AsyncSession,
        sale_date: Optional[datetime] = None,
        channel_id: Optional[str] = None,
    ) -> SaleDTO:
        """
        Create and finalize a sale from a cart, adjusting stock, balances, profits, and transactions.

        Executes all operations in a database transaction:
        - Creates the sale record.
        - Builds and validates sale items.
        - Validates stock and computes total.
        - Persists items.
        - Updates remaining balance for credit sales.
        - Updates bank or customer balances and creates a transaction when needed.
        - Computes and persists profit details and aggregated profit.
        - Optionally publishes a realtime "sale created" event.

        Args:
            customer_id: Identifier of the customer making the purchase.
            bank_id: Identifier of the bank or payment account used.
            status_id: Identifier of the sale status (e.g. cash or credit).
            cart: List of cart items with product_id, quantity, and unit_price.
            db: Active async database session.
            sale_date: Optional explicit sale datetime. Uses current time if not provided.
            channel_id: Optional realtime channel identifier to publish events.

        Returns:
            SaleDTO with summary information for the created sale.

        Raises:
            HTTPException: On validation errors or inconsistent state.
            Exception: Propagated if database operations fail (after rollback).
        """
        async def _run() -> SaleDTO:
            is_credit = await self._is_credit_status(status_id, db)

            sale = await self.sale_repository.create_sale(
                SaleInsert(
                    customer_id=customer_id,
                    bank_id=bank_id,
                    total=0.0,
                    status_id=status_id,
                    remaining_balance=0.0,
                    created_at=sale_date or datetime.now(),
                ),
                session=db,
            )

            items = await self._build_items_from_cart(cart=cart, sale_id=sale.id)
            total_amount = await self._validate_stock_and_total(items, db)

            await self._insert_items(sale.id, items, db)

            new_remaining = total_amount if is_credit else 0.0
            sale.total = total_amount
            sale.remaining_balance = new_remaining
            db.add(sale)

            await self._decrease_inventory(items, db)

            await self._adjust_balances_and_transaction(
                is_credit=is_credit,
                customer_id=customer_id,
                bank_id=bank_id,
                amount=total_amount,
                sale_id=sale.id,
                db=db,
            )

            profit_items = await self._compute_profit_items(
                sale_id=sale.id,
                items=items,
                session=db,
            )
            await self.profit_item_repository.bulk_insert_details(
                profit_items,
                session=db,
            )

            total_profit = sum(pi.total_profit for pi in profit_items)
            await self.profit_repository.create_profit(
                ProfitCreate(sale_id=sale.id, profit=total_profit),
                session=db,
            )

            customer = await self.customer_repository.get_by_id(
                customer_id,
                session=db,
            )
            bank = await self.bank_repository.get_by_id(
                bank_id,
                session=db,
            )
            status_row = await self.status_repository.get_by_id(
                status_id,
                session=db,
            )
            status_name = status_row.name if status_row else "Desconocido"

            return SaleDTO(
                id=sale.id,
                customer=customer.name if customer else "Desconocido",
                bank=bank.name if bank else "Desconocido",
                status=status_name,
                total=total_amount,
                remaining_balance=new_remaining,
                created_at=sale.created_at,
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
                    resource="sale",
                    action="created",
                    payload={"id": dto.id},
                )
                logger.info("[SaleService] Realtime sale created event published: sale_id=%s", dto.id)
            except Exception as e:
                logger.error(
                    "[SaleService] realtime publish failed: %s",
                    e,
                    exc_info=True,
                )

        return dto

    async def get_sale(self, sale_id: int, db: AsyncSession) -> SaleDTO:
        """
        Retrieve a single sale with resolved customer, bank, and status names.

        Args:
            sale_id: Identifier of the sale to retrieve.
            db: Active async database session.

        Returns:
            SaleDTO with sale summary data.

        Raises:
            HTTPException: If the sale does not exist.
        """
        sale = await self.sale_repository.get_by_id(sale_id, session=db)
        if not sale:
            raise HTTPException(status_code=404, detail="Sale not found")

        customer = await self.customer_repository.get_by_id(sale.customer_id, session=db)
        bank = await self.bank_repository.get_by_id(sale.bank_id, session=db)
        status_row = await self.status_repository.get_by_id(sale.status_id, session=db)

        customer_name = customer.name if customer else "Desconocido"
        bank_name = bank.name if bank else "Desconocido"
        status_name = status_row.name if status_row else "Desconocido"

        return SaleDTO(
            id=sale.id,
            customer=customer_name,
            bank=bank_name,
            status=status_name,
            total=sale.total,
            remaining_balance=sale.remaining_balance,
            created_at=sale.created_at,
        )

    async def delete_sale(
        self,
        sale_id: int,
        db: AsyncSession,
        channel_id: Optional[str] = None,
    ) -> None:
        """
        Delete a sale and fully revert its financial and inventory impact.

        Steps:
        - Restore product stock from sale items.
        - Adjust bank and customer balances depending on sale status and payments.
        - Delete related payments, profit details, profit records, sale items, and transactions.
        - Delete the sale record itself.
        - Optionally publish a realtime "sale deleted" event.

        Args:
            sale_id: Identifier of the sale to delete.
            db: Active async database session.
            channel_id: Optional realtime channel identifier to publish events.

        Returns:
            None

        Raises:
            HTTPException: If the sale does not exist.
            Exception: Propagated if database operations fail (after rollback).
        """
        async def _run() -> None:
            sale = await self.sale_repository.get_by_id(sale_id, session=db)
            if not sale:
                raise HTTPException(status_code=404, detail="Sale not found")

            items = await self.sale_item_repository.get_by_sale_id(
                sale_id,
                session=db,
            )
            for it in items:
                await self.product_repository.increase_quantity(
                    it.product_id,
                    it.quantity,
                    session=db,
                )

            status_row = await self.status_repository.get_by_id(
                sale.status_id,
                session=db,
            )
            status_name = (status_row.name or "").lower() if status_row else ""
            is_credit_like = status_name in ("venta credito", "venta cancelada")
            is_cash = status_name == "venta contado"

            payments = await self.sale_payment_repository.list_by_sale(
                sale_id,
                session=db,
            )

            if is_credit_like:
                for p in payments:
                    await self.bank_repository.decrease_balance(
                        p.bank_id,
                        float(p.amount or 0),
                        session=db,
                    )

                customer = await self.customer_repository.get_by_id(
                    sale.customer_id,
                    session=db,
                )
                if customer:
                    new_balance = max(
                        float(customer.balance or 0)
                        - float(sale.total or 0),
                        0.0,
                    )
                    await self.customer_repository.update_balance(
                        customer.id,
                        new_balance,
                        session=db,
                    )

            elif is_cash:
                await self.bank_repository.decrease_balance(
                    sale.bank_id,
                    float(sale.total or 0),
                    session=db,
                )

            await self.sale_payment_repository.delete_by_sale(
                sale_id,
                session=db,
            )
            await self.profit_item_repository.delete_by_sale(
                sale_id,
                session=db,
            )
            await self.profit_repository.delete_by_sale(
                sale_id,
                session=db,
            )
            await self.sale_item_repository.delete_by_sale(
                sale_id,
                session=db,
            )
            await self.transaction_service.delete_sale_transactions(
                sale_id,
                db=db,
            )
            await self.sale_repository.delete_sale(
                sale_id,
                session=db,
            )

        if not db.in_transaction():
            await db.begin()

        try:
            await _run()
            await db.commit()
        except Exception:
            await db.rollback()
            raise

        if channel_id:
            try:
                await publish_realtime_event(
                    channel_id=channel_id,
                    resource="sale",
                    action="deleted",
                    payload={"id": sale_id},
                )
                logger.info(
                    "[SaleService] Realtime sale deleted event published: sale_id=%s",
                    sale_id,
                )
            except Exception as e:
                logger.error(
                    "[SaleService] realtime publish failed: %s",
                    e,
                    exc_info=True,
                )

    async def list_sales(self, page: int, db: AsyncSession) -> SalePageDTO:
        """
        List paginated sales with resolved relation names.

        Uses PAGE_SIZE as page size and computes basic pagination metadata.

        Args:
            page: Page number to retrieve (1-based).
            db: Active async database session.

        Returns:
            SalePageDTO containing the list of SaleDTO items and pagination info.
        """
        page_size = self.PAGE_SIZE
        offset = max(page - 1, 0) * page_size

        items, total, *rest = await self.sale_repository.list_paginated(
            offset=offset, limit=page_size, session=db
        )

        view_items: List[SaleDTO] = [
            SaleDTO(
                id=s.id,
                customer=(s.customer.name if getattr(s, "customer", None) else f"Customer {s.customer_id}"),
                bank=(s.bank.name if getattr(s, "bank", None) else f"Bank {s.bank_id}"),
                status=(s.status.name if getattr(s, "status", None) else "Desconocido"),
                total=float(s.total) if s.total is not None else 0.0,
                remaining_balance=float(s.remaining_balance) if s.remaining_balance is not None else 0.0,
                created_at=s.created_at,
            )
            for s in items
        ]

        total = int(total or 0)
        total_pages = max(1, ceil(total / page_size)) if total else 1

        return SalePageDTO(
            items=view_items,
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1,
        )

    async def list_items(self, sale_id: int, db: AsyncSession) -> List[SaleItemViewDTO]:
        """
        List visualizable items of a given sale with product data.

        Ensures the sale exists, then returns items including product reference,
        description, quantity, unit price, and total.

        Args:
            sale_id: Identifier of the sale whose items will be listed.
            db: Active async database session.

        Returns:
            List of SaleItemViewDTO representing the sale items.

        Raises:
            HTTPException: If the sale does not exist.
        """
        async with db.begin():
            sale = await self.sale_repository.get_by_id(sale_id, session=db)
            if not sale:
                raise HTTPException(status_code=404, detail="Sale not found")

            details = await self.sale_item_repository.get_by_sale_id(sale_id, session=db)

            out: List[SaleItemViewDTO] = []
            for d in details:
                prod = await self.product_repository.get_by_id(d.product_id, session=db)
                reference = getattr(prod, "reference", "Desconocido") if prod else "Desconocido"
                description = getattr(prod, "description", "Desconocido") if prod else "Desconocido"
                out.append(
                    SaleItemViewDTO(
                        sale_id=sale_id,
                        product_reference=reference,
                        product_description=description,
                        quantity=d.quantity,
                        unit_price=d.unit_price,
                        total=d.total,
                    )
                )

        return out