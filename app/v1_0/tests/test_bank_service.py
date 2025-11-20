import pytest
from datetime import datetime
from fastapi import HTTPException

from app.v1_0.schemas import BankCreate
from app.v1_0.models import Bank
from app.v1_0.services.bank_service import BankService
from app.v1_0.tests.conftest import FakeAsyncSession


@pytest.mark.asyncio
async def test_create_bank(
    db_session: FakeAsyncSession,
    bank_service: BankService,
    bank_repository,
):
    payload = BankCreate(
        name="Banco Test",
        account_number="999-001",
        balance=0.0,
    )

    now = datetime.now()
    bank_repository.create_bank.return_value = Bank(
        id=10,
        name="Banco Test",
        account_number="999-001",
        balance=0.0,
        created_at=now,
        updated_at=now,
    )

    dto = await bank_service.create_bank(payload, db_session)

    bank_repository.create_bank.assert_awaited_once_with(payload, session=db_session)

    assert dto.id == 10
    assert dto.name == "Banco Test"
    assert dto.account_number == "999-001"
    assert dto.balance == 0.0
    assert db_session.committed is True
    assert db_session.rolled_back is False


@pytest.mark.asyncio
async def test_create_bank_with_realtime_event(
    db_session: FakeAsyncSession,
    bank_service: BankService,
    bank_repository,
    mocker,
):
    payload = BankCreate(
        name="Banco RT",
        account_number="999-RT",
        balance=0.0,
    )

    now = datetime.now()
    bank_repository.create_bank.return_value = Bank(
        id=20,
        name="Banco RT",
        account_number="999-RT",
        balance=0.0,
        created_at=now,
        updated_at=now,
    )

    mock_rt = mocker.patch(
        "app.v1_0.services.bank_service.publish_realtime_event",
        autospec=True,
    )

    dto = await bank_service.create_bank(payload, db_session, channel_id="user:1")

    assert dto.id == 20

    mock_rt.assert_awaited_once()
    _, kwargs = mock_rt.await_args
    assert kwargs["channel_id"] == "user:1"
    assert kwargs["resource"] == "bank"
    assert kwargs["action"] == "created"
    assert kwargs["payload"]["id"] == dto.id


@pytest.mark.asyncio
async def test_get_bank_by_id_found(
    db_session: FakeAsyncSession,
    bank_service: BankService,
    bank_repository,
):
    now = datetime.now()
    bank_repository.get_by_id.return_value = Bank(
        id=1,
        name="Banco Uno",
        account_number="ACC-1",
        balance=100.0,
        created_at=now,
        updated_at=now,
    )

    dto = await bank_service.get_bank_by_id(1, db_session)

    bank_repository.get_by_id.assert_awaited_once_with(1, session=db_session)
    assert dto is not None
    assert dto.id == 1
    assert dto.name == "Banco Uno"
    assert dto.balance == 100.0


@pytest.mark.asyncio
async def test_get_bank_by_id_not_found_returns_none(
    db_session: FakeAsyncSession,
    bank_service: BankService,
    bank_repository,
):
    bank_repository.get_by_id.return_value = None

    dto = await bank_service.get_bank_by_id(999, db_session)

    bank_repository.get_by_id.assert_awaited_once_with(999, session=db_session)
    assert dto is None


@pytest.mark.asyncio
async def test_get_bank_by_id_error_raises_500(
    db_session: FakeAsyncSession,
    bank_service: BankService,
    bank_repository,
):
    bank_repository.get_by_id.side_effect = RuntimeError("db down")

    with pytest.raises(HTTPException) as exc:
        await bank_service.get_bank_by_id(1, db_session)

    assert exc.value.status_code == 500
    assert "Failed to fetch bank" in exc.value.detail


@pytest.mark.asyncio
async def test_get_all_banks_returns_dtos(
    db_session: FakeAsyncSession,
    bank_service: BankService,
    bank_repository,
):
    now = datetime.now()
    bank_repository.list_all.return_value = [
        Bank(id=1, name="Bank A", account_number="A-1", balance=10.0, created_at=now, updated_at=now),
        Bank(id=2, name="Bank B", account_number="B-2", balance=20.0, created_at=now, updated_at=now),
    ]

    result = await bank_service.get_all_banks(db_session)

    bank_repository.list_all.assert_awaited_once_with(session=db_session)
    assert len(result) == 2
    assert {b.name for b in result} == {"Bank A", "Bank B"}


@pytest.mark.asyncio
async def test_get_all_banks_error_raises_500(
    db_session: FakeAsyncSession,
    bank_service: BankService,
    bank_repository,
):
    bank_repository.list_all.side_effect = RuntimeError("db down")

    with pytest.raises(HTTPException) as exc:
        await bank_service.get_all_banks(db_session)

    assert exc.value.status_code == 500
    assert "Failed to list banks" in exc.value.detail


@pytest.mark.asyncio
async def test_update_balance_success(
    db_session: FakeAsyncSession,
    bank_service: BankService,
    bank_repository,
):
    now = datetime.now()
    bank_repository.update_balance.return_value = Bank(
        id=1,
        name="Bank",
        account_number="ACC",
        balance=250.0,
        created_at=now,
        updated_at=now,
    )

    dto = await bank_service.update_balance(1, 250.0, db_session)

    bank_repository.update_balance.assert_awaited_once_with(1, 250.0, session=db_session)
    assert dto.balance == 250.0
    assert db_session.committed is True
    assert db_session.rolled_back is False


@pytest.mark.asyncio
async def test_update_balance_not_found_raises_404(
    db_session: FakeAsyncSession,
    bank_service: BankService,
    bank_repository,
):
    bank_repository.update_balance.return_value = None

    with pytest.raises(HTTPException) as exc:
        await bank_service.update_balance(1, 100.0, db_session)

    assert exc.value.status_code == 404
    assert "Bank not found" in exc.value.detail
    assert db_session.rolled_back is True


@pytest.mark.asyncio
async def test_update_balance_error_raises_500(
    db_session: FakeAsyncSession,
    bank_service: BankService,
    bank_repository,
):
    bank_repository.update_balance.side_effect = RuntimeError("boom")

    with pytest.raises(HTTPException) as exc:
        await bank_service.update_balance(1, 100.0, db_session)

    assert exc.value.status_code == 500
    assert "Failed to update balance" in exc.value.detail
    assert db_session.rolled_back is True


@pytest.mark.asyncio
async def test_update_balance_with_realtime_event(
    db_session: FakeAsyncSession,
    bank_service: BankService,
    bank_repository,
    mocker,
):
    now = datetime.now()
    bank_repository.update_balance.return_value = Bank(
        id=1,
        name="Bank",
        account_number="ACC",
        balance=300.0,
        created_at=now,
        updated_at=now,
    )

    mock_rt = mocker.patch(
        "app.v1_0.services.bank_service.publish_realtime_event",
        autospec=True,
    )

    dto = await bank_service.update_balance(1, 300.0, db_session, channel_id="user:2")

    assert dto.balance == 300.0

    mock_rt.assert_awaited_once()
    _, kwargs = mock_rt.await_args
    assert kwargs["channel_id"] == "user:2"
    assert kwargs["resource"] == "bank"
    assert kwargs["action"] == "updated"
    assert kwargs["payload"]["id"] == dto.id


@pytest.mark.asyncio
async def test_delete_bank_success_zero_balance(
    db_session: FakeAsyncSession,
    bank_service: BankService,
    bank_repository,
):
    now = datetime.now()
    bank_repository.get_by_id.return_value = Bank(
        id=1,
        name="Bank",
        account_number="ACC",
        balance=0.0,
        created_at=now,
        updated_at=now,
    )
    bank_repository.delete_bank.return_value = True

    result = await bank_service.delete_bank(1, db_session)

    bank_repository.get_by_id.assert_awaited_once_with(1, session=db_session)
    bank_repository.delete_bank.assert_awaited_once_with(1, session=db_session)
    assert result is True
    assert db_session.committed is True


@pytest.mark.asyncio
async def test_delete_bank_not_found_returns_false(
    db_session: FakeAsyncSession,
    bank_service: BankService,
    bank_repository,
):
    bank_repository.get_by_id.return_value = None

    result = await bank_service.delete_bank(999, db_session)

    bank_repository.get_by_id.assert_awaited_once_with(999, session=db_session)
    assert result is False
    assert db_session.committed is True  


@pytest.mark.asyncio
async def test_delete_bank_positive_balance_raises_400(
    db_session: FakeAsyncSession,
    bank_service: BankService,
    bank_repository,
):
    now = datetime.now()
    bank_repository.get_by_id.return_value = Bank(
        id=1,
        name="Bank",
        account_number="ACC",
        balance=50.0,
        created_at=now,
        updated_at=now,
    )

    with pytest.raises(HTTPException) as exc:
        await bank_service.delete_bank(1, db_session)

    assert exc.value.status_code == 400
    assert "Cannot delete a bank with balance greater than 0" in exc.value.detail
    assert db_session.rolled_back is True
    bank_repository.delete_bank.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_bank_error_raises_500(
    db_session: FakeAsyncSession,
    bank_service: BankService,
    bank_repository,
):
    now = datetime.now()
    bank_repository.get_by_id.return_value = Bank(
        id=1,
        name="Bank",
        account_number="ACC",
        balance=0.0,
        created_at=now,
        updated_at=now,
    )
    bank_repository.delete_bank.side_effect = RuntimeError("boom")

    with pytest.raises(HTTPException) as exc:
        await bank_service.delete_bank(1, db_session)

    assert exc.value.status_code == 500
    assert "Failed to delete bank" in exc.value.detail
    assert db_session.rolled_back is True


@pytest.mark.asyncio
async def test_delete_bank_with_realtime_event(
    db_session: FakeAsyncSession,
    bank_service: BankService,
    bank_repository,
    mocker,
):
    now = datetime.now()
    bank_repository.get_by_id.return_value = Bank(
        id=1,
        name="Bank",
        account_number="ACC",
        balance=0.0,
        created_at=now,
        updated_at=now,
    )
    bank_repository.delete_bank.return_value = True

    mock_rt = mocker.patch(
        "app.v1_0.services.bank_service.publish_realtime_event",
        autospec=True,
    )

    result = await bank_service.delete_bank(1, db_session, channel_id="user:3")

    assert result is True

    mock_rt.assert_awaited_once()
    _, kwargs = mock_rt.await_args
    assert kwargs["channel_id"] == "user:3"
    assert kwargs["resource"] == "bank"
    assert kwargs["action"] == "deleted"
    assert kwargs["payload"]["id"] == 1


@pytest.mark.asyncio
async def test_decrease_balance_invalid_amount_raises_400(
    db_session: FakeAsyncSession,
    bank_service: BankService,
    bank_repository,
):
    with pytest.raises(HTTPException) as exc:
        await bank_service.decrease_balance(1, 0.0, db_session)

    assert exc.value.status_code == 400
    assert "Amount must be greater than zero" in exc.value.detail
    bank_repository.get_by_id.assert_not_awaited()


@pytest.mark.asyncio
async def test_decrease_balance_bank_not_found_raises_404(
    db_session: FakeAsyncSession,
    bank_service: BankService,
    bank_repository,
):
    bank_repository.get_by_id.return_value = None

    with pytest.raises(HTTPException) as exc:
        await bank_service.decrease_balance(1, 50.0, db_session)

    assert exc.value.status_code == 404
    assert "Bank not found" in exc.value.detail
    assert db_session.rolled_back is True


@pytest.mark.asyncio
async def test_decrease_balance_insufficient_balance_raises_400(
    db_session: FakeAsyncSession,
    bank_service: BankService,
    bank_repository,
):
    now = datetime.now()
    bank_repository.get_by_id.return_value = Bank(
        id=1,
        name="Bank",
        account_number="ACC",
        balance=30.0,
        created_at=now,
        updated_at=now,
    )

    with pytest.raises(HTTPException) as exc:
        await bank_service.decrease_balance(1, 50.0, db_session)

    assert exc.value.status_code == 400
    assert "Insufficient balance" in exc.value.detail
    assert db_session.rolled_back is True


@pytest.mark.asyncio
async def test_decrease_balance_success(
    db_session: FakeAsyncSession,
    bank_service: BankService,
    bank_repository,
):
    now = datetime.now()
    bank_repository.get_by_id.return_value = Bank(
        id=1,
        name="Bank",
        account_number="ACC",
        balance=100.0,
        created_at=now,
        updated_at=now,
    )
    bank_repository.decrease_balance.return_value = Bank(
        id=1,
        name="Bank",
        account_number="ACC",
        balance=60.0,
        created_at=now,
        updated_at=now,
    )

    dto = await bank_service.decrease_balance(1, 40.0, db_session)

    bank_repository.get_by_id.assert_awaited_once_with(1, session=db_session)
    bank_repository.decrease_balance.assert_awaited_once_with(1, 40.0, session=db_session)
    assert dto.balance == 60.0
    assert db_session.committed is True


@pytest.mark.asyncio
async def test_decrease_balance_error_raises_500(
    db_session: FakeAsyncSession,
    bank_service: BankService,
    bank_repository,
):
    bank_repository.get_by_id.side_effect = RuntimeError("boom")

    with pytest.raises(HTTPException) as exc:
        await bank_service.decrease_balance(1, 10.0, db_session)

    assert exc.value.status_code == 500
    assert "Failed to decrease balance" in exc.value.detail
    assert db_session.rolled_back is True


@pytest.mark.asyncio
async def test_increase_balance_invalid_amount_raises_400(
    db_session: FakeAsyncSession,
    bank_service: BankService,
    bank_repository,
):
    with pytest.raises(HTTPException) as exc:
        await bank_service.increase_balance(1, 0.0, db_session)

    assert exc.value.status_code == 400
    assert "Amount must be greater than zero" in exc.value.detail
    bank_repository.get_by_id.assert_not_awaited()


@pytest.mark.asyncio
async def test_increase_balance_bank_not_found_raises_404(
    db_session: FakeAsyncSession,
    bank_service: BankService,
    bank_repository,
):
    bank_repository.get_by_id.return_value = None

    with pytest.raises(HTTPException) as exc:
        await bank_service.increase_balance(1, 50.0, db_session)

    assert exc.value.status_code == 404
    assert "Bank not found" in exc.value.detail
    assert db_session.rolled_back is True


@pytest.mark.asyncio
async def test_increase_balance_success(
    db_session: FakeAsyncSession,
    bank_service: BankService,
    bank_repository,
):
    now = datetime.now()
    bank_repository.get_by_id.return_value = Bank(
        id=1,
        name="Bank",
        account_number="ACC",
        balance=100.0,
        created_at=now,
        updated_at=now,
    )
    bank_repository.increase_balance.return_value = Bank(
        id=1,
        name="Bank",
        account_number="ACC",
        balance=150.0,
        created_at=now,
        updated_at=now,
    )

    dto = await bank_service.increase_balance(1, 50.0, db_session)

    bank_repository.get_by_id.assert_awaited_once_with(1, session=db_session)
    bank_repository.increase_balance.assert_awaited_once_with(1, 50.0, session=db_session)
    assert dto.balance == 150.0
    assert db_session.committed is True


@pytest.mark.asyncio
async def test_increase_balance_error_raises_500(
    db_session: FakeAsyncSession,
    bank_service: BankService,
    bank_repository,
):
    bank_repository.get_by_id.side_effect = RuntimeError("boom")

    with pytest.raises(HTTPException) as exc:
        await bank_service.increase_balance(1, 10.0, db_session)

    assert exc.value.status_code == 500
    assert "Failed to increase balance" in exc.value.detail
    assert db_session.rolled_back is True
