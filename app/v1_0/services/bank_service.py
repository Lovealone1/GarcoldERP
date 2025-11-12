from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.v1_0.repositories.bank_repository import BankRepository
from app.v1_0.schemas import BankCreate
from app.v1_0.models import Bank
from app.v1_0.entities import BankDTO
from app.core.realtime import publish_realtime_event
from app.core.logger import logger

class BankService:
    def __init__(self, bank_repository: BankRepository) -> None:
        self.bank_repository = bank_repository

    async def create_bank(
        self,
        payload: BankCreate,
        db: AsyncSession,
        channel_id: Optional[str] = None,
    ) -> BankDTO:
        logger.info(
            "[BankService] Creating bank with payload: %s",
            payload.model_dump(),
        )

        async def _run() -> BankDTO:
            bank = await self.bank_repository.create_bank(
                payload,
                session=db,
            )
            logger.info(
                "[BankService] Bank created successfully ID=%s",
                bank.id,
            )
            return BankDTO(
                id=bank.id,
                name=bank.name,
                account_number=bank.account_number,
                balance=bank.balance,
                created_at=bank.created_at,
                updated_at=bank.updated_at
            )

        if not db.in_transaction():
            await db.begin()
        try:
            dto = await _run()
            await db.commit()
        except Exception as e:
            await db.rollback()
            logger.error(
                "[BankService] Failed to create bank: %s",
                e,
                exc_info=True,
            )
            raise HTTPException(
                status_code=500,
                detail="Failed to create bank",
            )

        if channel_id:
            try:
                await publish_realtime_event(
                    channel_id=channel_id,
                    resource="bank",
                    action="created",
                    payload={"id": dto.id},
                )
            except Exception as e:
                logger.error(
                    "[BankService] RT publish failed (create_bank): %s",
                    e,
                    exc_info=True,
                )

        return dto

    async def get_bank_by_id(
        self,
        bank_id: int,
        db: AsyncSession,
    ) -> Optional[BankDTO]:
        logger.debug(
            "[BankService] Fetching bank by ID=%s",
            bank_id,
        )
        try:
            bank = await self.bank_repository.get_by_id(
                bank_id,
                session=db,
            )
            if not bank:
                logger.warning(
                    "[BankService] Bank not found with ID=%s",
                    bank_id,
                )
                return None

            logger.info(
                "[BankService] Bank fetched successfully: %s",
                bank.name,
            )
            return BankDTO(
                id=bank.id,
                name=bank.name,
                account_number=bank.account_number,
                balance=bank.balance,
                created_at=bank.created_at,
                updated_at=getattr(bank, "updated_at", None),
            )
        except Exception as e:
            logger.error(
                "[BankService] Error fetching bank ID=%s: %s",
                bank_id,
                e,
                exc_info=True,
            )
            raise HTTPException(
                status_code=500,
                detail="Failed to fetch bank",
            )

    async def get_all_banks(
        self,
        db: AsyncSession,
    ) -> List[BankDTO]:
        logger.debug("[BankService] Listing all banks")
        try:
            banks = await self.bank_repository.list_all(
                session=db,
            )
            logger.info(
                "[BankService] Retrieved %s banks from database.",
                len(banks),
            )
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
            logger.error(
                "[BankService] Error listing banks: %s",
                e,
                exc_info=True,
            )
            raise HTTPException(
                status_code=500,
                detail="Failed to list banks",
            )

    async def update_balance(
        self,
        bank_id: int,
        new_balance: float,
        db: AsyncSession,
        channel_id: Optional[str] = None,
    ) -> BankDTO:
        logger.info(
            "[BankService] Updating balance for Bank ID=%s to %s",
            bank_id,
            new_balance,
        )

        async def _run() -> BankDTO:
            bank = await self.bank_repository.update_balance(
                bank_id,
                new_balance,
                session=db,
            )
            if not bank:
                logger.warning(
                    "[BankService] Bank not found for update ID=%s",
                    bank_id,
                )
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Bank not found.",
                )
            logger.info(
                "[BankService] Bank ID=%s balance updated successfully.",
                bank_id,
            )
            return BankDTO(
                id=bank.id,
                name=bank.name,
                account_number=bank.account_number,
                balance=bank.balance,
                created_at=bank.created_at,
                updated_at=bank.updated_at
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
                "[BankService] Error updating bank balance ID=%s: %s",
                bank_id,
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
                    resource="bank",
                    action="updated",
                    payload={"id": dto.id},
                )
            except Exception as e:
                logger.error(
                    "[BankService] RT publish failed (update_balance): %s",
                    e,
                    exc_info=True,
                )

        return dto

    async def delete_bank(
        self,
        bank_id: int,
        db: AsyncSession,
        channel_id: Optional[str] = None,
    ) -> bool:
        """Delete bank if balance == 0."""
        logger.warning(
            "[BankService] Attempting to delete bank ID=%s",
            bank_id,
        )

        async def _run() -> bool:
            bank = await self.bank_repository.get_by_id(
                bank_id,
                session=db,
            )
            if not bank:
                logger.warning(
                    "[BankService] Bank not found for deletion ID=%s",
                    bank_id,
                )
                return False

            if float(bank.balance or 0.0) > 0.0:
                logger.warning(
                    "[BankService] Cannot delete bank ID=%s with balance=%s",
                    bank_id,
                    bank.balance,
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot delete a bank with balance greater than 0.",
                )

            result = await self.bank_repository.delete_bank(
                bank_id,
                session=db,
            )
            logger.info(
                "[BankService] Bank ID=%s deleted successfully.",
                bank_id,
            )
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
            logger.error(
                "[BankService] Error deleting bank ID=%s: %s",
                bank_id,
                e,
                exc_info=True,
            )
            raise HTTPException(
                status_code=500,
                detail="Failed to delete bank",
            )

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
                logger.error(
                    "[BankService] RT publish failed (delete_bank): %s",
                    e,
                    exc_info=True,
                )

        return True

    async def decrease_balance(
        self,
        bank_id: int,
        amount: float,
        db: AsyncSession,
    ) -> BankDTO:
        logger.info(
            "[BankService] Decreasing balance for Bank ID=%s by %s",
            bank_id,
            amount,
        )

        if amount <= 0:
            logger.warning(
                "[BankService] Invalid amount to decrease: %s",
                amount,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Amount to decrease must be greater than zero.",
            )

        async def _run() -> BankDTO:
            bank = await self.bank_repository.get_by_id(
                bank_id,
                session=db,
            )
            if not bank:
                logger.warning(
                    "[BankService] Bank not found ID=%s",
                    bank_id,
                )
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Bank not found.",
                )

            if float(bank.balance or 0.0) < amount:
                logger.warning(
                    "[BankService] Insufficient balance for ID=%s. Available=%s, Required=%s",
                    bank_id,
                    bank.balance,
                    amount,
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Insufficient balance: available {bank.balance}, required {amount}",
                )

            updated = await self.bank_repository.decrease_balance(
                bank_id,
                amount,
                session=db,
            )
            logger.info(
                "[BankService] Balance decreased successfully for Bank ID=%s. New=%s",
                bank_id,
                updated.balance,
            )
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
            logger.error(
                "[BankService] Error decreasing balance ID=%s: %s",
                bank_id,
                e,
                exc_info=True,
            )
            raise HTTPException(
                status_code=500,
                detail="Failed to decrease balance",
            )

    async def increase_balance(
        self,
        bank_id: int,
        amount: float,
        db: AsyncSession,
    ) -> BankDTO:
        logger.info(
            "[BankService] Increasing balance for Bank ID=%s by %s",
            bank_id,
            amount,
        )

        if amount <= 0:
            logger.warning(
                "[BankService] Invalid amount to increase: %s",
                amount,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Amount to increase must be greater than zero.",
            )

        async def _run() -> BankDTO:
            bank = await self.bank_repository.get_by_id(
                bank_id,
                session=db,
            )
            if not bank:
                logger.warning(
                    "[BankService] Bank not found ID=%s",
                    bank_id,
                )
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Bank not found.",
                )

            updated = await self.bank_repository.increase_balance(
                bank_id,
                amount,
                session=db,
            )
            logger.info(
                "[BankService] Balance increased successfully for Bank ID=%s. New=%s",
                bank_id,
                updated.balance,
            )
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
            logger.error(
                "[BankService] Error increasing balance ID=%s: %s",
                bank_id,
                e,
                exc_info=True,
            )
            raise HTTPException(
                status_code=500,
                detail="Failed to increase balance",
            )
