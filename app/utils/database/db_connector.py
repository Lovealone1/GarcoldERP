from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.engine.url import make_url
from app.core.settings import settings

raw = settings.DATABASE_URL
url = make_url(raw)
if not url.drivername.endswith("+asyncpg"):
    url = url.set(drivername="postgresql+asyncpg")

engine = create_async_engine(
    str(url),
    echo=bool(settings.DEBUG),
    pool_pre_ping=True,
    pool_recycle=1800,
    execution_options={"isolation_level": "READ COMMITTED"},
)

async_session: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
    class_=AsyncSession,
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Provides an AsyncSession. Rolls back on error and always closes."""
    session: AsyncSession = async_session()
    try:
        yield session
    except Exception:
        if session.in_transaction():
            await session.rollback()
        raise
    finally:
        await session.close()

async def dispose_engine() -> None:
    """Disposes the engine on shutdown."""
    await engine.dispose()
