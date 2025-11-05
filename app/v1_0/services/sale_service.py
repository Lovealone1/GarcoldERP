from datetime import datetime, timezone
from typing import List, Dict, Any, Sequence, Optional
from math import ceil
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import logger
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
from app.v1_0.services.transaction_service import TransactionService
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
        self.PAGE_SIZE = 8
        self._tx_type_pago_venta_id: Optional[int] = None

    async def _get_pago_venta_type_id(self, db: AsyncSession) -> Optional[int]:
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
        status_row = await self.status_repository.get_by_id(status_id, session=db)
        return bool(status_row and status_row.name.lower() == "venta credito")

    async def _build_items_from_cart(
        self,
        cart: List[Dict[str, Any]],
        sale_id: int,
    ) -> List[SaleItemDTO]:
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
        for it in items:
            await self.product_repository.decrease_quantity(it.product_id, it.quantity, session=db)

    async def _adjust_balances_and_transaction(
        self, *, is_credit: bool, customer_id: int, bank_id: int, amount: float, sale_id: int, db: AsyncSession
    ) -> None:
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
    ) -> SaleDTO:
        async with db.begin():
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

            profit_items = await self._compute_profit_items(sale_id=sale.id, items=items, session=db)
            await self.profit_item_repository.bulk_insert_details(profit_items, session=db)
            total_profit = sum(pi.total_profit for pi in profit_items)
            await self.profit_repository.create_profit(
                ProfitCreate(sale_id=sale.id, profit=total_profit), session=db
            )

            customer = await self.customer_repository.get_by_id(customer_id, session=db)
            bank = await self.bank_repository.get_by_id(bank_id, session=db)
            status_row = await self.status_repository.get_by_id(status_id, session=db)
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

    async def get_sale(self, sale_id: int, db: AsyncSession) -> SaleDTO:
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

    async def delete_sale(self, sale_id: int, db: AsyncSession) -> None:
        async with db.begin():
            sale = await self.sale_repository.get_by_id(sale_id, session=db)
            if not sale:
                raise HTTPException(status_code=404, detail="Sale not found")

            items = await self.sale_item_repository.get_by_sale_id(sale_id, session=db)
            for it in items:
                await self.product_repository.increase_quantity(it.product_id, it.quantity, session=db)

            status_row = await self.status_repository.get_by_id(sale.status_id, session=db)
            status_name = (status_row.name or "").lower() if status_row else ""
            is_credit_like = status_name in ("venta credito", "venta cancelada")
            is_cash = status_name == "venta contado"

            payments = await self.sale_payment_repository.list_by_sale(sale_id, session=db)

            if is_credit_like:
                for p in payments:
                    await self.bank_repository.decrease_balance(p.bank_id, float(p.amount or 0), session=db)
                customer = await self.customer_repository.get_by_id(sale.customer_id, session=db)
                if customer:
                    new_balance = max(float(customer.balance or 0) - float(sale.total or 0), 0.0)
                    await self.customer_repository.update_balance(customer.id, new_balance, session=db)
            elif is_cash:
                await self.bank_repository.decrease_balance(sale.bank_id, float(sale.total or 0), session=db)

            await self.sale_payment_repository.delete_by_sale(sale_id, session=db)
            await self.profit_item_repository.delete_by_sale(sale_id, session=db)
            await self.profit_repository.delete_by_sale(sale_id, session=db)
            await self.sale_item_repository.delete_by_sale(sale_id, session=db)
            await self.transaction_service.delete_sale_transactions(sale_id, db=db)
            await self.sale_repository.delete_sale(sale_id, session=db)

    async def list_sales(self, page: int, db: AsyncSession) -> SalePageDTO:
        offset = max(page - 1, 0) * self.PAGE_SIZE
        async with db.begin():
            rows, total = await self.sale_repository.list_paginated(
                offset=offset, limit=self.PAGE_SIZE, session=db
            )

            items: List[SaleDTO] = []
            for s in rows:
                customer = await self.customer_repository.get_by_id(s.customer_id, session=db)
                bank = await self.bank_repository.get_by_id(s.bank_id, session=db)
                status_row = await self.status_repository.get_by_id(s.status_id, session=db)

                customer_name = customer.name if customer else "Desconocido"
                bank_name = bank.name if bank else "Desconocido"
                status_name = status_row.name if status_row else "Desconocido"

                items.append(
                    SaleDTO(
                        id=s.id,
                        customer=customer_name,
                        bank=bank_name,
                        status=status_name,
                        total=s.total,
                        remaining_balance=s.remaining_balance,
                        created_at=s.created_at,
                    )
                )

        total = int(total or 0)
        total_pages = max(1, ceil(total / self.PAGE_SIZE)) if total else 1
        return SalePageDTO(
            items=items,
            page=page,
            page_size=self.PAGE_SIZE,
            total=total,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1,
        )

    async def list_items(self, sale_id: int, db: AsyncSession) -> List[SaleItemViewDTO]:
        """
        Return sale items for visualization: product_reference, quantity, price, total, and sale id.
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