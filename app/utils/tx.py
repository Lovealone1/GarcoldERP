from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession


@asynccontextmanager
async def maybe_begin(session: AsyncSession) -> AsyncIterator[AsyncSession]:
    """
    Open a transaction on `session`, or join the one already running.

    `AsyncSession.begin()` raises `A transaction is already begun on this
    Session` when the session is not idle, and a session is not idle after
    *any* statement: SQLAlchemy autobegins on the first execute. So a bare
    `async with db.begin()` is only correct while nothing else has touched the
    session -- an assumption that silently stopped holding when a dependency
    started reading from the request session, and took the expenses module and
    the customer detail down with it.

    Ownership decides who commits:

    - Idle session: this block owns the transaction and commits on a clean
      exit, rolls back on an exception. Same semantics as `session.begin()`.
    - Transaction already running: the block joins it and commits nothing --
      the caller that opened it stays responsible for the outcome, so a nested
      read or write cannot commit half of its caller's work.

    Yields the session, so `async with maybe_begin(db) as db:` reads naturally.
    """
    if session.in_transaction():
        yield session
        return

    async with session.begin():
        yield session
