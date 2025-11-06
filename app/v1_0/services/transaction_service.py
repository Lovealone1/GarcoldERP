from math import ceil
from decimal import Decimal
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import re

from app.core.logger import logger
from app.v1_0.schemas import TransactionCreate
from app.v1_0.entities import TransactionDTO, TransactionPageDTO, TransactionViewDTO
from app.v1_0.models import Transaction
from app.v1_0.repositories import (
    TransactionRepository,
    TransactionTypeRepository,
    BankRepository,
    CustomerRepository
)

class TransactionService:
    def __init__(
        self,
        transaction_repository: TransactionRepository,
        transaction_type_repository: TransactionTypeRepository,
        bank_repository: BankRepository,
        customer_repository: CustomerRepository
    ) -> None:
        self.tx_repo = transaction_repository
        self.type_repo = transaction_type_repository
        self.bank_repo = bank_repository
        self.customer_repository = customer_repository
        self.PAGE_SIZE = 8

    async def insert_transaction(
        self,
        payload: TransactionCreate,
        db: AsyncSession,
    ) -> Transaction:
        """
        Helper: thin passthrough to repository. No validation, no transaction block.
        Used by other services that already manage their own logic/transactions.
        """
        try:
            return await self.tx_repo.create_transaction(payload, session=db)
        except Exception as e:
            logger.error(f"[TransactionService] insert_transaction failed: {e}", exc_info=True)
            raise

    async def create(self, payload: TransactionCreate, db: AsyncSession) -> TransactionDTO:
        if payload.type_id is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="type_id is required.")

        amount = Decimal(str(payload.amount))

        async with db.begin():
            bank = await self.bank_repo.get_by_id(payload.bank_id, session=db)
            if not bank:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bank not found.")

            tx_type = await self.type_repo.get_by_id(payload.type_id, session=db)
            if not tx_type:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction type not found.")

            kind = (tx_type.name or "").strip().lower()
            current_balance = Decimal(str(bank.balance or 0))

            if kind == "ingreso":
                new_balance = current_balance + amount
            elif kind == "retiro":
                if amount > current_balance:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Insufficient funds.")
                new_balance = current_balance - amount
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Unsupported transaction type. Use 'Ingreso' or 'Retiro'."
                )

            bank.balance = float(new_balance)  
            tx = await self.tx_repo.create_transaction(payload, session=db)

        return TransactionDTO(
            id=tx.id,
            bank_id=tx.bank_id,
            amount=tx.amount,
            type_id=tx.type_id,
            description=tx.description,
            is_auto=tx.is_auto,
            created_at=tx.created_at,
        )
        
    async def delete_purchase_payment_transaction(
        self,
        payment_id: int,
        purchase_id: int,
        db: AsyncSession,
    ) -> int:
        """
        Helper: find and delete the transaction linked to a purchase payment.
        No transaction block here (caller manages it). Returns deleted tx ID, or 0 if none.
        """
        try:
            tx_id = await self.tx_repo.get_transaction_id_for_purchase_payment(
                payment_id=payment_id,
                purchase_id=purchase_id,
                session=db,
            )
            if not tx_id:
                return 0

            await self.tx_repo.delete_transaction(tx_id, session=db)
            return tx_id
        except Exception as e:
            logger.error(
                f"[TransactionService] delete_purchase_payment_transaction "
                f"failed (payment_id={payment_id}, purchase_id={purchase_id}): {e}",
                exc_info=True,
            )
            return 0
        
    async def delete_sale_payment_transaction(
        self,
        payment_id: int,
        sale_id: int,
        db: AsyncSession,
    ) -> int:
        """
        Helper: find and delete the transaction linked to a sale payment.
        Caller manages the surrounding transaction. Returns deleted tx ID, or 0.
        """
        try:
            tx_id = await self.tx_repo.get_transaction_id_for_sale_payment(
                payment_id=payment_id,
                sale_id=sale_id,
                session=db,
            )
            if not tx_id:
                return 0

            await self.tx_repo.delete_transaction(tx_id, session=db)
            return tx_id
        except Exception as e:
            logger.error(
                f"[TransactionService] delete_sale_payment_transaction "
                f"failed (payment_id={payment_id}, sale_id={sale_id}): {e}",
                exc_info=True,
            )
            return 0
        
    async def delete_sale_transactions(
        self,
        sale_id: int,
        db: AsyncSession,
    ) -> int:
        try:
            ids = await self.tx_repo.get_ids_for_sale_payment(sale_id, session=db)
            deleted = 0
            for tx_id in ids:
                await self.tx_repo.delete_transaction(tx_id, session=db)
                deleted += 1
            return deleted
        except Exception as e:
            logger.error(f"[TransactionService] delete_sale_transactions failed (sale_id={sale_id}): {e}", exc_info=True)
            return 0

    async def delete_purchase_transactions(
        self,
        purchase_id: int,
        db: AsyncSession,
    ) -> int:
        try:
            ids = await self.tx_repo.get_ids_for_purchase_payment(purchase_id, session=db)
            deleted = 0
            for tx_id in ids:
                await self.tx_repo.delete_transaction(tx_id, session=db)
                deleted += 1
            return deleted
        except Exception as e:
            logger.error(f"[TransactionService] delete_purchase_transactions failed (purchase_id={purchase_id}): {e}", exc_info=True)
            return 0
        
    async def delete_expense_transactions(
        self,
        expense_id: int,
        db: AsyncSession,
    ) -> int:
        """
        Helper: delete all transactions linked to an expense.
        No transaction block here. Returns count deleted.
        """
        try:
            ids = await self.tx_repo.get_ids_for_expense(expense_id, session=db)
            deleted = 0
            for tx_id in ids:
                await self.tx_repo.delete_transaction(tx_id, session=db)
                deleted += 1
            return deleted
        except Exception as e:
            logger.error(
                f"[TransactionService] delete_expense_transactions failed (expense_id={expense_id}): {e}",
                exc_info=True,
            )
            return 0
        
    def _extract_abono_nombre(self, desc: Optional[str]) -> Optional[str]:
        """Devuelve el nombre si la descripción es 'Abono saldo <NOMBRE>'."""
        if not desc:
            return None
        m = re.match(r'^\s*abono\s+saldo\s+(.+)\s*$', desc.strip(), re.IGNORECASE)
        return m.group(1).strip() if m else None

    async def _try_reverse_abono_saldo(self, tx, db: AsyncSession) -> bool:
        """
        Reversa específica de 'Abono saldo <NOMBRE>':
          ↓ banco, ↑ saldo cliente. True si aplicó, False si no.
        """
        nombre = self._extract_abono_nombre(tx.description)
        if not nombre:
            return False

        bank = await self.bank_repo.get_by_id(tx.bank_id, session=db)
        if not bank:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail=f"Banco {tx.bank_id} no encontrado")

        amount = float(tx.amount or 0.0)
        if amount <= 0:
            return True  

        customer = await self.customer_repository.get_by_name(nombre, session=db)
        if not customer:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail=f'Cliente con nombre exacto "{nombre}" no encontrado')

        if (bank.balance or 0.0) < amount:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"Saldo insuficiente para revertir abono (banco {bank.id} tiene {bank.balance:.2f})")

        await self.bank_repo.decrease_balance(bank.id, amount, session=db)
        await self.customer_repository.increase_balance(customer.id, amount, session=db)
        return True

    async def delete_manual_transaction(
        self,
        transaction_id: int,
        db: AsyncSession,
    ) -> bool:
        """
        Revierte por tipo ('ingreso'|'retiro') o, si es 'Abono saldo <NOMBRE>',
        descuenta banco y suma al cliente. Luego elimina la transacción.
        """
        async with db.begin():
            tx = await self.tx_repo.get_by_id(transaction_id, session=db)
            if not tx:
                return False

            # Caso especial: Abono saldo <NOMBRE>
            if await self._try_reverse_abono_saldo(tx, db):
                await self.tx_repo.delete(tx, session=db)
                return True

            # Reversa genérica por tipo
            tx_type = await self.type_repo.get_by_id(tx.type_id, session=db)
            if not tx_type:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                    detail=f"Tipo de transacción {tx.type_id} no encontrado")

            bank = await self.bank_repo.get_by_id(tx.bank_id, session=db)
            if not bank:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                    detail=f"Banco {tx.bank_id} no encontrado")

            amount = float(tx.amount or 0.0)
            tname = (tx_type.name or "").strip().lower()

            if tname == "ingreso":
                if (bank.balance or 0.0) < amount:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                        detail=f"Saldo insuficiente para revertir ingreso (banco {bank.id} tiene {bank.balance:.2f})")
                await self.bank_repo.decrease_balance(bank.id, amount, session=db)
            elif tname == "retiro":
                await self.bank_repo.increase_balance(bank.id, amount, session=db)

            await self.tx_repo.delete(tx, session=db)
            return True
    
    async def list_transactions(self, page: int, db: AsyncSession) -> TransactionPageDTO:
        page_size = self.PAGE_SIZE
        offset = max(page - 1, 0) * page_size

        # Soporta que el repo devuelva (items, total) o (items, total, algo_mas)
        items, total, *rest = await self.tx_repo.list_paginated(
            offset=offset, limit=page_size, session=db
        )

        view_items = [
            TransactionViewDTO(
                id=t.id,
                bank=(t.bank.name if getattr(t, "bank", None) else f"Bank {t.bank_id}"),
                amount=float(t.amount) if t.amount is not None else 0.0,  # <- evita warn Decimal
                type_str=(t.type.name if getattr(t, "type", None) else "Desconocido"),
                description=getattr(t, "description", None),
                created_at=t.created_at,
                is_auto=t.is_auto,
            )
            for t in items
        ]

        total = int(total or 0)
        total_pages = max(1, ceil(total / page_size)) if total else 1

        return TransactionPageDTO(
            items=view_items,
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1,
        )