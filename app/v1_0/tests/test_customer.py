import pytest
from fastapi import HTTPException
from datetime import datetime

from unittest.mock import AsyncMock
from app.v1_0.services.customer_service import CustomerService
from app.v1_0.schemas import CustomerCreate, CustomerUpdate, StandalonePaymentIn
from app.v1_0.models import Customer
from app.v1_0.entities import CustomerDTO, CustomerPageDTO
from app.v1_0.tests.conftest import FakeAsyncSession

from app.v1_0.routers.customer_router import (
    create_customer,
    get_customer,
    list_customers,
    list_customers_paginated,
    update_customer,
    update_customer_balance,
    delete_customer,
    create_simple_payment,
)

def make_customer(
    id=1,
    tax_id="123",
    name="John Doe",
    address="Street",
    city="City",
    phone="3000000000",
    email="john@example.com",
    balance=0.0,
):
    now = datetime.now()
    return Customer(
        id=id,
        tax_id=tax_id,
        name=name,
        address=address,
        city=city,
        phone=phone,
        email=email,
        created_at=now,
        balance=balance,
    )


@pytest.mark.asyncio
async def test_customer_create_success(
    db_session: FakeAsyncSession,
    customer_service: CustomerService,
    customer_repository,
    mocker
):
    payload = CustomerCreate(
        tax_id="111",
        name="Cliente Nuevo",
        address="Dir",
        city="Med",
        phone="300",
        email="x@test.com",
        balance=0
    )

    c = make_customer(id=10, name="Cliente Nuevo")
    customer_repository.create_customer.return_value = c

    mock_rt = mocker.patch(
        "app.v1_0.services.customer_service.publish_realtime_event",
        autospec=True
    )

    dto = await customer_service.create(payload, db_session, channel_id="user:1")

    assert dto.id == 10
    assert dto.name == "Cliente Nuevo"

    customer_repository.create_customer.assert_awaited_once()
    mock_rt.assert_awaited()


@pytest.mark.asyncio
async def test_customer_create_error(db_session, customer_service, customer_repository):
    payload = CustomerCreate(
        tax_id="111",
        name="X",
        address="Dir",
        city="Med",
        phone="300",
        email="test@test.com",
        balance=0
    )

    customer_repository.create_customer.side_effect = Exception("DB error")

    with pytest.raises(HTTPException) as exc:
        await customer_service.create(payload, db_session)

    assert exc.value.status_code == 500


@pytest.mark.asyncio
async def test_customer_get_success(db_session, customer_service, customer_repository):
    c = make_customer(id=33, name="Cliente X")
    customer_repository.get_customer_by_id.return_value = c

    dto = await customer_service.get(33, db_session)
    assert dto.id == 33
    assert dto.name == "Cliente X"


@pytest.mark.asyncio
async def test_customer_get_not_found(db_session, customer_service, customer_repository):
    customer_repository.get_customer_by_id.return_value = None

    with pytest.raises(HTTPException) as exc:
        await customer_service.get(99, db_session)

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_customer_list_all(db_session, customer_service, customer_repository):
    customer_repository.list_all.return_value = [
        make_customer(id=1, name="A"),
        make_customer(id=2, name="B"),
    ]

    lst = await customer_service.list_all(db_session)
    assert len(lst) == 2
    assert lst[0].name == "A"
    assert lst[1].name == "B"


@pytest.mark.asyncio
async def test_customer_list_paginated(db_session, customer_service, customer_repository):
    customer_repository.list_paginated.return_value = (
        [make_customer(id=1), make_customer(id=2)],
        10, 
        None,
    )

    page = await customer_service.list_paginated(1, db_session)

    assert page.page == 1
    assert page.total == 10
    assert len(page.items) == 2
    assert page.total_pages == 2


@pytest.mark.asyncio
async def test_customer_update_partial_success(
    db_session, customer_service, customer_repository, mocker
):
    updated = make_customer(id=10, name="Nuevo Nombre")
    customer_repository.update_customer.return_value = updated

    mock_rt = mocker.patch(
        "app.v1_0.services.customer_service.publish_realtime_event",
        autospec=True,
    )

    payload = CustomerUpdate(
        name="Nuevo Nombre",
        tax_id=None,
        email=None,
        phone=None,
        address=None,
        city=None,
    )

    dto = await customer_service.update_partial(
        10,
        payload,
        db_session,
        channel_id="user:1",
    )

    assert dto.id == 10
    assert dto.name == "Nuevo Nombre"
    mock_rt.assert_awaited()


@pytest.mark.asyncio
async def test_customer_update_partial_not_found(
    db_session, customer_service, customer_repository
):
    customer_repository.update_customer.return_value = None

    payload = CustomerUpdate(
        name="X",
        tax_id=None,
        email=None,
        phone=None,
        address=None,
        city=None,
    )

    with pytest.raises(HTTPException) as exc:
        await customer_service.update_partial(
            55,
            payload,
            db_session,
        )

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_customer_update_balance_success(
    db_session, customer_service, customer_repository
):
    updated = make_customer(id=20, balance=500)
    customer_repository.update_balance.return_value = updated

    dto = await customer_service.update_balance(
        20,
        500,
        db_session
    )

    assert dto.balance == 500


@pytest.mark.asyncio
async def test_customer_update_balance_not_found(
    db_session, customer_service, customer_repository
):
    customer_repository.update_balance.return_value = None

    with pytest.raises(HTTPException):
        await customer_service.update_balance(99, 100, db_session)


@pytest.mark.asyncio
async def test_customer_delete_success(
    db_session, customer_service, customer_repository, mocker
):
    customer_repository.delete_customer.return_value = True

    mock_rt = mocker.patch(
        "app.v1_0.services.customer_service.publish_realtime_event",
        autospec=True
    )

    ok = await customer_service.delete(1, db_session, channel_id="user:1")
    assert ok is True
    mock_rt.assert_awaited()


@pytest.mark.asyncio
async def test_customer_delete_not_found(
    db_session, customer_service, customer_repository
):
    customer_repository.delete_customer.return_value = False

    with pytest.raises(HTTPException) as exc:
        await customer_service.delete(22, db_session)

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_customer_register_payment_success(
    db_session,
    customer_service,
    customer_repository,
    bank_repository,
    transaction_service,
    mocker,
):
    customer_repository.get_by_id.return_value = make_customer(id=1, balance=100)
    bank_repository.get_by_id.return_value = make_customer(id=2, balance=50)

    customer_repository.update_balance.return_value = True
    bank_repository.update_balance.return_value = True
    transaction_service.insert_transaction.return_value = True

    mock_rt = mocker.patch(
        "app.v1_0.services.customer_service.publish_realtime_event",
        autospec=True
    )

    ok = await customer_service.register_simple_balance_payment(
        customer_id=1,
        bank_id=2,
        amount=50,
        description="Pago",
        db=db_session,
        channel_id="x",
    )

    assert ok is True
    mock_rt.assert_awaited()


@pytest.mark.asyncio
async def test_customer_register_payment_exceeds_balance(
    db_session, customer_service, customer_repository, bank_repository
):
    customer_repository.get_by_id.return_value = make_customer(id=1, balance=20)
    bank_repository.get_by_id.return_value = make_customer(id=2, balance=50)

    with pytest.raises(HTTPException) as exc:
        await customer_service.register_simple_balance_payment(
            customer_id=1,
            bank_id=2,
            amount=100,
            description="Pago",
            db=db_session,
        )

    assert exc.value.status_code == 422


def make_customer_dto(
    id: int = 1,
    tax_id: str | None = "123",
    name: str = "John Doe",
    address: str | None = "Street 1",
    city: str | None = "City",
    phone: str | None = "3000000000",
    email: str | None = "test@example.com",
    balance: float = 0.0,
) -> CustomerDTO:
    now = datetime.now()
    return CustomerDTO(
        id=id,
        tax_id=tax_id,
        name=name,
        address=address,
        city=city,
        phone=phone,
        email=email,
        created_at=now,
        balance=balance,
    )


@pytest.mark.asyncio
async def test_router_create_customer_returns_dto(
    db_session: FakeAsyncSession,
    mocker,
    fake_auth_ctx,
):
    payload = CustomerCreate(
        tax_id="111",
        name="Cliente Router",
        address="Dir",
        city="Med",
        phone="3000000",
        email="router@example.com",
        balance=0.0,
    )

    dto = make_customer_dto(id=10, name="Cliente Router")

    mock_service = mocker.Mock()
    mock_service.create = AsyncMock(return_value=dto)

    mocker.patch(
        "app.v1_0.routers.customer_router.build_channel_id_from_auth",
        return_value="chan-1",
    )

    result = await create_customer(
        request=payload,
        db=db_session,
        auth_ctx=fake_auth_ctx,
        service=mock_service,
    )

    mock_service.create.assert_awaited_once_with(
        payload=payload,
        db=db_session,
        channel_id="chan-1",
    )

    assert isinstance(result, CustomerDTO)
    assert result.id == 10
    assert result.name == "Cliente Router"


@pytest.mark.asyncio
async def test_router_create_customer_generic_error_returns_500(
    db_session: FakeAsyncSession,
    mocker,
    fake_auth_ctx,
):
    payload = CustomerCreate(
        tax_id="111",
        name="X",
        address="Dir",
        city="Med",
        phone="3000000",
        email="x@example.com",
        balance=0.0,
    )

    mock_service = mocker.Mock()
    mock_service.create = AsyncMock(side_effect=RuntimeError("boom"))

    mocker.patch(
        "app.v1_0.routers.customer_router.build_channel_id_from_auth",
        return_value="chan-err",
    )

    with pytest.raises(HTTPException) as exc:
        await create_customer(
            request=payload,
            db=db_session,
            auth_ctx=fake_auth_ctx,
            service=mock_service,
        )

    assert exc.value.status_code == 500
    assert exc.value.detail == "Failed to create customer"


@pytest.mark.asyncio
async def test_router_create_customer_http_exception_passthrough(
    db_session: FakeAsyncSession,
    mocker,
    fake_auth_ctx,
):
    payload = CustomerCreate(
        tax_id="111",
        name="X",
        address="Dir",
        city="Med",
        phone="3000000",
        email="x@example.com",
        balance=0.0,
    )

    mock_service = mocker.Mock()
    mock_service.create = AsyncMock(
        side_effect=HTTPException(status_code=400, detail="Bad customer")
    )

    mocker.patch(
        "app.v1_0.routers.customer_router.build_channel_id_from_auth",
        return_value="chan-err",
    )

    with pytest.raises(HTTPException) as exc:
        await create_customer(
            request=payload,
            db=db_session,
            auth_ctx=fake_auth_ctx,
            service=mock_service,
        )

    assert exc.value.status_code == 400
    assert exc.value.detail == "Bad customer"


@pytest.mark.asyncio
async def test_router_get_customer_success(
    db_session: FakeAsyncSession,
    mocker,
):
    mock_service = mocker.Mock()
    mock_service.get = AsyncMock(
        return_value=make_customer_dto(id=33, name="Cliente X")
    )

    result = await get_customer(
        customer_id=33,
        db=db_session,
        service=mock_service,
    )

    mock_service.get.assert_awaited_once_with(33, db_session)
    assert isinstance(result, CustomerDTO)
    assert result.id == 33
    assert result.name == "Cliente X"


@pytest.mark.asyncio
async def test_router_get_customer_http_404(
    db_session: FakeAsyncSession,
    mocker,
):
    mock_service = mocker.Mock()
    mock_service.get = AsyncMock(
        side_effect=HTTPException(status_code=404, detail="Customer not found.")
    )

    with pytest.raises(HTTPException) as exc:
        await get_customer(
            customer_id=99,
            db=db_session,
            service=mock_service,
        )

    assert exc.value.status_code == 404
    assert exc.value.detail == "Customer not found."


@pytest.mark.asyncio
async def test_router_get_customer_generic_error_returns_500(
    db_session: FakeAsyncSession,
    mocker,
):
    mock_service = mocker.Mock()
    mock_service.get = AsyncMock(side_effect=RuntimeError("boom"))

    with pytest.raises(HTTPException) as exc:
        await get_customer(
            customer_id=1,
            db=db_session,
            service=mock_service,
        )

    assert exc.value.status_code == 500
    assert exc.value.detail == "Failed to fetch customer"


@pytest.mark.asyncio
async def test_router_list_customers_success(
    db_session: FakeAsyncSession,
    mocker,
):
    mock_service = mocker.Mock()
    mock_service.list_all = AsyncMock(
        return_value=[
            make_customer_dto(id=1, name="A"),
            make_customer_dto(id=2, name="B"),
        ]
    )

    result = await list_customers(
        db=db_session,
        service=mock_service,
    )

    mock_service.list_all.assert_awaited_once_with(db_session)
    assert isinstance(result, list)
    assert len(result) == 2
    assert {c.name for c in result} == {"A", "B"}


@pytest.mark.asyncio
async def test_router_list_customers_generic_error_returns_500(
    db_session: FakeAsyncSession,
    mocker,
):
    mock_service = mocker.Mock()
    mock_service.list_all = AsyncMock(side_effect=RuntimeError("boom"))

    with pytest.raises(HTTPException) as exc:
        await list_customers(
            db=db_session,
            service=mock_service,
        )

    assert exc.value.status_code == 500
    assert exc.value.detail == "Failed to list customers"


@pytest.mark.asyncio
async def test_router_list_customers_paginated_success(
    db_session: FakeAsyncSession,
    mocker,
):
    page_dto = CustomerPageDTO(
        items=[make_customer_dto(id=1), make_customer_dto(id=2)],
        page=1,
        page_size=8,
        total=10,
        total_pages=2,
        has_next=True,
        has_prev=False,
    )

    mock_service = mocker.Mock()
    mock_service.list_paginated = AsyncMock(return_value=page_dto)

    result = await list_customers_paginated(
        page=1,
        db=db_session,
        service=mock_service,
    )

    mock_service.list_paginated.assert_awaited_once_with(1, db_session)
    assert result.page == 1
    assert result.total == 10
    assert len(result.items) == 2


@pytest.mark.asyncio
async def test_router_list_customers_paginated_error_returns_500(
    db_session: FakeAsyncSession,
    mocker,
):
    mock_service = mocker.Mock()
    mock_service.list_paginated = AsyncMock(side_effect=RuntimeError("boom"))

    with pytest.raises(HTTPException) as exc:
        await list_customers_paginated(
            page=1,
            db=db_session,
            service=mock_service,
        )

    assert exc.value.status_code == 500
    assert exc.value.detail == "Failed to list customers"


@pytest.mark.asyncio
async def test_router_update_customer_success(
    db_session: FakeAsyncSession,
    mocker,
    fake_auth_ctx,
):
    updated = make_customer_dto(id=10, name="Nuevo Nombre")

    mock_service = mocker.Mock()
    mock_service.update_partial = AsyncMock(return_value=updated)

    mocker.patch(
        "app.v1_0.routers.customer_router.build_channel_id_from_auth",
        return_value="chan-upd",
    )

    payload = CustomerUpdate(
        name="Nuevo Nombre",
        tax_id=None,
        email=None,
        phone=None,
        address=None,
        city=None,
    )

    result = await update_customer(
        customer_id=10,
        data=payload,
        db=db_session,
        auth_ctx=fake_auth_ctx,
        service=mock_service,
    )

    mock_service.update_partial.assert_awaited_once()
    assert isinstance(result, CustomerDTO)
    assert result.id == 10
    assert result.name == "Nuevo Nombre"


@pytest.mark.asyncio
async def test_router_update_customer_generic_error_returns_500(
    db_session: FakeAsyncSession,
    mocker,
    fake_auth_ctx,
):
    mock_service = mocker.Mock()
    mock_service.update_partial = AsyncMock(side_effect=RuntimeError("boom"))

    mocker.patch(
        "app.v1_0.routers.customer_router.build_channel_id_from_auth",
        return_value="chan-upd",
    )

    payload = CustomerUpdate(
        name="X",
        tax_id=None,
        email=None,
        phone=None,
        address=None,
        city=None,
    )

    with pytest.raises(HTTPException) as exc:
        await update_customer(
            customer_id=10,
            data=payload,
            db=db_session,
            auth_ctx=fake_auth_ctx,
            service=mock_service,
        )

    assert exc.value.status_code == 500
    assert exc.value.detail == "Failed to update customer"


@pytest.mark.asyncio
async def test_router_update_customer_balance_success(
    db_session: FakeAsyncSession,
    mocker,
    fake_auth_ctx,
):
    updated = make_customer_dto(id=20, balance=500.0)

    mock_service = mocker.Mock()
    mock_service.update_balance = AsyncMock(return_value=updated)

    mocker.patch(
        "app.v1_0.routers.customer_router.build_channel_id_from_auth",
        return_value="chan-bal",
    )

    result = await update_customer_balance(
        customer_id=20,
        new_balance=500.0,
        db=db_session,
        auth_ctx=fake_auth_ctx,
        service=mock_service,
    )

    mock_service.update_balance.assert_awaited_once_with(
        customer_id=20,
        new_balance=500.0,
        db=db_session,
        channel_id="chan-bal",
    )

    assert isinstance(result, CustomerDTO)
    assert result.balance == 500.0



@pytest.mark.asyncio
async def test_router_update_customer_balance_generic_error_returns_500(
    db_session: FakeAsyncSession,
    mocker,
    fake_auth_ctx,
):
    mock_service = mocker.Mock()
    mock_service.update_balance = AsyncMock(side_effect=RuntimeError("boom"))

    mocker.patch(
        "app.v1_0.routers.customer_router.build_channel_id_from_auth",
        return_value="chan-bal",
    )

    with pytest.raises(HTTPException) as exc:
        await update_customer_balance(
            customer_id=20,
            new_balance=100.0,
            db=db_session,
            auth_ctx=fake_auth_ctx,
            service=mock_service,
        )

    assert exc.value.status_code == 500
    assert exc.value.detail == "Failed to update balance"


@pytest.mark.asyncio
async def test_router_delete_customer_success_returns_message(
    db_session: FakeAsyncSession,
    mocker,
    fake_auth_ctx,
):
    mock_service = mocker.Mock()
    mock_service.delete = AsyncMock(return_value=True)

    mocker.patch(
        "app.v1_0.routers.customer_router.build_channel_id_from_auth",
        return_value="chan-del",
    )

    result = await delete_customer(
        customer_id=5,
        db=db_session,
        auth_ctx=fake_auth_ctx,
        service=mock_service,
    )

    mock_service.delete.assert_awaited_once_with(
        customer_id=5,
        db=db_session,
        channel_id="chan-del",
    )

    assert result == {"message": "Customer with ID 5 deleted successfully"}



@pytest.mark.asyncio
async def test_router_delete_customer_not_found_returns_404(
    db_session: FakeAsyncSession,
    mocker,
    fake_auth_ctx,
):
    mock_service = mocker.Mock()
    mock_service.delete = AsyncMock(return_value=False)

    mocker.patch(
        "app.v1_0.routers.customer_router.build_channel_id_from_auth",
        return_value="chan-del",
    )

    with pytest.raises(HTTPException) as exc:
        await delete_customer(
            customer_id=99,
            db=db_session,
            auth_ctx=fake_auth_ctx,
            service=mock_service,
        )

    assert exc.value.status_code == 404
    assert exc.value.detail == "Customer not found"


@pytest.mark.asyncio
async def test_router_delete_customer_generic_error_returns_500(
    db_session: FakeAsyncSession,
    mocker,
    fake_auth_ctx,
):
    mock_service = mocker.Mock()
    mock_service.delete = AsyncMock(side_effect=RuntimeError("boom"))

    mocker.patch(
        "app.v1_0.routers.customer_router.build_channel_id_from_auth",
        return_value="chan-del",
    )

    with pytest.raises(HTTPException) as exc:
        await delete_customer(
            customer_id=1,
            db=db_session,
            auth_ctx=fake_auth_ctx,
            service=mock_service,
        )

    assert exc.value.status_code == 500
    assert exc.value.detail == "Failed to delete customer"


@pytest.mark.asyncio
async def test_router_create_simple_payment_success(
    db_session: FakeAsyncSession,
    mocker,
    fake_auth_ctx,
):
    mock_service = mocker.Mock()
    mock_service.register_simple_balance_payment = AsyncMock(return_value=True)

    mocker.patch(
        "app.v1_0.routers.customer_router.build_channel_id_from_auth",
        return_value="chan-pay",
    )

    payload = StandalonePaymentIn(
        bank_id=2,
        amount=50.0,
        description="Pago router",
    )

    result = await create_simple_payment(
        customer_id=1,
        payload=payload,
        db=db_session,
        auth_ctx=fake_auth_ctx,
        service=mock_service,
    )

    mock_service.register_simple_balance_payment.assert_awaited_once_with(
        customer_id=1,
        bank_id=2,
        amount=50.0,
        description="Pago router",
        db=db_session,
        channel_id="chan-pay",
    )
    assert result is True


@pytest.mark.asyncio
async def test_router_create_simple_payment_generic_error_returns_500(
    db_session: FakeAsyncSession,
    mocker,
    fake_auth_ctx,
):
    mock_service = mocker.Mock()
    mock_service.register_simple_balance_payment = AsyncMock(side_effect=RuntimeError("boom"))

    mocker.patch(
        "app.v1_0.routers.customer_router.build_channel_id_from_auth",
        return_value="chan-pay",
    )

    payload = StandalonePaymentIn(
        bank_id=2,
        amount=50.0,
        description="Pago router",
    )

    with pytest.raises(HTTPException) as exc:
        await create_simple_payment(
            customer_id=1,
            payload=payload,
            db=db_session,
            auth_ctx=fake_auth_ctx,
            service=mock_service,
        )

    assert exc.value.status_code == 500
    assert exc.value.detail == "Failed to register payment"