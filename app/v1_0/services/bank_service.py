from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.v1_0.repositories.bank_repository import BankRepository
from app.v1_0.schemas import BankCreate
from app.v1_0.models import Bank
from app.core.logger import logger

class BankService:
    def __init__(self, bank_repository: BankRepository) -> None:
        self.bank_repository = bank_repository

    async def create_bank(self, payload: BankCreate, db: AsyncSession) -> Bank:
        """Create bank with detailed logging."""
        logger.info(f"[BankService] Creating bank with payload: {payload.model_dump()}")
        try:
            async with db.begin():
                bank = await self.bank_repository.create_bank(payload, session=db)
            logger.info(f"[BankService] Bank created successfully with ID={bank.id}")
            return bank
        except Exception as e:
            logger.error(f"[BankService] Failed to create bank: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to create bank")

    async def get_bank_by_id(self, bank_id: int, db: AsyncSession) -> Optional[Bank]:
        """Get bank by ID."""
        logger.debug(f"[BankService] Fetching bank by ID={bank_id}")
        try:
            async with db.begin():
                bank = await self.bank_repository.get_by_id(bank_id, session=db)
            if not bank:
                logger.warning(f"[BankService] Bank not found with ID={bank_id}")
            else:
                logger.info(f"[BankService] Bank fetched successfully: {bank.name}")
            return bank
        except Exception as e:
            logger.error(f"[BankService] Error fetching bank ID={bank_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to fetch bank")

    async def get_all_banks(self, db: AsyncSession) -> List[Bank]:
        """List all banks."""
        logger.debug("[BankService] Listing all banks...")
        try:
            async with db.begin():
                banks = await self.bank_repository.list_all(session=db)
            logger.info(f"[BankService] Retrieved {len(banks)} banks from database.")
            return banks
        except Exception as e:
            logger.error(f"[BankService] Error listing banks: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to list banks")

    async def update_balance(self, bank_id: int, new_balance: float, db: AsyncSession) -> Optional[Bank]:
        """Update balance."""
        logger.info(f"[BankService] Updating balance for Bank ID={bank_id} to {new_balance}")
        try:
            async with db.begin():
                bank = await self.bank_repository.update_balance(bank_id, new_balance, session=db)
            if not bank:
                logger.warning(f"[BankService] Bank not found for update ID={bank_id}")
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bank not found.")
            logger.info(f"[BankService] Bank ID={bank_id} balance updated successfully.")
            return bank
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"[BankService] Error updating bank balance ID={bank_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to update balance")

    async def delete_bank(self, bank_id: int, db: AsyncSession) -> bool:
        """Delete bank if balance == 0."""
        logger.warning(f"[BankService] Attempting to delete bank ID={bank_id}")
        try:
            async with db.begin():
                bank = await self.bank_repository.get_by_id(bank_id, session=db)
                if not bank:
                    logger.warning(f"[BankService] Bank not found for deletion ID={bank_id}")
                    return False
                if (bank.balance or 0) > 0:
                    logger.warning(f"[BankService] Cannot delete bank ID={bank_id} with balance={bank.balance}")
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Cannot delete a bank with balance greater than 0."
                    )
                result = await self.bank_repository.delete_bank(bank_id, session=db)
            logger.info(f"[BankService] Bank ID={bank_id} deleted successfully.")
            return result
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"[BankService] Error deleting bank ID={bank_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to delete bank")

    async def decrease_balance(self, bank_id: int, amount: float, db: AsyncSession) -> Bank:
        """Decrease balance with validation and tracking."""
        logger.info(f"[BankService] Decreasing balance for Bank ID={bank_id} by {amount}")
        try:
            if amount <= 0:
                logger.warning(f"[BankService] Invalid amount to decrease: {amount}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Amount to decrease must be greater than zero."
                )
            async with db.begin():
                bank = await self.bank_repository.get_by_id(bank_id, session=db)
                if not bank:
                    logger.warning(f"[BankService] Bank not found ID={bank_id}")
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bank not found.")
                if (bank.balance or 0) < amount:
                    logger.warning(
                        f"[BankService] Insufficient balance for ID={bank_id}. "
                        f"Available={bank.balance}, Required={amount}"
                    )
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Insufficient balance: available {bank.balance}, required {amount}"
                    )
                updated = await self.bank_repository.decrease_balance(bank_id, amount, session=db)
            logger.info(f"[BankService] Balance decreased successfully for Bank ID={bank_id}. New={updated.balance}")
            return updated
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"[BankService] Error decreasing balance ID={bank_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to decrease balance")

    async def increase_balance(self, bank_id: int, amount: float, db: AsyncSession) -> Bank:
        """Increase balance with validation and tracking."""
        logger.info(f"[BankService] Increasing balance for Bank ID={bank_id} by {amount}")
        try:
            if amount <= 0:
                logger.warning(f"[BankService] Invalid amount to increase: {amount}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Amount to increase must be greater than zero."
                )
            async with db.begin():
                bank = await self.bank_repository.get_by_id(bank_id, session=db)
                if not bank:
                    logger.warning(f"[BankService] Bank not found ID={bank_id}")
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bank not found.")
                updated = await self.bank_repository.increase_balance(bank_id, amount, session=db)
            logger.info(f"[BankService] Balance increased successfully for Bank ID={bank_id}. New={updated.balance}")
            return updated
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"[BankService] Error increasing balance ID={bank_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to increase balance")
