from datetime import datetime
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession

from app.v1_0.models import Bank  
from app.v1_0.schemas import BankCreateSchema
from .base_repository import BaseRepository

class BankRepository(BaseRepository[Bank]):
    """
    Repository for Bank model.
    English API with Spanish aliases preserved for backwards compatibility.
    """

    def __init__(self):
        super().__init__(Bank)

    async def create_bank(
        self,
        dto: BankCreateSchema,
        session: AsyncSession
    ) -> Bank:
        """
        Create a new Bank from the incoming DTO and flush to assign its ID.
        """
        bank = Bank(**dto.model_dump())
        await self.add(bank, session)
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

        bank.saldo = new_balance
        bank.fecha_actualizacion = datetime.now()
        await self.update(bank, session)
        return bank

    async def delete_bank(
        self,
        bank_id: int,
        session: AsyncSession
    ) -> bool:
        """
        Delete a Bank by its ID.

        Returns
        -------
        bool
            True if the bank existed and was deleted. False otherwise.
        """
        bank = await self.get_by_id(bank_id, session)
        if not bank:
            return False

        await self.delete(bank, session)
        return True

    async def increase_balance(
        self,
        bank_id: int,
        amount: float,
        session: AsyncSession
    ) -> Optional[Bank]:
        """
        Increase the Bank balance and update the timestamp.
        """
        bank = await self.get_by_id(bank_id, session)
        if not bank:
            return None

        bank.saldo += amount
        bank.fecha_actualizacion = datetime.now()
        await self.update(bank, session)
        return bank

    async def decrease_balance(
        self,
        bank_id: int,
        amount: float,
        session: AsyncSession
    ) -> Optional[Bank]:
        """
        Decrease the Bank balance and update the timestamp.
        """
        bank = await self.get_by_id(bank_id, session)
        if not bank:
            return None

        bank.saldo -= amount
        bank.fecha_actualizacion = datetime.now()
        await self.update(bank, session)
        return bank

    async def list_banks(
        self,
        session: AsyncSession
    ) -> List[Bank]:
        """
        Return all Banks with all fields.
        """
        return await self.get_all(session)