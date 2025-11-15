from math import ceil
from decimal import Decimal
from typing import Optional
import re

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import logger
from app.core.realtime import publish_realtime_event
from app.v1_0.schemas import TransactionCreate
from app.v1_0.entities import TransactionDTO, TransactionPageDTO, TransactionViewDTO
from app.v1_0.models import Transaction
from app.v1_0.repositories import (
    TransactionRepository,
    TransactionTypeRepository,
    BankRepository,
    CustomerRepository,
)

class TransactionService:
    def __init__(
        self,
        transaction_repository: TransactionRepository,
        transaction_type_repository: TransactionTypeRepository,
        bank_repository: BankRepository,
        customer_repository: CustomerRepository,
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
        Insert a transaction without business validation or transaction block.

        Intended for internal use by other services that already handle:
        - Domain validation.
        - Surrounding database transaction.

        Args:
            payload: TransactionCreate payload with transaction data.
            db: Active async database session.

        Returns:
            The created Transaction ORM instance.

        Raises:
            Exception: If the repository operation fails.
        """
        try:
            return await self.tx_repo.create_transaction(payload, session=db)
        except Exception as e:
            logger.error(
                "[TransactionService] insert_transaction failed: %s",
                e,
                exc_info=True,
            )
            raise

    async def create(
        self,
        payload: TransactionCreate,
        db: AsyncSession,
        channel_id: Optional[str] = None,
    ) -> TransactionDTO:
        """
        Create a manual bank transaction and update the bank balance.

        Supported types (by name of TransactionType):
        - "Ingreso": Increases bank balance.
        - "Retiro": Decreases bank balance (requires sufficient funds).

        Args:
            payload: TransactionCreate with bank_id, amount, type_id, and description.
            db: Active async database session.
            channel_id: Optional realtime channel identifier to publish events.

        Returns:
            TransactionDTO representing the created transaction.

        Raises:
            HTTPException:
                400 if type_id is missing, unsupported, or insufficient funds.
                404 if bank or transaction type does not exist.
                500 if creation fails.
        """
        type_id = payload.type_id
        if type_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="type_id is required.",
            )

        amount = Decimal(str(payload.amount))

        async def _run() -> TransactionDTO:
            bank = await self.bank_repo.get_by_id(
                payload.bank_id,
                session=db,
            )
            if not bank:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Bank not found.",
                )

            tx_type = await self.type_repo.get_by_id(type_id, session=db)
            if not tx_type:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Transaction type not found.",
                )

            kind = (tx_type.name or "").strip().lower()
            current_balance = Decimal(str(bank.balance or 0))

            if kind == "ingreso":
                new_balance = current_balance + amount
            elif kind == "retiro":
                if amount > current_balance:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Insufficient funds.",
                    )
                new_balance = current_balance - amount
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Unsupported transaction type. Use 'Ingreso' or 'Retiro'.",
                )

            bank.balance = float(new_balance)

            tx = await self.tx_repo.create_transaction(
                payload,
                session=db,
            )

            return TransactionDTO(
                id=tx.id,
                bank_id=tx.bank_id,
                amount=tx.amount,
                type_id=tx.type_id,
                description=tx.description,
                is_auto=tx.is_auto,
                created_at=tx.created_at,
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
                "[TransactionService] Create failed: %s",
                e,
                exc_info=True,
            )
            raise HTTPException(
                status_code=500,
                detail="Failed to create transaction",
            )

        if channel_id:
            try:
                await publish_realtime_event(
                    channel_id=channel_id,
                    resource="transaction",
                    action="created",
                    payload={"id": dto.id, "bank_id": dto.bank_id},
                )
                logger.info(
                    "[TransactionService] RT transaction created published: id=%s",
                    dto.id,
                )
            except Exception as e:
                logger.error(
                    "[TransactionService] RT publish failed (create): %s",
                    e,
                    exc_info=True,
                )

        return dto

    async def delete_purchase_payment_transaction(
        self,
        payment_id: int,
        purchase_id: int,
        db: AsyncSession,
    ) -> int:
        """
        Delete the transaction linked to a purchase payment.

        No explicit transaction block; caller must handle it.

        Args:
            payment_id: Purchase payment identifier.
            purchase_id: Related purchase identifier.
            db: Active async database session.

        Returns:
            ID of the deleted transaction, or 0 if none was found.
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
                "[TransactionService] delete_purchase_payment_transaction "
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
        Delete the transaction linked to a sale payment.

        Caller manages the surrounding transaction.

        Args:
            payment_id: Sale payment identifier.
            sale_id: Related sale identifier.
            db: Active async database session.

        Returns:
            ID of the deleted transaction, or 0 if none was found.
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
                "[TransactionService] delete_sale_payment_transaction "
                f"failed (payment_id={payment_id}, sale_id={sale_id}): {e}",
                exc_info=True,
            )
            return 0

    async def delete_sale_transactions(
        self,
        sale_id: int,
        db: AsyncSession,
    ) -> int:
        """
        Delete all transactions linked to a sale.

        Args:
            sale_id: Sale identifier.
            db: Active async database session.

        Returns:
            Number of deleted transactions.
        """
        try:
            ids = await self.tx_repo.get_ids_for_sale_payment(
                sale_id,
                session=db,
            )
            deleted = 0
            for tx_id in ids:
                await self.tx_repo.delete_transaction(tx_id, session=db)
                deleted += 1
            return deleted
        except Exception as e:
            logger.error(
                "[TransactionService] delete_sale_transactions failed (sale_id=%s): %s",
                sale_id,
                e,
                exc_info=True,
            )
            return 0

    async def delete_purchase_transactions(
        self,
        purchase_id: int,
        db: AsyncSession,
    ) -> int:
        """
        Delete all transactions linked to a purchase.

        Args:
            purchase_id: Purchase identifier.
            db: Active async database session.

        Returns:
            Number of deleted transactions.
        """
        try:
            ids = await self.tx_repo.get_ids_for_purchase_payment(
                purchase_id,
                session=db,
            )
            deleted = 0
            for tx_id in ids:
                await self.tx_repo.delete_transaction(tx_id, session=db)
                deleted += 1
            return deleted
        except Exception as e:
            logger.error(
                "[TransactionService] delete_purchase_transactions failed (purchase_id=%s): %s",
                purchase_id,
                e,
                exc_info=True,
            )
            return 0

    async def delete_expense_transactions(
        self,
        expense_id: int,
        db: AsyncSession,
    ) -> int:
        """
        Delete all transactions linked to an expense.

        No explicit transaction block; caller must handle it.

        Args:
            expense_id: Expense identifier.
            db: Active async database session.

        Returns:
            Number of deleted transactions.
        """
        try:
            ids = await self.tx_repo.get_ids_for_expense(
                expense_id,
                session=db,
            )
            deleted = 0
            for tx_id in ids:
                await self.tx_repo.delete_transaction(tx_id, session=db)
                deleted += 1
            return deleted
        except Exception as e:
            logger.error(
                "[TransactionService] delete_expense_transactions failed (expense_id=%s): %s",
                expense_id,
                e,
                exc_info=True,
            )
            return 0

    def _extract_abono_nombre(
        self,
        desc: Optional[str],
    ) -> Optional[str]:
        """
        Extract the customer name from descriptions in the form:
        'Abono saldo <NAME>'.

        Args:
            desc: Description text.

        Returns:
            Extracted name if format matches, otherwise None.
        """
        if not desc:
            return None
        m = re.match(
            r"^\s*abono\s+saldo\s+(.+)\s*$",
            desc.strip(),
            re.IGNORECASE,
        )
        return m.group(1).strip() if m else None

    async def _try_reverse_abono_saldo(
        self,
        tx: Transaction,
        db: AsyncSession,
    ) -> bool:
        """
        Try to reverse a customer balance payment of the form 'Abono saldo <NAME>'.

        Logic:
        - Decrease bank balance by transaction amount.
        - Increase the matched customer's balance by the same amount.

        Args:
            tx: Transaction candidate to reverse.
            db: Active async database session.

        Returns:
            True if the transaction was recognized and reversed, False otherwise.

        Raises:
            HTTPException:
                404 if bank or customer cannot be resolved.
                400 if bank has insufficient balance to reverse.
        """
        nombre = self._extract_abono_nombre(tx.description)
        if not nombre:
            return False

        bank = await self.bank_repo.get_by_id(
            tx.bank_id,
            session=db,
        )
        if not bank:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Banco {tx.bank_id} no encontrado",
            )

        amount = float(tx.amount or 0.0)
        if amount <= 0:
            return True

        customer = await self.customer_repository.get_by_name(
            nombre,
            session=db,
        )
        if not customer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f'Cliente con nombre exacto "{nombre}" no encontrado',
            )

        if (bank.balance or 0.0) < amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Saldo insuficiente para revertir abono "
                    f"(banco {bank.id} tiene {bank.balance:.2f})"
                ),
            )

        await self.bank_repo.decrease_balance(
            bank.id,
            amount,
            session=db,
        )
        await self.customer_repository.increase_balance(
            customer.id,
            amount,
            session=db,
        )
        return True

    async def delete_manual_transaction(
        self,
        transaction_id: int,
        db: AsyncSession,
        channel_id: Optional[str] = None,
    ) -> bool:
        """
        Delete a manual transaction and revert its financial impact when possible.

        Rules:
        - If description matches 'Abono saldo <NAME>':
            - Reverse customer payment (decrease bank, increase customer balance).
        - Else if type is 'Ingreso':
            - Decrease bank balance by transaction amount (requires sufficient funds).
        - Else if type is 'Retiro':
            - Increase bank balance by transaction amount.
        - Only manual domain logic is applied (is_auto should be handled by caller).

        Args:
            transaction_id: Identifier of the transaction to delete.
            db: Active async database session.
            channel_id: Optional realtime channel identifier to publish events.

        Returns:
            True if the transaction existed and was deleted, False otherwise.

        Raises:
            HTTPException:
                400 or 404 for validation and consistency errors.
                500 if the deletion flow fails.
        """

        async def _run() -> bool:
            tx = await self.tx_repo.get_by_id(
                transaction_id,
                session=db,
            )
            if not tx:
                return False

            if await self._try_reverse_abono_saldo(tx, db):
                await self.tx_repo.delete(tx, session=db)
                return True

            tx_type = await self.type_repo.get_by_id(
                tx.type_id,
                session=db,
            )
            if not tx_type:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Tipo de transacción {tx.type_id} no encontrado",
                )

            bank = await self.bank_repo.get_by_id(
                tx.bank_id,
                session=db,
            )
            if not bank:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Banco {tx.bank_id} no encontrado",
                )

            amount = float(tx.amount or 0.0)
            tname = (tx_type.name or "").strip().lower()

            if tname == "ingreso":
                if float(bank.balance or 0.0) < amount:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=(
                            "Saldo insuficiente para revertir ingreso "
                            f"(banco {bank.id} tiene {bank.balance:.2f})"
                        ),
                    )
                await self.bank_repo.decrease_balance(
                    bank.id,
                    amount,
                    session=db,
                )
            elif tname == "retiro":
                await self.bank_repo.increase_balance(
                    bank.id,
                    amount,
                    session=db,
                )

            await self.tx_repo.delete(tx, session=db)
            return True

        if not db.in_transaction():
            await db.begin()

        try:
            existed = await _run()
            await db.commit()
        except HTTPException:
            await db.rollback()
            raise
        except Exception as e:
            await db.rollback()
            logger.error(
                "[TransactionService] delete_manual_transaction failed ID=%s: %s",
                transaction_id,
                e,
                exc_info=True,
            )
            raise HTTPException(
                status_code=500,
                detail="Failed to delete transaction",
            )

        if not existed:
            return False

        if channel_id:
            try:
                await publish_realtime_event(
                    channel_id=channel_id,
                    resource="transaction",
                    action="deleted",
                    payload={"id": transaction_id},
                )
                logger.info(
                    "[TransactionService] RT transaction deleted published: id=%s",
                    transaction_id,
                )
            except Exception as e:
                logger.error(
                    "[TransactionService] RT publish failed (delete): %s",
                    e,
                    exc_info=True,
                )

        return True

    async def list_transactions(
        self,
        page: int,
        db: AsyncSession,
    ) -> TransactionPageDTO:
        """
        List transactions in a paginated format with resolved relations.

        For each transaction includes:
        - Bank name or fallback.
        - Type name or "Desconocido".
        - Amount, description, created_at, is_auto.

        Args:
            page: Page number to retrieve (1-based).
            db: Active async database session.

        Returns:
            TransactionPageDTO with items and pagination metadata.
        """
        page_size = self.PAGE_SIZE
        offset = max(page - 1, 0) * page_size

        items, total, *_ = await self.tx_repo.list_paginated(
            offset=offset,
            limit=page_size,
            session=db,
        )

        view_items = [
            TransactionViewDTO(
                id=t.id,
                bank=(
                    t.bank.name
                    if getattr(t, "bank", None)
                    else f"Bank {t.bank_id}"
                ),
                amount=float(t.amount) if t.amount is not None else 0.0,
                type_str=(
                    t.type.name
                    if getattr(t, "type", None)
                    else "Desconocido"
                ),
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
