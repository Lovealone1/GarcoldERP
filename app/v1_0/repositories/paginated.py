from typing import Optional, Sequence, Tuple, Type, TypeVar
from sqlalchemy import select, func, desc, tuple_
from sqlalchemy.sql.elements import ColumnElement  
from sqlalchemy.ext.asyncio import AsyncSession

ModelT = TypeVar("ModelT")

WhereExpr = ColumnElement[bool]

async def list_paginated_keyset(
    *,
    session: AsyncSession,
    model: Type[ModelT],
    created_col,                      
    id_col,                           
    limit: int,
    offset: int,
    base_filters: Sequence[WhereExpr] = (),      
    eager: Sequence = (),                         
    pin_enabled: bool = False,
    pin_predicate: Optional[WhereExpr] = None,    
) -> Tuple[list[ModelT], int, bool]:
    pin_exists = False
    if pin_enabled and pin_predicate is not None:
        pin_exists = bool(
            await session.scalar(
                select(func.count()).select_from(model).where(pin_predicate)
            )
        )

    eff_offset = max(offset - (1 if pin_exists else 0), 0)

    total_rows = await session.scalar(
        select(func.count(id_col)).select_from(model).where(*base_filters)
    ) or 0

    take = limit + 1

    if eff_offset == 0:
        stmt = (
            select(model)
            .options(*eager)
            .where(*base_filters)
            .order_by(desc(created_col), desc(id_col))
            .limit(take)
        )
        rows = (await session.execute(stmt)).scalars().all()

    else:
        anchor = (
            await session.execute(
                select(created_col, id_col)
                .select_from(model)
                .where(*base_filters)
                .order_by(desc(created_col), desc(id_col))
                .offset(eff_offset - 1).limit(1)
            )
        ).first()

        if not anchor:
            rows = []
        else:
            ac, aid = anchor
            stmt = (
                select(model)
                .options(*eager)
                .where(*base_filters)
                .where(tuple_(created_col, id_col) < tuple_(ac, aid))
                .order_by(desc(created_col), desc(id_col))
                .limit(take)
            )
            rows = (await session.execute(stmt)).scalars().all()

    items: list[ModelT] = []
    if offset == 0 and pin_enabled and pin_predicate is not None:
        pin = (
            await session.execute(
                select(model).options(*eager).where(pin_predicate).limit(1)
            )
        ).scalars().first()
        if pin:
            items.append(pin)

    remaining_core = max(total_rows - eff_offset, 0)
    visible_core = min(limit, remaining_core)
    has_next = eff_offset + visible_core < total_rows

    page_rows = rows[:visible_core]
    items.extend(page_rows)

    total_public = total_rows + (1 if pin_exists else 0)
    return items, total_public, has_next
