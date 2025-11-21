import pytest
from dataclasses import dataclass
from datetime import datetime
from unittest.mock import AsyncMock

from fastapi import HTTPException 

from app.v1_0.tests.conftest import FakeAsyncSession
from app.v1_0.services.user_service import UserService
from app.v1_0.entities import UserDTO


@dataclass
class DummyUser:
    id: int = 1
    external_sub: str = "sub-1"
    email: str | None = "user@test.com"
    display_name: str | None = "User"
    role_id: int | None = None
    is_active: bool = True
    created_at: datetime = datetime.now()
    updated_at: datetime | None = None


@dataclass
class DummyRole:
    id: int
    code: str


def make_user(
    id: int = 1,
    sub: str = "sub-1",
    email: str | None = "user@test.com",
    name: str | None = "User",
    role_id: int | None = None,
    is_active: bool = True,
) -> DummyUser:
    return DummyUser(
        id=id,
        external_sub=sub,
        email=email,
        display_name=name,
        role_id=role_id,
        is_active=is_active,
        created_at=datetime.now(),
        updated_at=None,
    )


def make_role(id: int = 1, code: str = "admin") -> DummyRole:
    return DummyRole(id=id, code=code)


@pytest.mark.asyncio
async def test_set_role_by_sub_success(
    user_service: UserService,
    user_repository,
    role_repository,
    supabase_admin,
    db_session: FakeAsyncSession,
):
    role_repository.get_code_by_id.return_value = "admin"

    await user_service.set_role_by_sub(sub="auth-sub", role_id=1, db=db_session)

    user_repository.set_role_by_sub.assert_awaited_once_with("auth-sub", 1, db_session)
    role_repository.get_code_by_id.assert_awaited_once_with(1, db_session)
    supabase_admin.set_role_metadata_dynamic.assert_awaited_once()
    assert db_session.committed is True
    assert db_session.rolled_back is False


@pytest.mark.asyncio
async def test_set_role_by_sub_supabase_failure_does_not_raise(
    user_service: UserService,
    user_repository,
    role_repository,
    supabase_admin,
    db_session: FakeAsyncSession,
):
    role_repository.get_code_by_id.return_value = "admin"
    supabase_admin.set_role_metadata_dynamic.side_effect = RuntimeError("supabase down")

    await user_service.set_role_by_sub(sub="auth-sub", role_id=1, db=db_session)

    user_repository.set_role_by_sub.assert_awaited_once()
    role_repository.get_code_by_id.assert_awaited_once()

    assert db_session.committed is True
    assert db_session.rolled_back is False


@pytest.mark.asyncio
async def test_set_role_by_sub_repo_error_rolls_back(
    user_service: UserService,
    user_repository,
    supabase_admin,
    db_session: FakeAsyncSession,
):
    user_repository.set_role_by_sub.side_effect = RuntimeError("db error")

    with pytest.raises(RuntimeError):
        await user_service.set_role_by_sub(sub="auth-sub", role_id=1, db=db_session)

    supabase_admin.set_role_metadata_dynamic.assert_not_awaited()
    assert db_session.rolled_back is True or db_session.committed is False


@pytest.mark.asyncio
async def test_upsert_basics_by_sub_user_exists_commits(
    user_service: UserService,
    user_repository,
    db_session: FakeAsyncSession,
):
    u = make_user(id=10, sub="sub-10", email="old@test.com", name="Old Name")
    user_repository.get_by_sub.return_value = u

    await user_service.upsert_basics_by_sub(
        sub="sub-10",
        email="new@test.com",
        name="New Name",
        db=db_session,
    )

    user_repository.get_by_sub.assert_awaited_once_with("sub-10", db_session)
    user_repository.upsert_basics.assert_awaited_once_with(
        u,
        email="new@test.com",
        name="New Name",
        session=db_session,
    )
    assert db_session.committed is True


@pytest.mark.asyncio
async def test_upsert_basics_by_sub_user_not_found_noop(
    user_service: UserService,
    user_repository,
    db_session: FakeAsyncSession,
):
    user_repository.get_by_sub.return_value = None

    await user_service.upsert_basics_by_sub(
        sub="missing-sub",
        email="x@test.com",
        name="X",
        db=db_session,
    )

    user_repository.get_by_sub.assert_awaited_once_with("missing-sub", db_session)
    user_repository.upsert_basics.assert_not_awaited()
    assert db_session.committed is False
    assert db_session.rolled_back is False


@pytest.mark.asyncio
async def test_list_users_full_maps_roles(
    user_service: UserService,
    user_repository,
    role_repository,
    db_session: FakeAsyncSession,
):
    u1 = make_user(id=1, sub="s1", role_id=1, name="Admin")
    u2 = make_user(id=2, sub="s2", role_id=None, name="NoRole")
    u3 = make_user(id=3, sub="s3", role_id=99, name="OrphanRole")

    user_repository.list_all.return_value = [u1, u2, u3]
    role_repository.list_all.return_value = [
        make_role(id=1, code="admin"),
        make_role(id=2, code="manager"),
    ]

    out = await user_service.list_users_full(db=db_session)

    assert len(out) == 3

    d1, d2, d3 = out
    assert isinstance(d1, UserDTO)
    assert d1.id == 1 and d1.role == "admin"
    assert d2.id == 2 and d2.role is None
    assert d3.id == 3 and d3.role is None


@pytest.mark.asyncio
async def test_get_user_full_by_sub_success_with_role(
    user_service: UserService,
    user_repository,
    role_repository,
    db_session: FakeAsyncSession,
):
    u = make_user(id=1, sub="s1", role_id=2, name="User 1")
    user_repository.get_by_sub.return_value = u
    role_repository.get_code_by_id.return_value = "manager"

    dto = await user_service.get_user_full_by_sub(sub="s1", db=db_session)

    user_repository.get_by_sub.assert_awaited_once_with("s1", db_session)
    role_repository.get_code_by_id.assert_awaited_once_with(2, db_session)

    assert isinstance(dto, UserDTO)
    assert dto.id == 1
    assert dto.role == "manager"


@pytest.mark.asyncio
async def test_get_user_full_by_sub_success_without_role(
    user_service: UserService,
    user_repository,
    role_repository,
    db_session: FakeAsyncSession,
):
    u = make_user(id=2, sub="s2", role_id=None, name="User 2")
    user_repository.get_by_sub.return_value = u

    dto = await user_service.get_user_full_by_sub(sub="s2", db=db_session)

    user_repository.get_by_sub.assert_awaited_once_with("s2", db_session)
    role_repository.get_code_by_id.assert_not_awaited()

    assert dto.id == 2
    assert dto.role is None


@pytest.mark.asyncio
async def test_get_user_full_by_sub_not_found_raises_value_error(
    user_service: UserService,
    user_repository,
    db_session: FakeAsyncSession,
):
    user_repository.get_by_sub.return_value = None

    with pytest.raises(ValueError) as exc:
        await user_service.get_user_full_by_sub(sub="missing", db=db_session)

    assert str(exc.value) == "user_not_found"


@pytest.mark.asyncio
async def test_set_active_by_sub_success_commits(
    user_service: UserService,
    user_repository,
    db_session: FakeAsyncSession,
):
    await user_service.set_active_by_sub(
        sub="s1",
        is_active=False,
        db=db_session,
    )

    user_repository.set_active_by_sub.assert_awaited_once_with(
        "s1",
        False,
        db_session,
    )
    assert db_session.committed is True
    assert db_session.rolled_back is False


@pytest.mark.asyncio
async def test_set_active_by_sub_error_rolls_back(
    user_service: UserService,
    user_repository,
    db_session: FakeAsyncSession,
):
    user_repository.set_active_by_sub.side_effect = RuntimeError("db error")

    with pytest.raises(RuntimeError):
        await user_service.set_active_by_sub(
            sub="s1",
            is_active=True,
            db=db_session,
        )

    assert db_session.rolled_back is True
