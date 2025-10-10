# app/v1_0/repositories/bank_repository.py
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession

from app.v1_0.models import Bank
from app.v1_0.schemas import BankCreate  
from .base_repository import BaseRepository


class BankRepository(BaseRepository[Bank]):
    """Repository for Bank model."""

    def __init__(self) -> None:
        super().__init__(Bank)

    # Create
    async def create_bank(self, dto: BankCreate, session: AsyncSession) -> Bank:
        bank = Bank(**dto.model_dump())
        await self.add(bank, session)  # flush/refresh inside BaseRepository.add()
        return bank

    async def update_balance(
        self,
        bank_id: int,
        new_balance: float,
        session: AsyncSession
    ) -> Optional[Bank]:
        """
        Set the Bank balance and update the timestamp.
        """
        bank = await self.get_by_id(bank_id, session)
        if not bank:
            return None
        bank.balance = new_balance
        bank.updated_at = datetime.now(timezone.utc)
        await self.update(bank, session)
        return bank

    async def decrease_balance(self, bank_id: int, amount: float, session: AsyncSession) -> Bank:
        bank = await self.get_by_id(bank_id, session)
        if bank is None:
            raise ValueError("bank_not_found")

        bank.balance = (bank.balance or 0.0) - amount
        bank.updated_at = datetime.now(timezone.utc)
        await self.update(bank, session)
        return bank

    async def increase_balance(self, bank_id: int, amount: float, session: AsyncSession) -> Bank:
        bank = await self.get_by_id(bank_id, session)
        if bank is None:
            raise ValueError("bank_not_found")

        bank.balance = (bank.balance or 0.0) + amount
        bank.updated_at = datetime.now(timezone.utc)
        await self.update(bank, session)
        return bank

    # Delete
    async def delete_bank(self, bank_id: int, session: AsyncSession) -> bool:
        bank = await self.get_by_id(bank_id, session)
        if not bank:
            return False
        await self.delete(bank, session)
        return True
