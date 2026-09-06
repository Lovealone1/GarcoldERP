"""
Who owns the transaction on a request's session.

The expenses module and the customer detail returned
`A transaction is already begun on this Session` for every request. The cause
was in neither module: authentication is applied at router registration
(app/v1_0/v1_router.py) and `get_auth_context` took its session from
`Depends(get_db)`. FastAPI caches that dependency per request, so authentication
and the endpoint shared one session; the auth SELECTs autobegan a transaction
on it and nothing ever ended it, so the first `async with db.begin()` inside a
service raised.

Two properties keep it fixed:

- `get_auth_context` runs on its own session, leaving the handler's idle.
- `maybe_begin` opens a transaction or joins one, so a service can no longer be
  broken by whoever touched the session first.
"""

from datetime import datetime, timezone

import pytest
from fastapi import APIRouter, Depends, FastAPI
from sqlalchemy import func, insert, select, text
from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from app.core.security import deps as auth_deps_module
from app.core.security.deps import get_auth_context
from app.storage.database.db_connector import get_db
from app.utils.tx import maybe_begin
from app.v1_0.models import Role, User

#: The mapped tables get_auth_context reads through the ORM.
AUTH_TABLES = [Role.__table__, User.__table__]

#: `permission` and `role_permission` are read by the raw SQL in
#: AuthDeps.permissions_for_role, and their mapped definitions carry Postgres
#: types (JSONB) that SQLite cannot build. Only the columns that query touches
#: matter here.
PERMISSION_DDL = (
    "create table permission (id integer primary key, code text not null)",
    "create table role_permission (role_id integer, permission_id integer)",
)

SUB = "auth0|probe-user"

AUTHORIZED = {"Authorization": "Bearer any-token"}


@pytest.fixture
async def auth_db():
    """An SQLite database holding one provisioned user with one permission."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        for table in AUTH_TABLES:
            await conn.run_sync(table.create)
        for ddl in PERMISSION_DDL:
            await conn.execute(text(ddl))

        now = datetime.now(timezone.utc)
        await conn.execute(insert(Role.__table__).values(id=1, code="admin"))
        await conn.execute(
            insert(User.__table__).values(
                id=1,
                external_sub=SUB,
                email="probe@example.com",
                display_name="Probe",
                role_id=1,
                is_active=True,
                created_at=now,
                updated_at=now,
            )
        )
        await conn.execute(
            text("insert into permission (id, code) values (1, 'expenses.read')")
        )
        await conn.execute(
            text("insert into role_permission (role_id, permission_id) values (1, 1)")
        )

    sessionmaker = async_sessionmaker(
        bind=engine, expire_on_commit=False, autoflush=False, class_=AsyncSession
    )
    yield sessionmaker
    await engine.dispose()


@pytest.fixture
def authenticated_app(auth_db, monkeypatch):
    """
    A protected route wired the way every v1 router is: authentication applied
    at registration, the handler taking its own `Depends(get_db)`.
    """
    monkeypatch.setattr(auth_deps_module, "async_session", auth_db, raising=True)

    async def _fake_verify_token(token: str):
        return {"sub": SUB}

    monkeypatch.setattr(
        auth_deps_module, "verify_token", _fake_verify_token, raising=True
    )

    probe = APIRouter(prefix="/probe")

    @probe.get("/idle")
    async def reports_transaction_state(db: AsyncSession = Depends(get_db)):
        return {"in_transaction": db.in_transaction()}

    @probe.get("/explicit-begin")
    async def opens_its_own_transaction(db: AsyncSession = Depends(get_db)):
        # Exactly what the services did: a bare begin() on the request session.
        async with db.begin():
            total = await db.scalar(select(func.count()).select_from(User.__table__))
        return {"users": total}

    @probe.get("/maybe-begin")
    async def joins_or_opens(db: AsyncSession = Depends(get_db)):
        async with maybe_begin(db) as session:
            total = await session.scalar(
                select(func.count()).select_from(User.__table__)
            )
        return {"users": total}

    holder = APIRouter(prefix="/v1")
    holder.include_router(probe, dependencies=[Depends(get_auth_context)])

    app = FastAPI()
    app.include_router(holder)

    async def _request_session():
        session = auth_db()
        try:
            yield session
        finally:
            await session.close()

    app.dependency_overrides[get_db] = _request_session
    return app


class TestAuthenticationLeavesTheHandlerSessionAlone:
    def test_the_handler_receives_an_idle_session(self, authenticated_app):
        with TestClient(authenticated_app) as client:
            res = client.get("/v1/probe/idle", headers=AUTHORIZED)
        assert res.status_code == 200
        assert res.json()["in_transaction"] is False

    def test_a_handler_can_open_its_own_transaction(self, authenticated_app):
        # This is the request that returned 500 in production.
        with TestClient(authenticated_app) as client:
            res = client.get("/v1/probe/explicit-begin", headers=AUTHORIZED)
        assert res.status_code == 200, res.text
        assert res.json() == {"users": 1}

    def test_the_same_holds_through_maybe_begin(self, authenticated_app):
        with TestClient(authenticated_app) as client:
            res = client.get("/v1/probe/maybe-begin", headers=AUTHORIZED)
        assert res.status_code == 200, res.text
        assert res.json() == {"users": 1}

    def test_authentication_does_not_depend_on_the_request_session(self):
        from fastapi.dependencies.utils import get_dependant

        dependant = get_dependant(path="/", call=get_auth_context)
        shared = {d.call for d in dependant.dependencies}
        assert get_db not in shared, (
            "get_auth_context is back on Depends(get_db); FastAPI caches it, so "
            "its transaction would leak into every handler again"
        )

    def test_an_unprovisioned_user_is_still_rejected(
        self, authenticated_app, monkeypatch
    ):
        async def _other_sub(token: str):
            return {"sub": "auth0|nobody"}

        monkeypatch.setattr(auth_deps_module, "verify_token", _other_sub, raising=True)
        with TestClient(authenticated_app) as client:
            res = client.get("/v1/probe/idle", headers=AUTHORIZED)
        assert res.status_code == 401


class TestASessionTouchingDependencyIsNoLongerFatal:
    """
    The shape of the original bug, reproduced deliberately.

    `get_auth_context` no longer reads from the request session, but the next
    dependency someone adds might. `maybe_begin` is what keeps that from being
    a 500 on every endpoint again, so the difference is pinned here.
    """

    @staticmethod
    def _app_with_a_reading_dependency(auth_db):
        async def reads_the_request_session(db: AsyncSession = Depends(get_db)):
            # Any statement autobegins a transaction the handler did not open.
            await db.scalar(select(func.count()).select_from(User.__table__))

        probe = APIRouter(prefix="/probe")

        @probe.get("/explicit-begin")
        async def bare_begin(db: AsyncSession = Depends(get_db)):
            async with db.begin():
                return {"ok": True}

        @probe.get("/maybe-begin")
        async def guarded_begin(db: AsyncSession = Depends(get_db)):
            async with maybe_begin(db):
                return {"ok": True}

        app = FastAPI()
        app.include_router(probe, dependencies=[Depends(reads_the_request_session)])

        async def _request_session():
            session = auth_db()
            try:
                yield session
            finally:
                await session.close()

        app.dependency_overrides[get_db] = _request_session
        return app

    def test_a_bare_begin_still_breaks(self, auth_db):
        app = self._app_with_a_reading_dependency(auth_db)
        with TestClient(app) as client:
            with pytest.raises(InvalidRequestError, match="already begun"):
                client.get("/probe/explicit-begin")

    def test_maybe_begin_carries_the_request_through(self, auth_db):
        app = self._app_with_a_reading_dependency(auth_db)
        with TestClient(app) as client:
            res = client.get("/probe/maybe-begin")
        assert res.status_code == 200, res.text
        assert res.json() == {"ok": True}


@pytest.fixture
async def session_factory():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.execute(
            text("create table note (id integer primary key, body text)")
        )
    sessionmaker = async_sessionmaker(
        bind=engine, expire_on_commit=False, autoflush=False
    )
    yield sessionmaker
    await engine.dispose()


async def _notes(sessionmaker) -> int:
    async with sessionmaker() as probe:
        return await probe.scalar(text("select count(*) from note"))


class TestMaybeBegin:
    async def test_it_opens_a_transaction_on_an_idle_session(self, session_factory):
        async with session_factory() as session:
            assert not session.in_transaction()
            async with maybe_begin(session):
                assert session.in_transaction()

    async def test_it_commits_the_transaction_it_owns(self, session_factory):
        async with session_factory() as session:
            async with maybe_begin(session):
                await session.execute(text("insert into note (body) values ('owned')"))
        assert await _notes(session_factory) == 1

    async def test_it_rolls_back_the_transaction_it_owns_on_error(
        self, session_factory
    ):
        with pytest.raises(RuntimeError):
            async with session_factory() as session:
                async with maybe_begin(session):
                    await session.execute(
                        text("insert into note (body) values ('doomed')")
                    )
                    raise RuntimeError("boom")
        assert await _notes(session_factory) == 0

    async def test_it_joins_a_transaction_someone_else_started(self, session_factory):
        # A bare begin() raises here; that is the production failure.
        async with session_factory() as session:
            await session.execute(text("select 1"))
            assert session.in_transaction()

            with pytest.raises(InvalidRequestError):
                async with session.begin():
                    pass

            async with maybe_begin(session):
                await session.execute(text("insert into note (body) values ('joined')"))

    async def test_joining_leaves_the_commit_to_the_owner(self, session_factory):
        async with session_factory() as session:
            async with session.begin():
                async with maybe_begin(session):
                    await session.execute(
                        text("insert into note (body) values ('nested')")
                    )
                # The inner block must not have committed on the owner's behalf.
                assert session.in_transaction()
        assert await _notes(session_factory) == 1

    async def test_the_yielded_value_is_the_session(self, session_factory):
        async with session_factory() as session:
            async with maybe_begin(session) as yielded:
                assert yielded is session
