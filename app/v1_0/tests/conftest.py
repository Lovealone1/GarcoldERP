import asyncio
from dataclasses import dataclass
import pytest
from unittest.mock import AsyncMock
from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.ext.asyncio import AsyncSession
from app.v1_0.repositories import (
    BankRepository, 
    CustomerRepository, 
    SupplierRepository, 
    UserRepository, 
    RoleRepository, 
    StatusRepository
)
from app.v1_0.services import (
    BankService, 
    TransactionService, 
    CustomerService, 
    SupplierService, 
    SupabaseAdminService, 
    UserService, 
    StatusService
)
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
    """
    Stand-in for AsyncSession that reproduces its transaction rules.

    `begin()` used to be permissive here: calling it on a session that was
    already in a transaction quietly re-entered instead of failing. The real
    AsyncSession raises `InvalidRequestError("A transaction is already begun on
    this Session.")`, which is the error the expenses and customer endpoints
    returned in production while this suite stayed green. The double now raises
    the same way, so that class of bug fails a test instead of a request.
    """

    began: bool = False
    committed: bool = False
    rolled_back: bool = False
    _in_tx: bool = False

    def __init__(self) -> None:
        self.began = False
        self.committed = False
        self.rolled_back = False
        self._in_tx = False

    class _BeginContext:
        def __init__(self, outer: "FakeAsyncSession"):
            self.outer = outer
            # Raised at use, not at construction: `session.begin()` builds the
            # context manager and only the real AsyncSession's __aenter__ /
            # __await__ touches the transaction state.
            self.error = (
                InvalidRequestError("A transaction is already begun on this Session.")
                if outer._in_tx
                else None
            )

        def _start(self) -> None:
            if self.error is not None:
                raise self.error
            self.outer.began = True
            self.outer._in_tx = True

        def __await__(self):
            async def _inner():
                self._start()

            return _inner().__await__()

        async def __aenter__(self):
            self._start()
            return self.outer

        async def __aexit__(self, exc_type, exc, tb):
            if exc_type is not None:
                self.outer.rolled_back = True
            else:
                self.outer.committed = True
            self.outer._in_tx = False

    def begin(self):
        return FakeAsyncSession._BeginContext(self)

    async def commit(self):
        self.committed = True
        self._in_tx = False

    async def rollback(self):
        self.rolled_back = True
        self._in_tx = False

    def in_transaction(self) -> bool:
        return self._in_tx

    def autobegin(self) -> None:
        """Mark the session as mid-transaction, the way any statement would."""
        self._in_tx = True

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

@pytest.fixture
def customer_repository() -> AsyncMock:
    return AsyncMock(spec=CustomerRepository)

@pytest.fixture
def user_repository() -> AsyncMock:
    return AsyncMock(spec=UserRepository)


@pytest.fixture
def role_repository() -> AsyncMock:
    return AsyncMock(spec=RoleRepository)

@pytest.fixture
def supplier_repository() -> AsyncMock:
    return AsyncMock(spec=SupplierRepository)

@pytest.fixture
def supabase_admin() -> AsyncMock:
    return AsyncMock(spec=SupabaseAdminService)

@pytest.fixture
def status_repository() -> AsyncMock:
    repo = AsyncMock(spec=StatusRepository)
    repo.list_statuses = AsyncMock()
    return repo


@pytest.fixture
def status_service(status_repository: AsyncMock) -> StatusService:
    return StatusService(status_repository=status_repository)

@pytest.fixture
def transaction_service() -> AsyncMock:
    return AsyncMock(spec=TransactionService)

@pytest.fixture
def customer_service(
    customer_repository: AsyncMock,
    bank_repository: AsyncMock,
    transaction_service: AsyncMock,
) -> CustomerService:
    return CustomerService(
        customer_repository=customer_repository,
        bank_repository=bank_repository,
        transaction_service=transaction_service,
    )

@pytest.fixture
def user_service(
    user_repository: AsyncMock,
    role_repository: AsyncMock,
    supabase_admin: AsyncMock,
) -> UserService:
    return UserService(
        user_repository=user_repository,
        role_repository=role_repository,
        supabase_admin=supabase_admin,
    )

@pytest.fixture
def supplier_service(
    supplier_repository: AsyncMock,
) -> SupplierService:
    return SupplierService(
        supplier_repository=supplier_repository,
    )

def _wrap_factory(factory_fn):
    async def run_fake():
        return await factory_fn(None)  
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
