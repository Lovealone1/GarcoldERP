from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession

@asynccontextmanager
async def maybe_begin(session: AsyncSession):
    """
    Si la sesión ya está en transacción, reutilízala.
    Si no, abre una transacción de contexto.
    """
    if session.in_transaction():   
        yield
    else:
        async with session.begin():
            yield
