import pytest
from datetime import datetime
from decimal import Decimal
from fastapi import HTTPException
from unittest.mock import AsyncMock

from app.v1_0.schemas import TransactionCreate
from app.v1_0.entities import TransactionDTO, TransactionPageDTO, TransactionViewDTO
from app.v1_0.models import Transaction, TransactionType, Bank, Customer
from app.v1_0.tests.conftest import FakeAsyncSession
from app.v1_0.services import TransactionService
from app.v1_0.routers.transaction_router import (
    create_transaction,
    delete_transaction,
    list_transactions,
)

def make_tx_dto(
    id: int = 1,
    bank_id: int = 10,
    amount: float = 50.0,
    type_id: int = 1,
    description: str = "Manual",
    is_auto: bool = False,
) -> TransactionDTO:
    now = datetime.now()
    return TransactionDTO(
        id=id,
        bank_id=bank_id,
        amount=amount,
        type_id=type_id,
        description=description,
        is_auto=is_auto,
        created_at=now,
    )


def make_tx_view(
    id: int = 1,
    bank: str = "Banco X",
    amount: float = 50.0,
    type_str: str = "Ingreso",
    description: str | None = "Manual",
    is_auto: bool = False,
) -> TransactionViewDTO:
    now = datetime.now()
    return TransactionViewDTO(
        id=id,
        bank=bank,
        amount=amount,
        type_str=type_str,
        description=description,
        created_at=now,
        is_auto=is_auto,
    )

def make_type(id: int = 1, name: str = "Ingreso") -> TransactionType:
    return TransactionType(
        id=id,
        name=name,
    )

def make_bank(id: int = 10, balance: float = 500.0, name: str | None = None) -> Bank:
    return Bank(
        id=id,
        name=name or f"Bank {id}",
        account_number=f"ACC-{id}",
        balance=balance,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )

def make_customer(id: int = 1, name: str = "Juan", balance: float = 0.0) -> Customer:
    return Customer(
        id=id,
        tax_id="123",
        name=name,
        address="Dir",
        city="City",
        phone="3000000000",
        email="juan@test.com",
        balance=balance,
        created_at=datetime.now(),
    )

def make_tx(
    id: int = 1,
    bank_id: int = 10,
    type_id: int = 1,
    amount: float = 100.0,
    description: str | None = "Test tx",
    is_auto: bool = False,
) -> Transaction:
    return Transaction(
        id=id,
        bank_id=bank_id,
        type_id=type_id,
        amount=Decimal(str(amount)),
        description=description,
        is_auto=is_auto,
        created_at=datetime.now(),
    )

@pytest.fixture
def transaction_service(mocker):
    tx_repo = AsyncMock()
    type_repo = AsyncMock()
    bank_repo = AsyncMock()
    customer_repo = AsyncMock()

    service = TransactionService(
        transaction_repository=tx_repo,
        transaction_type_repository=type_repo,
        bank_repository=bank_repo,
        customer_repository=customer_repo,
    )
    return service


@pytest.mark.asyncio
async def test_create_transaction_ingreso_success(transaction_service, db_session):
    payload = TransactionCreate(
        bank_id=10,
        type_id=1,
        amount=100.0,
        description="Ingreso normal",
    )

    transaction_service.bank_repo.get_by_id.return_value = make_bank(10, 500)
    transaction_service.type_repo.get_by_id.return_value = make_type(1, "Ingreso")

    created_tx = make_tx(id=99, bank_id=10, amount=100.0)
    transaction_service.tx_repo.create_transaction.return_value = created_tx

    dto = await transaction_service.create(payload, db_session)

    assert dto.id == 99
    assert dto.bank_id == 10
    assert dto.amount == 100.0
    transaction_service.tx_repo.create_transaction.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_transaction_retiro_saldo_insuficiente(transaction_service, db_session):
    payload = TransactionCreate(
        bank_id=10,
        type_id=1,
        amount=1000.0,
        description="Retiro grande",
    )

    transaction_service.bank_repo.get_by_id.return_value = make_bank(10, 100)
    transaction_service.type_repo.get_by_id.return_value = make_type(1, "Retiro")

    with pytest.raises(HTTPException) as exc:
        await transaction_service.create(payload, db_session)

    assert exc.value.status_code == 400
    assert "Insufficient funds" in exc.value.detail


@pytest.mark.asyncio
async def test_create_transaction_type_not_found(transaction_service, db_session):
    payload = TransactionCreate(
        bank_id=10,
        type_id=999,
        amount=50,
        description="test",
    )

    transaction_service.bank_repo.get_by_id.return_value = make_bank()
    transaction_service.type_repo.get_by_id.return_value = None

    with pytest.raises(HTTPException) as exc:
        await transaction_service.create(payload, db_session)

    assert exc.value.status_code == 404
    assert "Transaction type not found." in exc.value.detail


@pytest.mark.asyncio
async def test_create_transaction_bank_not_found(transaction_service, db_session):
    payload = TransactionCreate(
        bank_id=1000,
        type_id=1,
        amount=10,
        description="test",
    )

    transaction_service.bank_repo.get_by_id.return_value = None

    with pytest.raises(HTTPException) as exc:
        await transaction_service.create(payload, db_session)

    assert exc.value.status_code == 404
    assert "Bank not found." in exc.value.detail


@pytest.mark.asyncio
async def test_delete_manual_transaction_not_found(transaction_service, db_session):
    transaction_service.tx_repo.get_by_id.return_value = None

    result = await transaction_service.delete_manual_transaction(10, db_session)

    assert result is False


@pytest.mark.asyncio
async def test_delete_manual_transaction_abono_saldo_success(transaction_service, db_session):
    tx = make_tx(id=5, description="Abono saldo Juan", amount=50)
    transaction_service.tx_repo.get_by_id.return_value = tx

    transaction_service.bank_repo.get_by_id.return_value = make_bank(balance=500)
    transaction_service.customer_repository.get_by_name.return_value = make_customer(id=3)

    transaction_service.tx_repo.delete.return_value = True

    result = await transaction_service.delete_manual_transaction(5, db_session)

    assert result is True
    transaction_service.bank_repo.decrease_balance.assert_awaited_once()
    transaction_service.customer_repository.increase_balance.assert_awaited_once()
    transaction_service.tx_repo.delete.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_manual_transaction_ingreso_success(transaction_service, db_session):
    tx = make_tx(id=5, type_id=1, description="Ingreso normal", amount=50)
    transaction_service.tx_repo.get_by_id.return_value = tx

    transaction_service.type_repo.get_by_id.return_value = make_type(1, "Ingreso")
    transaction_service.bank_repo.get_by_id.return_value = make_bank(10, balance=200)

    transaction_service.tx_repo.delete.return_value = True

    result = await transaction_service.delete_manual_transaction(5, db_session)

    assert result is True
    transaction_service.bank_repo.decrease_balance.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_manual_transaction_retiro_success(transaction_service, db_session):
    tx = make_tx(id=5, type_id=1, description="Retiro normal", amount=50)
    transaction_service.tx_repo.get_by_id.return_value = tx

    transaction_service.type_repo.get_by_id.return_value = make_type(1, "Retiro")
    transaction_service.bank_repo.get_by_id.return_value = make_bank(10, balance=200)

    transaction_service.tx_repo.delete.return_value = True

    result = await transaction_service.delete_manual_transaction(5, db_session)

    assert result is True
    transaction_service.bank_repo.increase_balance.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_manual_transaction_bank_not_found(transaction_service, db_session):
    tx = make_tx(id=5, type_id=1, description="Ingreso", amount=50)
    transaction_service.tx_repo.get_by_id.return_value = tx

    transaction_service.type_repo.get_by_id.return_value = make_type(1)
    transaction_service.bank_repo.get_by_id.return_value = None

    with pytest.raises(HTTPException) as exc:
        await transaction_service.delete_manual_transaction(5, db_session)

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_delete_manual_transaction_internal_error_returns_500(transaction_service, db_session):
    tx = make_tx(id=5)
    transaction_service.tx_repo.get_by_id.return_value = tx

    transaction_service.type_repo.get_by_id.side_effect = Exception("boom")

    with pytest.raises(HTTPException) as exc:
        await transaction_service.delete_manual_transaction(5, db_session)

    assert exc.value.status_code == 500
    assert "Failed to delete transaction" in exc.value.detail


@pytest.mark.asyncio
async def test_list_transactions_success(transaction_service, db_session):
    tx1 = make_tx(id=1, amount=10)
    tx1.bank = make_bank(id=10)
    tx1.type = make_type(name="Ingreso")

    tx2 = make_tx(id=2, amount=20)
    tx2.bank = make_bank(id=99)
    tx2.type = make_type(name="Retiro")

    transaction_service.tx_repo.list_paginated.return_value = (
        [tx1, tx2],
        20,
    )

    result = await transaction_service.list_transactions(1, db_session)

    assert len(result.items) == 2
    assert result.total == 20
    assert result.page_size == 8
    assert result.page == 1

    assert result.items[0].id == 1
    assert result.items[1].id == 2

@pytest.mark.asyncio
async def test_router_create_transaction_returns_dto(
    db_session: FakeAsyncSession,
    mocker,
    fake_auth_ctx,
):
    payload = TransactionCreate(
        bank_id=10,
        amount=50.0,
        type_id=1,
        description="Manual",
        is_auto=False,
    )
    dto = make_tx_dto(id=123, bank_id=10, amount=50.0)

    mock_service = mocker.Mock()
    mock_service.create = AsyncMock(return_value=dto)

    mocker.patch(
        "app.v1_0.routers.transaction_router.build_channel_id_from_auth",
        return_value="chan-1",
    )

    result = await create_transaction(
        payload=payload,
        db=db_session,
        auth_ctx=fake_auth_ctx,
        service=mock_service,
    )

    mock_service.create.assert_awaited_once_with(
        payload=payload,
        db=db_session,
        channel_id="chan-1",
    )

    assert isinstance(result, TransactionDTO)
    assert result.id == 123
    assert result.bank_id == 10


@pytest.mark.asyncio
async def test_router_create_transaction_http_error_propagates(
    db_session: FakeAsyncSession,
    mocker,
    fake_auth_ctx,
):
    payload = TransactionCreate(
        bank_id=10,
        amount=50.0,
        type_id=1,
        description="Manual",
        is_auto=False,
    )

    mock_service = mocker.Mock()
    mock_service.create = AsyncMock(
        side_effect=HTTPException(status_code=400, detail="Bad tx")
    )

    mocker.patch(
        "app.v1_0.routers.transaction_router.build_channel_id_from_auth",
        return_value="chan-1",
    )

    with pytest.raises(HTTPException) as exc:
        await create_transaction(
            payload=payload,
            db=db_session,
            auth_ctx=fake_auth_ctx,
            service=mock_service,
        )

    assert exc.value.status_code == 400
    assert exc.value.detail == "Bad tx"


@pytest.mark.asyncio
async def test_router_create_transaction_generic_error_returns_500(
    db_session: FakeAsyncSession,
    mocker,
    fake_auth_ctx,
):
    payload = TransactionCreate(
        bank_id=10,
        amount=50.0,
        type_id=1,
        description="Manual",
        is_auto=False,
    )

    mock_service = mocker.Mock()
    mock_service.create = AsyncMock(side_effect=RuntimeError("boom"))

    mocker.patch(
        "app.v1_0.routers.transaction_router.build_channel_id_from_auth",
        return_value="chan-1",
    )

    with pytest.raises(HTTPException) as exc:
        await create_transaction(
            payload=payload,
            db=db_session,
            auth_ctx=fake_auth_ctx,
            service=mock_service,
        )

    assert exc.value.status_code == 500
    assert exc.value.detail == "Failed to create transaction"


@pytest.mark.asyncio
async def test_router_delete_transaction_success_returns_message(
    db_session: FakeAsyncSession,
    mocker,
    fake_auth_ctx,
):
    mock_service = mocker.Mock()
    mock_service.delete_manual_transaction = AsyncMock(return_value=True)

    mocker.patch(
        "app.v1_0.routers.transaction_router.build_channel_id_from_auth",
        return_value="chan-del",
    )

    result = await delete_transaction(
        transaction_id=5,
        db=db_session,
        auth_ctx=fake_auth_ctx,
        service=mock_service,
    )

    mock_service.delete_manual_transaction.assert_awaited_once_with(
        transaction_id=5,
        db=db_session,
        channel_id="chan-del",
    )

    assert result == {"message": "Transaction 5 deleted successfully"}


@pytest.mark.asyncio
async def test_router_delete_transaction_not_found_returns_404(
    db_session: FakeAsyncSession,
    mocker,
    fake_auth_ctx,
):
    mock_service = mocker.Mock()
    mock_service.delete_manual_transaction = AsyncMock(return_value=False)

    mocker.patch(
        "app.v1_0.routers.transaction_router.build_channel_id_from_auth",
        return_value="chan-del",
    )

    with pytest.raises(HTTPException) as exc:
        await delete_transaction(
            transaction_id=99,
            db=db_session,
            auth_ctx=fake_auth_ctx,
            service=mock_service,
        )

    assert exc.value.status_code == 404
    assert exc.value.detail == "Transaction not found"


@pytest.mark.asyncio
async def test_router_delete_transaction_http_error_propagates(
    db_session: FakeAsyncSession,
    mocker,
    fake_auth_ctx,
):
    mock_service = mocker.Mock()
    mock_service.delete_manual_transaction = AsyncMock(
        side_effect=HTTPException(status_code=400, detail="bad delete")
    )

    mocker.patch(
        "app.v1_0.routers.transaction_router.build_channel_id_from_auth",
        return_value="chan-del",
    )

    with pytest.raises(HTTPException) as exc:
        await delete_transaction(
            transaction_id=5,
            db=db_session,
            auth_ctx=fake_auth_ctx,
            service=mock_service,
        )

    assert exc.value.status_code == 400
    assert exc.value.detail == "bad delete"


@pytest.mark.asyncio
async def test_router_delete_transaction_generic_error_returns_500(
    db_session: FakeAsyncSession,
    mocker,
    fake_auth_ctx,
):
    mock_service = mocker.Mock()
    mock_service.delete_manual_transaction = AsyncMock(
        side_effect=RuntimeError("boom")
    )

    mocker.patch(
        "app.v1_0.routers.transaction_router.build_channel_id_from_auth",
        return_value="chan-del",
    )

    with pytest.raises(HTTPException) as exc:
        await delete_transaction(
            transaction_id=5,
            db=db_session,
            auth_ctx=fake_auth_ctx,
            service=mock_service,
        )

    assert exc.value.status_code == 500
    assert exc.value.detail == "Failed to delete transaction"



@pytest.mark.asyncio
async def test_router_list_transactions_success(
    db_session: FakeAsyncSession,
    mocker,
):
    view = make_tx_view(id=1, bank="Bank 10", amount=50.0, type_str="Ingreso")
    page_dto = TransactionPageDTO(
        items=[view],
        page=2,
        page_size=8,
        total=20,
        total_pages=3,
        has_next=True,
        has_prev=True,
    )

    mock_service = mocker.Mock()
    mock_service.list_transactions = AsyncMock(return_value=page_dto)

    result = await list_transactions(
        page=2,
        db=db_session,
        service=mock_service,
    )

    mock_service.list_transactions.assert_awaited_once_with(2, db_session)

    assert result.page == 2
    assert len(result.items) == 1
    assert result.items[0].bank == "Bank 10"


@pytest.mark.asyncio
async def test_router_list_transactions_http_error_propagates(
    db_session: FakeAsyncSession,
    mocker,
):
    mock_service = mocker.Mock()
    mock_service.list_transactions = AsyncMock(
        side_effect=HTTPException(status_code=400, detail="bad page")
    )

    with pytest.raises(HTTPException) as exc:
        await list_transactions(
            page=1,
            db=db_session,
            service=mock_service,
        )

    assert exc.value.status_code == 400
    assert exc.value.detail == "bad page"