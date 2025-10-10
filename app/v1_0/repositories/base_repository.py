from typing import Any, Iterable, Optional, Sequence, Tuple, Type, TypeVar, Generic
from sqlalchemy import Select, select, func, insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.v1_0.models import Base

ModelT = TypeVar("ModelT", bound=Base)

class BaseRepository(Generic[ModelT]):

    def __init__(self, model: Type[ModelT]):
        """
        Initialize the repository with its model class.

        Args:
            model: SQLAlchemy model class.
        """
        self.model = model

    async def add(self, entity: ModelT, session: AsyncSession) -> ModelT:
        """
        Add a single entity and flush to materialize PK.

        Args:
            entity: Model instance to persist.
            session: Active async SQLAlchemy session.

        Returns:
            The persisted entity (with primary key set).

        Raises:
            IntegrityError: If a constraint is violated.
        """
        session.add(entity)
        try:
            await session.flush([entity])
        except IntegrityError:
            await session.rollback()
            raise
        return entity

    async def add_many(self, entities: Iterable[ModelT], session: AsyncSession) -> list[ModelT]:
        """
        Add multiple entities in one batch and flush.

        Args:
            entities: Iterable of model instances to persist.
            session: Active async SQLAlchemy session.

        Returns:
            List of persisted entities.
        """
        entities = list(entities)
        session.add_all(entities)
        await session.flush()
        return entities

    async def bulk_insert_core(session, model, rows: list[dict]):
        """
        Insert many rows using SQLAlchemy Core (no ORM instances, faster).

        Args:
            session: Active async SQLAlchemy session.
            model: SQLAlchemy table/model target of the insert.
            rows: List of dictionaries with column values.

        Returns:
            None
        """
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
        """
        Fetch a single entity by primary key.

        Args:
            id_: Primary key value.
            session: Active async SQLAlchemy session.
            options: ORM load options (e.g., eager loading strategies).
            for_update: Apply row lock (`FOR UPDATE`) if True.

        Returns:
            The entity or None if not found.
        """
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
        """
        List all rows of the model table.

        Args:
            session: Active async SQLAlchemy session.
            order_by: Ordering expression. Defaults to `model.id.desc()`.
            options: ORM load options (e.g., eager loading strategies).

        Returns:
            List of entities.
        """
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
        """
        List rows with pagination and return total count.

        Args:
            session: Active async SQLAlchemy session.
            offset: Zero-based starting offset.
            limit: Maximum number of rows to return.
            order_by: Ordering expression. Defaults to `model.id.desc()`.
            options: ORM load options (e.g., eager loading strategies).

        Returns:
            Tuple of (items, total_count).
        """
        if order_by is None:
            order_by = self.model.id.desc()

        page_q: Select = select(self.model).order_by(order_by).offset(offset).limit(limit)
        if options:
            page_q = page_q.options(*options)

        items = list((await session.execute(page_q)).scalars().all())
        total = int((await session.execute(select(func.count()).select_from(self.model))).scalar_one())
        return items, total

    async def update(self, entity: ModelT, session: AsyncSession) -> ModelT:
        """
        Flush pending changes of an entity.

        Args:
            entity: Model instance with modified fields.
            session: Active async SQLAlchemy session.

        Returns:
            The same entity after flush.
        """
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
        """
        Update selected fields on an entity and flush.

        Args:
            entity: Model instance to mutate.
            data: Mapping of field names to new values.
            session: Active async SQLAlchemy session.
            allow: If provided, only these fields are updated.
            deny: If provided, these fields are skipped.

        Returns:
            The entity after fields update and flush.
        """
        for k, v in data.items():
            if allow and k not in allow:
                continue
            if deny and k in deny:
                continue
            setattr(entity, k, v)
        await session.flush([entity])
        return entity

    async def delete(self, entity: ModelT, session: AsyncSession) -> None:
        """
        Delete an entity and flush.

        Args:
            entity: Model instance to delete.
            session: Active async SQLAlchemy session.

        Returns:
            None
        """
        await session.delete(entity)
        await session.flush()

    async def delete_by_id(self, id_: Any, session: AsyncSession) -> int:
        """
        Delete an entity by primary key and flush.

        Args:
            id_: Primary key value.
            session: Active async SQLAlchemy session.

        Returns:
            1 if deleted, 0 if not found.
        """
        obj = await self.get_by_id(id_, session)
        if not obj:
            return 0
        await session.delete(obj)
        await session.flush()
        return 1
