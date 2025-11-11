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
    echo=bool(getattr(settings, "DEBUG", False)),
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
    session: AsyncSession = async_session()
    try:
        yield session
    finally:
        await session.close()

async def dispose_engine() -> None:
    await engine.dispose()
