# app/utils/database/db_connector.py
from collections.abc import AsyncGenerator
from sqlalchemy.engine.url import make_url, URL
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from app.core.settings import settings

# Ej: settings.DATABASE_URL = "postgresql://user:pass@ep-...-pooler.neon.tech/db?sslmode=require&channel_binding=require"

raw = settings.DATABASE_URL

# 1) Parseo base
u = make_url(raw)

# 2) Construyo un URL limpio sin query y con driver asyncpg
#    (evita que cualquier query como channel_binding/sslmode llegue a asyncpg)
clean_url: URL = URL.create(
    drivername="postgresql+asyncpg",
    username=u.username,
    password=u.password,
    host=u.host,
    port=u.port,
    database=u.database,
)

# 3) Engine: usa PgBouncer del pooler de Neon
engine = create_async_engine(
    clean_url.render_as_string(hide_password=False),
    echo=bool(getattr(settings, "DEBUG", False)),
    poolclass=NullPool,
    pool_pre_ping=True,
    execution_options={"isolation_level": "READ COMMITTED"},
    # Lo único que va a asyncpg.connect():
    connect_args={
        "ssl": True,                 # TLS ON
        "statement_cache_size": 0,   # evita prepared stmts con PgBouncer
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
