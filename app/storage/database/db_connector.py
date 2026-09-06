from collections.abc import AsyncGenerator
from sqlalchemy.engine.url import make_url, URL
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from app.core.settings import settings

raw: str = settings.DATABASE_URL.get_secret_value()

u = make_url(raw)

clean_url: URL = URL.create(
    drivername="postgresql+asyncpg",
    username=u.username,
    password=u.password,
    host=u.host,
    port=u.port,
    database=u.database,
)

engine = create_async_engine(
    clean_url.render_as_string(hide_password=False),
    echo=settings.DEBUG,
    poolclass=NullPool,
    pool_pre_ping=True,
    execution_options={"isolation_level": "READ COMMITTED"},
    connect_args={
        "ssl": True,               
        "statement_cache_size": 0, 
    },
)

async_session = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False, class_=AsyncSession)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    The request's session, owned by the endpoint that handles it.

    FastAPI caches this dependency per request, so everything that declares
    `Depends(get_db)` -- the handler and any dependency above it -- receives the
    same object. The transaction on it therefore has to have one owner: a
    dependency that runs a statement here autobegins a transaction the handler
    never opened and never closes, and the handler's own `begin()` then fails
    with `A transaction is already begun on this Session`.

    So anything that needs the database *before* the handler runs opens its own
    session instead (see `get_auth_context`), and services guard their
    transaction blocks with `app.utils.tx.maybe_begin`.
    """
    session: AsyncSession = async_session()
    try:
        yield session
    finally:
        await session.close()

async def dispose_engine() -> None:
    await engine.dispose()
