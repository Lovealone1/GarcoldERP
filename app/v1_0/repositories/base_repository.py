from typing import Any, Iterable, Optional, Sequence, Tuple, Type, TypeVar, Generic, Protocol, runtime_checkable
from sqlalchemy import Select, select, func, insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

# --- los modelos deben exponer .id ---
@runtime_checkable
class HasId(Protocol):
    id: Any  # columna PK

ModelT = TypeVar("ModelT", bound=HasId)


class BaseRepository(Generic[ModelT]):
    def __init__(self, model: Type[ModelT]):
        self.model = model

    async def add(self, entity: ModelT, session: AsyncSession) -> ModelT:
        session.add(entity)
        try:
            await session.flush([entity])
        except IntegrityError:
            await session.rollback()
            raise
        return entity

    async def add_many(self, entities: Iterable[ModelT], session: AsyncSession) -> list[ModelT]:
        items = list(entities)
        session.add_all(items)
        await session.flush()
        return items

    async def bulk_insert_core(self,session: AsyncSession, model: Any, rows: list[dict]) -> None:
        stmt = insert(model).values(rows)
        await session.execute(stmt)
        await session.flush()

    async def get_by_id(
        self,
        id_: Any,
        session: AsyncSession,
        *,
        options: Sequence[Any] | None = None,
        for_update: bool = False,
    ) -> Optional[ModelT]:
        stmt: Select = select(self.model).where(self.model.id == id_)
        if for_update:
            stmt = stmt.with_for_update()
        if options:
            stmt = stmt.options(*options)
        res = await session.execute(stmt)
        return res.scalars().first()

    async def list_all(
        self,
        session: AsyncSession,
        *,
        order_by: Any | None = None,
        options: Sequence[Any] | None = None,
    ) -> list[ModelT]:
        if order_by is None:
            order_by = self.model.id.desc()
        stmt: Select = select(self.model).order_by(order_by)
        if options:
            stmt = stmt.options(*options)
        res = await session.execute(stmt)
        return list(res.scalars().all())

    async def list_paginated(
        self,
        session: AsyncSession,
        offset: int,
        limit: int,
        *,
        order_by: Any | None = None,
        options: Sequence[Any] | None = None,
    ) -> Tuple[list[ModelT], int]:
        if order_by is None:
            order_by = self.model.id.desc()

        page_q: Select = select(self.model).order_by(order_by).offset(offset).limit(limit)
        if options:
            page_q = page_q.options(*options)

        items = list((await session.execute(page_q)).scalars().all())
        total = int(await session.scalar(select(func.count(self.model.id))) or 0)
        return items, total

    async def update(self, entity: ModelT, session: AsyncSession) -> ModelT:
        await session.flush([entity])
        return entity

    async def update_fields(
        self,
        entity: ModelT,
        data: dict[str, Any],
        session: AsyncSession,
        *,
        allow: set[str] | None = None,
        deny: set[str] | None = None,
    ) -> ModelT:
        for k, v in data.items():
            if allow and k not in allow:
                continue
            if deny and k in deny:
                continue
            setattr(entity, k, v)
        await session.flush([entity])
        return entity

    async def delete(self, entity: ModelT, session: AsyncSession) -> None:
        await session.delete(entity)
        await session.flush()

    async def delete_by_id(self, id_: Any, session: AsyncSession) -> int:
        obj = await self.get_by_id(id_, session)
        if not obj:
            return 0
        await session.delete(obj)
        await session.flush()
        return 1
