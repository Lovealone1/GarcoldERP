import asyncio
from typing import AsyncGenerator, Callable, List
from dataclasses import dataclass
from datetime import datetime
import pytest

from unittest.mock import AsyncMock
from sqlalchemy.ext.asyncio import AsyncSession
from app.v1_0.repositories import BankRepository
from app.v1_0.services import BankService

from app.v1_0.tests.factories import (
    seed_banks,
    seed_customers,
    seed_expense_categories,
    seed_expenses,
    seed_investments,
    seed_loans,
    seed_products,
    seed_suppliers,
    seed_transaction_types,
    seed_roles,
    seed_users,
    seed_statuses,
    seed_permissions,
    seed_company,
)

class FakeAuthContext:
    def __init__(self, user_id="test-user"):
        self.user_id = user_id

@pytest.fixture
def fake_auth_ctx():
    return FakeAuthContext()

@dataclass
class FakeAsyncSession(AsyncSession):
    began: bool = False
    committed: bool = False
    rolled_back: bool = False

    def __init__(self) -> None:
        self.began = False
        self.committed = False
        self.rolled_back = False

    async def begin(self):
        self.began = True

    async def commit(self):
        self.committed = True

    async def rollback(self):
        self.rolled_back = True

    def in_transaction(self) -> bool:
        return self.began and not (self.committed or self.rolled_back)


@pytest.fixture
def db_session() -> FakeAsyncSession:
    return FakeAsyncSession()

@pytest.fixture
def bank_repository(mocker) -> BankRepository:
    repo = mocker.Mock(spec=BankRepository)
    repo.create_bank = AsyncMock()
    repo.get_by_id = AsyncMock()
    repo.list_all = AsyncMock()
    repo.update_balance = AsyncMock()
    repo.decrease_balance = AsyncMock()
    repo.increase_balance = AsyncMock()
    repo.delete_bank = AsyncMock()
    return repo

@pytest.fixture
def bank_service(bank_repository: BankRepository) -> BankService:
    return BankService(bank_repository=bank_repository)


def _wrap_factory(factory_fn):
    async def run_fake():
        return await factory_fn(None)  # ignora db
    return run_fake


@pytest.fixture
def seed_banks_fixture():
    return _wrap_factory(seed_banks)

@pytest.fixture
def seed_customers_fixture():
    return _wrap_factory(seed_customers)

@pytest.fixture
def seed_expense_categories_fixture():
    return _wrap_factory(seed_expense_categories)

@pytest.fixture
def seed_expenses_fixture():
    return _wrap_factory(seed_expenses)

@pytest.fixture
def seed_investments_fixture():
    return _wrap_factory(seed_investments)

@pytest.fixture
def seed_loans_fixture():
    return _wrap_factory(seed_loans)

@pytest.fixture
def seed_products_fixture():
    return _wrap_factory(seed_products)

@pytest.fixture
def seed_suppliers_fixture():
    return _wrap_factory(seed_suppliers)

@pytest.fixture
def seed_transaction_types_fixture():
    return _wrap_factory(seed_transaction_types)

@pytest.fixture
def seed_roles_fixture():
    return _wrap_factory(seed_roles)

@pytest.fixture
def seed_users_fixture():
    return _wrap_factory(seed_users)

@pytest.fixture
def seed_statuses_fixture():
    return _wrap_factory(seed_statuses)

@pytest.fixture
def seed_permissions_fixture():
    return _wrap_factory(seed_permissions)

@pytest.fixture
def seed_company_fixture():
    return _wrap_factory(seed_company)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
