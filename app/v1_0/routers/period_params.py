"""
Shared period query parameters for the filtered list and summary endpoints.

Declared once as a dependency rather than repeated across ten endpoints, so
every resource resolves a period the same way and the frontend can send the
same parameters everywhere.
"""

from datetime import date, datetime
from typing import Literal, Optional, Union

from fastapi import HTTPException, Query

from app.utils.date_utils import Period, PeriodError, resolve_period
from app.v1_0.entities import PeriodDTO

DateOrDatetime = Union[date, datetime]


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
    date_from: Optional[DateOrDatetime] = Query(
        None,
        description=(
            "Range start. A date (YYYY-MM-DD) means the start of that day in "
            "America/Bogota; a timestamp is used as the exact instant, and a "
            "naive one is read in Bogota."
        ),
    ),
    date_to: Optional[DateOrDatetime] = Query(
        None,
        description=(
            "Range end. A date (YYYY-MM-DD) means the END of that day in "
            "America/Bogota, so the day's records are included."
        ),
    ),
    period: Optional[Literal["all"]] = Query(
        None,
        description=(
            "Pass 'all' for every record ever written. Explicit by design: "
            "with no parameters the answer is the current month."
        ),
    ),
) -> Period:
    """
    Resolve the period once per request.

    Only one selector may be used: year/month/day, date_from/date_to, or
    period=all. Combining them is a 422.
    """
    try:
        return resolve_period(
            year=year,
            month=month,
            day=day,
            date_from=date_from,
            date_to=date_to,
            all_time=period == "all",
        )
    except PeriodError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def period_dto(period: Period) -> PeriodDTO:
    """The resolved range, in the shape the responses echo back."""
    return PeriodDTO(
        date_from=period.date_from,
        date_to=period.date_to,
        resolved_from=period.resolved_from,
    )


def with_period(page, period: Period):
    """
    Stamp the resolved range onto a pagination envelope.

    Done in the router rather than in the service because the router is where
    the period is resolved; the services keep taking a plain date range.
    """
    page.period = period_dto(period)
    return page


def totals_with_period(totals: dict, period: Period) -> dict:
    """
    Add the resolved range to a flat totals response.

    The existing float keys are untouched, so a caller reading `total` or
    `count` is unaffected.
    """
    return {**totals, "period": period_dto(period)}
