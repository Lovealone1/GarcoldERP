import pytest
from fastapi import HTTPException, status
from unittest.mock import AsyncMock
from app.v1_0.entities import StatusDTO
from app.v1_0.services.status_service import StatusService
from app.v1_0.tests.conftest import FakeAsyncSession
from app.v1_0.routers.status_router import list_statuses
from app.v1_0.entities import StatusDTO
def make_status(id: int = 1, name: str = "Pendiente"):
    class S:
        id: int
        name: str   

    s = S()
    s.id = id
    s.name = name
    return s


@pytest.mark.asyncio
async def test_list_statuses_success(
    status_service: StatusService,
    status_repository,
    db_session: FakeAsyncSession,
):
    rows = [
        make_status(id=1, name="Pendiente"),
        make_status(id=2, name="Pagado"),
    ]
    status_repository.list_statuses.return_value = rows

    result = await status_service.list_statuses(db_session)

    status_repository.list_statuses.assert_awaited_once_with(db_session)
    assert db_session.began is True
    assert db_session.committed is True
    assert db_session.rolled_back is False

    assert isinstance(result, list)
    assert len(result) == 2

    s1, s2 = result
    assert isinstance(s1, StatusDTO)
    assert s1.id == 1
    assert s1.name == "Pendiente"

    assert isinstance(s2, StatusDTO)
    assert s2.id == 2
    assert s2.name == "Pagado"


@pytest.mark.asyncio
async def test_list_statuses_error_raises_500(
    status_service: StatusService,
    status_repository,
    db_session: FakeAsyncSession,
):
    status_repository.list_statuses.side_effect = RuntimeError("db down")

    with pytest.raises(HTTPException) as exc:
        await status_service.list_statuses(db_session)

    err = exc.value
    assert err.status_code == 500
    assert err.detail == "Failed to list statuses"

    assert db_session.began is True
    assert db_session.rolled_back is True

@pytest.mark.asyncio
async def test_router_list_statuses_success(db_session, mocker):
    dto_list = [
        StatusDTO(id=1, name="Pendiente"),
        StatusDTO(id=2, name="Pagado"),
    ]

    mock_service = mocker.Mock()
    mock_service.list_statuses = AsyncMock(return_value=dto_list)

    result = await list_statuses(
        db=db_session,
        service=mock_service,
    )

    mock_service.list_statuses.assert_awaited_once_with(db_session)

    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0].id == 1
    assert result[0].name == "Pendiente"

@pytest.mark.asyncio
async def test_router_list_statuses_error_returns_500(db_session, mocker):
    mock_service = mocker.Mock()
    mock_service.list_statuses = AsyncMock(side_effect=RuntimeError("boom"))

    with pytest.raises(HTTPException) as exc:
        await list_statuses(
            db=db_session,
            service=mock_service,
        )

    assert exc.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert exc.value.detail == "Failed to list statuses"
