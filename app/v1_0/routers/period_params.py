"""
Shared year/month/day query parameters for the filtered list endpoints.

Declared once as a dependency rather than repeated across ten endpoints, so
every resource resolves a period the same way and the frontend can send the
same parameters everywhere.
"""

from datetime import datetime
from typing import Optional

from fastapi import HTTPException, Query

from app.utils.date_utils import Period, PeriodError, resolve_period


def period_range(
    year: Optional[int] = Query(
        None, ge=1970, le=2999, description="Calendar year, e.g. 2026"
    ),
    month: Optional[int] = Query(
        None, ge=1, le=12, description="Month 1-12; year defaults to the current one"
    ),
    day: Optional[int] = Query(
        None,
        ge=1,
        le=31,
        description="Day of month; year and month default to the current ones",
    ),
    date_from: Optional[datetime] = Query(
        None, description="Arbitrary range start; cannot be combined with year/month/day"
    ),
    date_to: Optional[datetime] = Query(
        None, description="Arbitrary range end; cannot be combined with year/month/day"
    ),
) -> Period:
    """
    Resolve the period once per request.

    With no parameters this is the current month, not the whole history.
    """
    try:
        return resolve_period(
            year=year, month=month, day=day, date_from=date_from, date_to=date_to
        )
    except PeriodError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
