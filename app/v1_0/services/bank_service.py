from typing import Optional, List
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import logger
from app.core.realtime import publish_realtime_event
from app.v1_0.entities import BankDTO
from app.v1_0.repositories.bank_repository import BankRepository
from app.v1_0.schemas import BankCreate


class BankService:
    """Service layer for managing bank accounts and balances."""

    def __init__(self, bank_repository: BankRepository) -> None:
        self.bank_repository = bank_repository

    async def create_bank(
        self,
        payload: BankCreate,
        db: AsyncSession,
        channel_id: Optional[str] = None,
    ) -> BankDTO:
        """
        Create a new bank record.

        Behavior:
        - Persists a new bank record.
        - Optionally emits a realtime `bank:created` event.

        Args:
            payload: BankCreate schema containing bank details.
            db: Active async database session.
            channel_id: Optional realtime channel to notify subscribers.

        Returns:
            BankDTO with created bank data.

        Raises:
            HTTPException: 500 if persistence fails.
        """
        logger.info("[BankService] Creating bank with payload: %s", payload.model_dump())

        async def _run() -> BankDTO:
            bank = await self.bank_repository.create_bank(payload, session=db)
            logger.info("[BankService] Bank created successfully ID=%s", bank.id)
            return BankDTO(
                id=bank.id,
                name=bank.name,
                account_number=bank.account_number,
                balance=bank.balance,
                created_at=bank.created_at,
                updated_at=bank.updated_at,
            )

        if not db.in_transaction():
            await db.begin()
        try:
            dto = await _run()
            await db.commit()
        except Exception as e:
            await db.rollback()
            logger.error("[BankService] Failed to create bank: %s", e, exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to create bank")

        if channel_id:
            try:
                await publish_realtime_event(
                    channel_id=channel_id,
                    resource="bank",
                    action="created",
                    payload={"id": dto.id},
                )
            except Exception as e:
                logger.error("[BankService] RT publish failed (create_bank): %s", e, exc_info=True)

        return dto

    async def get_bank_by_id(self, bank_id: int, db: AsyncSession) -> Optional[BankDTO]:
        """
        Retrieve a single bank by its ID.

        Args:
            bank_id: Bank identifier.
            db: Active async database session.

        Returns:
            BankDTO if found, otherwise None.

        Raises:
            HTTPException: 500 if database access fails.
        """
        logger.debug("[BankService] Fetching bank by ID=%s", bank_id)
        try:
            bank = await self.bank_repository.get_by_id(bank_id, session=db)
            if not bank:
                logger.warning("[BankService] Bank not found ID=%s", bank_id)
                return None

            return BankDTO(
                id=bank.id,
                name=bank.name,
                account_number=bank.account_number,
                balance=bank.balance,
                created_at=bank.created_at,
                updated_at=getattr(bank, "updated_at", None),
            )
        except Exception as e:
            logger.error("[BankService] Error fetching bank ID=%s: %s", bank_id, e, exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to fetch bank")

    async def get_all_banks(self, db: AsyncSession) -> List[BankDTO]:
        """
        List all registered banks.

        Args:
            db: Active async database session.

        Returns:
            List of all BankDTOs.

        Raises:
            HTTPException: 500 if listing fails.
        """
        logger.debug("[BankService] Listing all banks")
        try:
            banks = await self.bank_repository.list_all(session=db)
            logger.info("[BankService] Retrieved %s banks", len(banks))
            return [
                BankDTO(
                    id=b.id,
                    name=b.name,
                    account_number=b.account_number,
                    balance=b.balance,
                    created_at=b.created_at,
                    updated_at=getattr(b, "updated_at", None),
                )
                for b in banks
            ]
        except Exception as e:
            logger.error("[BankService] Error listing banks: %s", e, exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to list banks")

    async def update_balance(
        self,
        bank_id: int,
        new_balance: float,
        db: AsyncSession,
        channel_id: Optional[str] = None,
    ) -> BankDTO:
        """
        Set the balance of a bank to a specific value.

        Args:
            bank_id: Bank identifier.
            new_balance: New balance value to set.
            db: Active async database session.
            channel_id: Optional realtime channel for "bank:updated".

        Returns:
            Updated BankDTO.

        Raises:
            HTTPException:
                404 if the bank does not exist.
                500 on persistence failure.
        """
        logger.info("[BankService] Updating balance for Bank ID=%s to %s", bank_id, new_balance)

        async def _run() -> BankDTO:
            bank = await self.bank_repository.update_balance(bank_id, new_balance, session=db)
            if not bank:
                raise HTTPException(status_code=404, detail="Bank not found.")
            return BankDTO(
                id=bank.id,
                name=bank.name,
                account_number=bank.account_number,
                balance=bank.balance,
                created_at=bank.created_at,
                updated_at=bank.updated_at,
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
            logger.error("[BankService] Error updating balance ID=%s: %s", bank_id, e, exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to update balance")

        if channel_id:
            try:
                await publish_realtime_event(
                    channel_id=channel_id,
                    resource="bank",
                    action="updated",
                    payload={"id": dto.id},
                )
            except Exception as e:
                logger.error("[BankService] RT publish failed (update_balance): %s", e, exc_info=True)

        return dto

    async def delete_bank(self, bank_id: int, db: AsyncSession, channel_id: Optional[str] = None) -> bool:
        """
        Delete a bank if its balance is zero.

        Args:
            bank_id: Bank identifier.
            db: Active async database session.
            channel_id: Optional realtime channel for "bank:deleted".

        Returns:
            True if the bank was deleted, False if not found.

        Raises:
            HTTPException:
                400 if the bank still has a positive balance.
                500 if deletion fails.
        """
        logger.warning("[BankService] Attempting to delete bank ID=%s", bank_id)

        async def _run() -> bool:
            bank = await self.bank_repository.get_by_id(bank_id, session=db)
            if not bank:
                return False
            if float(bank.balance or 0.0) > 0.0:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot delete a bank with balance greater than 0.",
                )
            result = await self.bank_repository.delete_bank(bank_id, session=db)
            return bool(result)

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
            logger.error("[BankService] Error deleting bank ID=%s: %s", bank_id, e, exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to delete bank")

        if not existed:
            return False

        if channel_id:
            try:
                await publish_realtime_event(
                    channel_id=channel_id,
                    resource="bank",
                    action="deleted",
                    payload={"id": bank_id},
                )
            except Exception as e:
                logger.error("[BankService] RT publish failed (delete_bank): %s", e, exc_info=True)

        return True

    async def decrease_balance(self, bank_id: int, amount: float, db: AsyncSession) -> BankDTO:
        """
        Decrease a bank's balance by a specified amount.

        Args:
            bank_id: Bank identifier.
            amount: Positive amount to subtract from the current balance.
            db: Active async database session.

        Returns:
            Updated BankDTO with new balance.

        Raises:
            HTTPException:
                400 if amount <= 0 or insufficient balance.
                404 if bank not found.
                500 on persistence failure.
        """
        logger.info("[BankService] Decreasing balance for Bank ID=%s by %s", bank_id, amount)

        if amount <= 0:
            raise HTTPException(status_code=400, detail="Amount must be greater than zero.")

        async def _run() -> BankDTO:
            bank = await self.bank_repository.get_by_id(bank_id, session=db)
            if not bank:
                raise HTTPException(status_code=404, detail="Bank not found.")
            if float(bank.balance or 0.0) < amount:
                raise HTTPException(
                    status_code=400,
                    detail=f"Insufficient balance: available {bank.balance}, required {amount}",
                )

            updated = await self.bank_repository.decrease_balance(bank_id, amount, session=db)
            return BankDTO(
                id=updated.id,
                name=updated.name,
                account_number=updated.account_number,
                balance=updated.balance,
                created_at=updated.created_at,
                updated_at=getattr(updated, "updated_at", None),
            )

        if not db.in_transaction():
            await db.begin()
        try:
            dto = await _run()
            await db.commit()
            return dto
        except HTTPException:
            await db.rollback()
            raise
        except Exception as e:
            await db.rollback()
            logger.error("[BankService] Error decreasing balance ID=%s: %s", bank_id, e, exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to decrease balance")

    async def increase_balance(self, bank_id: int, amount: float, db: AsyncSession) -> BankDTO:
        """
        Increase a bank's balance by a specified amount.

        Args:
            bank_id: Bank identifier.
            amount: Positive amount to add to the current balance.
            db: Active async database session.

        Returns:
            Updated BankDTO with new balance.

        Raises:
            HTTPException:
                400 if amount <= 0.
                404 if bank not found.
                500 on persistence failure.
        """
        logger.info("[BankService] Increasing balance for Bank ID=%s by %s", bank_id, amount)

        if amount <= 0:
            raise HTTPException(status_code=400, detail="Amount must be greater than zero.")

        async def _run() -> BankDTO:
            bank = await self.bank_repository.get_by_id(bank_id, session=db)
            if not bank:
                raise HTTPException(status_code=404, detail="Bank not found.")

            updated = await self.bank_repository.increase_balance(bank_id, amount, session=db)
            return BankDTO(
                id=updated.id,
                name=updated.name,
                account_number=updated.account_number,
                balance=updated.balance,
                created_at=updated.created_at,
                updated_at=getattr(updated, "updated_at", None),
            )

        if not db.in_transaction():
            await db.begin()
        try:
            dto = await _run()
            await db.commit()
            return dto
        except HTTPException:
            await db.rollback()
            raise
        except Exception as e:
            await db.rollback()
            logger.error("[BankService] Error increasing balance ID=%s: %s", bank_id, e, exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to increase balance")
