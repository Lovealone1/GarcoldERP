import pytest
from datetime import datetime
from fastapi import HTTPException, status

from unittest.mock import AsyncMock

from app.v1_0.services.supplier_service import SupplierService
from app.v1_0.schemas import SupplierCreate
from app.v1_0.models import Supplier
from app.v1_0.entities import SupplierDTO, SupplierPageDTO
from app.v1_0.tests.conftest import FakeAsyncSession
from app.v1_0.routers.supplier_router import (
    create_supplier,
    get_supplier,
    list_suppliers,
    list_suppliers_paginated,
    update_supplier,
    delete_supplier,
)

def make_supplier(
    id: int = 1,
    name: str = "Proveedor X",
    tax_id: str | None = "900000000",
    email: str | None = "prov@example.com",
    phone: str | None = "3000000000",
    address: str | None = "Calle 1 # 1-1",
    city: str | None = "Medellín",
):
    now = datetime.now()
    return Supplier(
        id=id,
        name=name,
        tax_id=tax_id,
        email=email,
        phone=phone,
        address=address,
        city=city,
        created_at=now,
    )


def make_supplier_dto(
    id: int = 1,
    name: str = "Proveedor X",
    tax_id: str | None = "900000000",
    email: str | None = "prov@example.com",
    phone: str | None = "3000000000",
    address: str | None = "Calle 1 # 1-1",
    city: str | None = "Medellín",
):
    now = datetime.now()
    return SupplierDTO(
        id=id,
        name=name,
        tax_id=tax_id,
        email=email,
        phone=phone,
        address=address,
        city=city,
        created_at=now,
    )


@pytest.mark.asyncio
async def test_supplier_create_success(
    db_session: FakeAsyncSession,
    supplier_service: SupplierService,
    supplier_repository,
    mocker,
):
    payload = SupplierCreate(
        name="Nuevo Proveedor",
        tax_id="901111111",
        email="nuevo@example.com",
        phone="3111111111",
        address="Dir 123",
        city="Medellín",
    )

    s = make_supplier(id=10, name="Nuevo Proveedor")
    supplier_repository.create_supplier.return_value = s

    mock_rt = mocker.patch(
        "app.v1_0.services.supplier_service.publish_realtime_event",
        autospec=True,
    )

    dto = await supplier_service.create(payload, db_session, channel_id="chan-1")

    supplier_repository.create_supplier.assert_awaited_once_with(payload, db_session)
    assert dto.id == 10
    assert dto.name == "Nuevo Proveedor"
    assert db_session.committed is True
    assert db_session.rolled_back is False

    mock_rt.assert_awaited_once()
    _, kwargs = mock_rt.await_args
    assert kwargs["channel_id"] == "chan-1"
    assert kwargs["resource"] == "supplier"
    assert kwargs["action"] == "created"
    assert kwargs["payload"]["id"] == dto.id


@pytest.mark.asyncio
async def test_supplier_create_error(
    db_session: FakeAsyncSession,
    supplier_service: SupplierService,
    supplier_repository,
):
    payload = SupplierCreate(
        name="X",
        tax_id="900",
        email="x@example.com",
        phone="300",
        address="Dir",
        city="Med",
    )

    supplier_repository.create_supplier.side_effect = Exception("DB error")

    with pytest.raises(HTTPException) as exc:
        await supplier_service.create(payload, db_session)

    assert exc.value.status_code == 500
    assert "Failed to create supplier" in exc.value.detail
    assert db_session.rolled_back is True


@pytest.mark.asyncio
async def test_supplier_get_success(
    db_session: FakeAsyncSession,
    supplier_service: SupplierService,
    supplier_repository,
):
    s = make_supplier(id=33, name="Proveedor 33")
    supplier_repository.get_supplier_by_id.return_value = s

    dto = await supplier_service.get(33, db_session)

    supplier_repository.get_supplier_by_id.assert_awaited_once_with(33, db_session)
    assert dto.id == 33
    assert dto.name == "Proveedor 33"


@pytest.mark.asyncio
async def test_supplier_get_not_found(
    db_session: FakeAsyncSession,
    supplier_service: SupplierService,
    supplier_repository,
):
    supplier_repository.get_supplier_by_id.return_value = None

    with pytest.raises(HTTPException) as exc:
        await supplier_service.get(99, db_session)

    assert exc.value.status_code == 404
    assert "Supplier not found" in exc.value.detail


@pytest.mark.asyncio
async def test_supplier_get_error(
    db_session: FakeAsyncSession,
    supplier_service: SupplierService,
    supplier_repository,
):
    supplier_repository.get_supplier_by_id.side_effect = RuntimeError("boom")

    with pytest.raises(HTTPException) as exc:
        await supplier_service.get(1, db_session)

    assert exc.value.status_code == 500
    assert "Failed to fetch supplier" in exc.value.detail


@pytest.mark.asyncio
async def test_supplier_list_all_success(
    db_session: FakeAsyncSession,
    supplier_service: SupplierService,
    supplier_repository,
):
    supplier_repository.list_all.return_value = [
        make_supplier(id=1, name="A"),
        make_supplier(id=2, name="B"),
    ]

    lst = await supplier_service.list_all(db_session)

    supplier_repository.list_all.assert_awaited_once_with(db_session)
    assert len(lst) == 2
    assert lst[0].name == "A"
    assert lst[1].name == "B"


@pytest.mark.asyncio
async def test_supplier_list_all_error(
    db_session: FakeAsyncSession,
    supplier_service: SupplierService,
    supplier_repository,
):
    supplier_repository.list_all.side_effect = RuntimeError("boom")

    with pytest.raises(HTTPException) as exc:
        await supplier_service.list_all(db_session)

    assert exc.value.status_code == 500
    assert "Failed to list suppliers" in exc.value.detail


@pytest.mark.asyncio
async def test_supplier_list_paginated(
    db_session: FakeAsyncSession,
    supplier_service: SupplierService,
    supplier_repository,
):
    supplier_repository.list_paginated.return_value = (
        [make_supplier(id=1), make_supplier(id=2)],
        10,  # total
        None,
    )

    page = await supplier_service.list_paginated(1, db_session)

    supplier_repository.list_paginated.assert_awaited_once()
    assert page.page == 1
    assert page.total == 10
    assert len(page.items) == 2
    assert page.total_pages == 2
    assert page.has_next is True
    assert page.has_prev is False


@pytest.mark.asyncio
async def test_supplier_update_partial_success(
    db_session: FakeAsyncSession,
    supplier_service: SupplierService,
    supplier_repository,
    mocker,
):
    updated = make_supplier(id=10, name="Nuevo Nombre")
    supplier_repository.update_supplier.return_value = updated

    mock_rt = mocker.patch(
        "app.v1_0.services.supplier_service.publish_realtime_event",
        autospec=True,
    )

    data = {
        "name": "Nuevo Nombre",
        "tax_id": None,
        "email": None,
        "phone": None,
        "address": None,
        "city": None,
    }

    dto = await supplier_service.update_partial(
        supplier_id=10,
        data=data,
        db=db_session,
        channel_id="chan-1",
    )

    supplier_repository.update_supplier.assert_awaited_once_with(
        10,
        data,
        db_session,
    )
    assert dto.id == 10
    assert dto.name == "Nuevo Nombre"
    assert db_session.committed is True
    assert db_session.rolled_back is False

    mock_rt.assert_awaited_once()
    _, kwargs = mock_rt.await_args
    assert kwargs["channel_id"] == "chan-1"
    assert kwargs["resource"] == "supplier"
    assert kwargs["action"] == "updated"
    assert kwargs["payload"]["id"] == dto.id


@pytest.mark.asyncio
async def test_supplier_update_partial_not_found(
    db_session: FakeAsyncSession,
    supplier_service: SupplierService,
    supplier_repository,
):
    supplier_repository.update_supplier.return_value = None

    data = {"name": "X"}

    with pytest.raises(HTTPException) as exc:
        await supplier_service.update_partial(
            supplier_id=55,
            data=data,
            db=db_session,
        )

    assert exc.value.status_code == 404
    assert "Supplier not found" in exc.value.detail
    assert db_session.rolled_back is True


@pytest.mark.asyncio
async def test_supplier_update_partial_error(
    db_session: FakeAsyncSession,
    supplier_service: SupplierService,
    supplier_repository,
):
    supplier_repository.update_supplier.side_effect = RuntimeError("boom")

    data = {"name": "X"}

    with pytest.raises(HTTPException) as exc:
        await supplier_service.update_partial(
            supplier_id=1,
            data=data,
            db=db_session,
        )

    assert exc.value.status_code == 500
    assert "Failed to update supplier" in exc.value.detail
    assert db_session.rolled_back is True


@pytest.mark.asyncio
async def test_supplier_delete_success(
    db_session: FakeAsyncSession,
    supplier_service: SupplierService,
    supplier_repository,
    mocker,
):
    supplier_repository.delete_supplier.return_value = True

    mock_rt = mocker.patch(
        "app.v1_0.services.supplier_service.publish_realtime_event",
        autospec=True,
    )

    ok = await supplier_service.delete(
        supplier_id=1,
        db=db_session,
        channel_id="chan-del",
    )

    supplier_repository.delete_supplier.assert_awaited_once_with(1, db_session)
    assert ok is True
    assert db_session.committed is True

    mock_rt.assert_awaited_once()
    _, kwargs = mock_rt.await_args
    assert kwargs["channel_id"] == "chan-del"
    assert kwargs["resource"] == "supplier"
    assert kwargs["action"] == "deleted"
    assert kwargs["payload"]["id"] == 1


@pytest.mark.asyncio
async def test_supplier_delete_not_found(
    db_session: FakeAsyncSession,
    supplier_service: SupplierService,
    supplier_repository,
):
    supplier_repository.delete_supplier.return_value = False

    with pytest.raises(HTTPException) as exc:
        await supplier_service.delete(22, db_session)

    assert exc.value.status_code == 404
    assert "Supplier not found" in exc.value.detail
    assert db_session.rolled_back is True


@pytest.mark.asyncio
async def test_supplier_delete_error(
    db_session: FakeAsyncSession,
    supplier_service: SupplierService,
    supplier_repository,
):
    supplier_repository.delete_supplier.side_effect = RuntimeError("boom")

    with pytest.raises(HTTPException) as exc:
        await supplier_service.delete(1, db_session)

    assert exc.value.status_code == 500
    assert "Failed to delete supplier" in exc.value.detail
    assert db_session.rolled_back is True

@pytest.mark.asyncio
async def test_router_create_supplier_returns_dto(
    db_session: FakeAsyncSession,
    mocker,
    fake_auth_ctx,
):
    payload = SupplierCreate(
        name="Proveedor Router",
        tax_id="901111111",
        email="router@example.com",
        phone="3000000000",
        address="Dir 123",
        city="Medellín",
    )

    dto = make_supplier_dto(id=10, name="Proveedor Router")

    mock_service = mocker.Mock()
    mock_service.create = AsyncMock(return_value=dto)

    mocker.patch(
        "app.v1_0.routers.supplier_router.build_channel_id_from_auth",
        return_value="chan-1",
    )

    result = await create_supplier(
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

    assert isinstance(result, SupplierDTO)
    assert result.id == 10
    assert result.name == "Proveedor Router"


@pytest.mark.asyncio
async def test_router_create_supplier_error_returns_500(
    db_session: FakeAsyncSession,
    mocker,
    fake_auth_ctx,
):
    payload = SupplierCreate(
        name="X",
        tax_id="900",
        email="x@example.com",
        phone="300",
        address="Dir",
        city="Med",
    )

    mock_service = mocker.Mock()
    mock_service.create = AsyncMock(side_effect=RuntimeError("boom"))

    mocker.patch(
        "app.v1_0.routers.supplier_router.build_channel_id_from_auth",
        return_value="chan-1",
    )

    with pytest.raises(HTTPException) as exc:
        await create_supplier(
            request=payload,
            db=db_session,
            auth_ctx=fake_auth_ctx,
            service=mock_service,
        )

    assert exc.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert exc.value.detail == "Failed to create supplier"


@pytest.mark.asyncio
async def test_router_get_supplier_success(
    db_session: FakeAsyncSession,
    mocker,
):
    dto = make_supplier_dto(id=5, name="Proveedor 5")

    mock_service = mocker.Mock()
    mock_service.get = AsyncMock(return_value=dto)

    result = await get_supplier(
        supplier_id=5,
        db=db_session,
        service=mock_service,
    )

    mock_service.get.assert_awaited_once_with(5, db_session)
    assert isinstance(result, SupplierDTO)
    assert result.id == 5
    assert result.name == "Proveedor 5"


@pytest.mark.asyncio
async def test_router_get_supplier_http_exception_propagates(
    db_session: FakeAsyncSession,
    mocker,
):
    mock_service = mocker.Mock()
    mock_service.get = AsyncMock(
        side_effect=HTTPException(status_code=404, detail="Supplier not found.")
    )

    with pytest.raises(HTTPException) as exc:
        await get_supplier(
            supplier_id=99,
            db=db_session,
            service=mock_service,
        )

    assert exc.value.status_code == 404
    assert exc.value.detail == "Supplier not found."


@pytest.mark.asyncio
async def test_router_get_supplier_generic_error_returns_500(
    db_session: FakeAsyncSession,
    mocker,
):
    mock_service = mocker.Mock()
    mock_service.get = AsyncMock(side_effect=RuntimeError("boom"))

    with pytest.raises(HTTPException) as exc:
        await get_supplier(
            supplier_id=1,
            db=db_session,
            service=mock_service,
        )

    assert exc.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert exc.value.detail == "Failed to fetch supplier"


@pytest.mark.asyncio
async def test_router_list_suppliers_success(
    db_session: FakeAsyncSession,
    mocker,
):
    suppliers = [
        make_supplier_dto(id=1, name="A"),
        make_supplier_dto(id=2, name="B"),
    ]

    mock_service = mocker.Mock()
    mock_service.list_all = AsyncMock(return_value=suppliers)

    result = await list_suppliers(
        db=db_session,
        service=mock_service,
    )

    mock_service.list_all.assert_awaited_once_with(db_session)
    assert isinstance(result, list)
    assert len(result) == 2
    assert {s.name for s in result} == {"A", "B"}


@pytest.mark.asyncio
async def test_router_list_suppliers_error_returns_500(
    db_session: FakeAsyncSession,
    mocker,
):
    mock_service = mocker.Mock()
    mock_service.list_all = AsyncMock(side_effect=RuntimeError("boom"))

    with pytest.raises(HTTPException) as exc:
        await list_suppliers(
            db=db_session,
            service=mock_service,
        )

    assert exc.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert exc.value.detail == "Failed to list suppliers"


@pytest.mark.asyncio
async def test_router_list_suppliers_paginated_success(
    db_session: FakeAsyncSession,
    mocker,
):
    page_dto = SupplierPageDTO(
        items=[make_supplier_dto(id=1), make_supplier_dto(id=2)],
        page=1,
        page_size=8,
        total=10,
        total_pages=2,
        has_next=True,
        has_prev=False,
    )

    mock_service = mocker.Mock()
    mock_service.list_paginated = AsyncMock(return_value=page_dto)

    result = await list_suppliers_paginated(
        page=1,
        db=db_session,
        service=mock_service,
    )

    mock_service.list_paginated.assert_awaited_once_with(1, db_session)
    assert result.page == 1
    assert result.total == 10
    assert len(result.items) == 2


@pytest.mark.asyncio
async def test_router_list_suppliers_paginated_error_returns_500(
    db_session: FakeAsyncSession,
    mocker,
):
    mock_service = mocker.Mock()
    mock_service.list_paginated = AsyncMock(side_effect=RuntimeError("boom"))

    with pytest.raises(HTTPException) as exc:
        await list_suppliers_paginated(
            page=2,
            db=db_session,
            service=mock_service,
        )

    assert exc.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert exc.value.detail == "Failed to list suppliers"


@pytest.mark.asyncio
async def test_router_update_supplier_success(
    db_session: FakeAsyncSession,
    mocker,
    fake_auth_ctx,
):
    updated = make_supplier_dto(id=10, name="Nuevo Nombre")

    mock_service = mocker.Mock()
    mock_service.update_partial = AsyncMock(return_value=updated)

    mocker.patch(
        "app.v1_0.routers.supplier_router.build_channel_id_from_auth",
        return_value="chan-upd",
    )

    data = {
        "name": "Nuevo Nombre",
        "tax_id": None,
        "email": None,
        "phone": None,
        "address": None,
        "city": None,
    }

    result = await update_supplier(
        supplier_id=10,
        data=data,
        db=db_session,
        auth_ctx=fake_auth_ctx,
        service=mock_service,
    )

    mock_service.update_partial.assert_awaited_once_with(
        supplier_id=10,
        data=data,
        db=db_session,
        channel_id="chan-upd",
    )

    assert isinstance(result, SupplierDTO)
    assert result.id == 10
    assert result.name == "Nuevo Nombre"


@pytest.mark.asyncio
async def test_router_update_supplier_error_returns_500(
    db_session: FakeAsyncSession,
    mocker,
    fake_auth_ctx,
):
    mock_service = mocker.Mock()
    mock_service.update_partial = AsyncMock(side_effect=RuntimeError("boom"))

    mocker.patch(
        "app.v1_0.routers.supplier_router.build_channel_id_from_auth",
        return_value="chan-upd",
    )

    data = {"name": "X"}

    with pytest.raises(HTTPException) as exc:
        await update_supplier(
            supplier_id=10,
            data=data,
            db=db_session,
            auth_ctx=fake_auth_ctx,
            service=mock_service,
        )

    assert exc.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert exc.value.detail == "Failed to update supplier"


@pytest.mark.asyncio
async def test_router_delete_supplier_success_returns_message(
    db_session: FakeAsyncSession,
    mocker,
    fake_auth_ctx,
):
    mock_service = mocker.Mock()
    mock_service.delete = AsyncMock(return_value=True)

    mocker.patch(
        "app.v1_0.routers.supplier_router.build_channel_id_from_auth",
        return_value="chan-del",
    )

    result = await delete_supplier(
        supplier_id=5,
        db=db_session,
        auth_ctx=fake_auth_ctx,
        service=mock_service,
    )

    mock_service.delete.assert_awaited_once_with(
        supplier_id=5,
        db=db_session,
        channel_id="chan-del",
    )

    assert result == {"message": "Supplier with ID 5 deleted successfully"}


@pytest.mark.asyncio
async def test_router_delete_supplier_http_exception_propagates(
    db_session: FakeAsyncSession,
    mocker,
    fake_auth_ctx,
):
    mock_service = mocker.Mock()
    mock_service.delete = AsyncMock(
        side_effect=HTTPException(status_code=404, detail="Supplier not found.")
    )

    mocker.patch(
        "app.v1_0.routers.supplier_router.build_channel_id_from_auth",
        return_value="chan-del",
    )

    with pytest.raises(HTTPException) as exc:
        await delete_supplier(
            supplier_id=99,
            db=db_session,
            auth_ctx=fake_auth_ctx,
            service=mock_service,
        )

    assert exc.value.status_code == 404
    assert exc.value.detail == "Supplier not found."


@pytest.mark.asyncio
async def test_router_delete_supplier_error_returns_500(
    db_session: FakeAsyncSession,
    mocker,
    fake_auth_ctx,
):
    mock_service = mocker.Mock()
    mock_service.delete = AsyncMock(side_effect=RuntimeError("boom"))

    mocker.patch(
        "app.v1_0.routers.supplier_router.build_channel_id_from_auth",
        return_value="chan-del",
    )

    with pytest.raises(HTTPException) as exc:
        await delete_supplier(
            supplier_id=1,
            db=db_session,
            auth_ctx=fake_auth_ctx,
            service=mock_service,
        )

    assert exc.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert exc.value.detail == "Failed to delete supplier"