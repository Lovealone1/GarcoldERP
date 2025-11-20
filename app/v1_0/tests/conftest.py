import asyncio
from typing import AsyncGenerator

import pytest
from httpx import AsyncClient, ASGITransport
from asgi_lifespan import LifespanManager

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.v1_0.models import Base
from app.main import app
from app.storage.database import get_db

from tests.factories import (
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
    seed_company
    )

DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine_test = create_async_engine(
    DATABASE_URL,
    future=True,
    echo=False,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,  
)

AsyncSessionLocal = async_sessionmaker(
    engine_test,
    expire_on_commit=False,
    class_=AsyncSession,
)

@pytest.fixture
async def seed_banks_fixture(db_session):
    async def run():
        return await seed_banks(db_session)

    return run

@pytest.fixture
async def seed_customers_fixture(db_session):
    async def run():
        return await seed_customers(db_session)

    return run

@pytest.fixture
async def seed_expense_categories_fixture(db_session):

    async def run():
        return await seed_expense_categories(db_session)

    return run

@pytest.fixture
async def seed_expenses_fixture(db_session):

    async def run():
        return await seed_expenses(db_session)

    return run

@pytest.fixture
async def seed_investments_fixture(db_session):

    async def run():
        return await seed_investments(db_session)

    return run

@pytest.fixture
async def seed_loans_fixture(db_session):

    async def run():
        return await seed_loans(db_session)

    return run

@pytest.fixture
async def seed_products_fixture(db_session):

    async def run():
        return await seed_products(db_session)

    return run

@pytest.fixture
async def seed_suppliers_fixture(db_session):

    async def run():
        return await seed_suppliers(db_session)

    return run

@pytest.fixture
async def seed_transaction_types_fixture(db_session):

    async def run():
        return await seed_transaction_types(db_session)

    return run

@pytest.fixture
async def seed_roles_fixture(db_session):

    async def run():
        return await seed_roles(db_session)

    return run

@pytest.fixture
async def seed_users_fixture(db_session):

    async def run():
        return await seed_users(db_session)

    return run

@pytest.fixture
async def seed_statuses_fixture(db_session):

    async def run():
        return await seed_statuses(db_session)

    return run

@pytest.fixture
async def seed_permissions_fixture(db_session):

    async def run():
        return await seed_permissions(db_session)

    return run

@pytest.fixture
async def seed_company_fixture(db_session):

    async def run():
        return await seed_company(db_session)

    return run

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
async def prepare_database():
    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.rollback()


def _get_test_db_session():
    async def _override() -> AsyncGenerator[AsyncSession, None]:
        async with AsyncSessionLocal() as session:
            try:
                yield session
            finally:
                await session.rollback()

    return _override


@pytest.fixture(scope="session", autouse=True)
def override_db_dependency():
    app.dependency_overrides[get_db] = _get_test_db_session()
    yield
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as ac:
            yield ac
