from __future__ import annotations

import calendar
from datetime import date, datetime, time
from typing import NamedTuple, Optional, Union
from zoneinfo import ZoneInfo

#: The business runs on Colombian time. The server does not: on Railway it is
#: UTC, where 7pm in Bogota is already the next calendar day. Resolving "this
#: month" against the server clock would move the default period a day early
#: every evening, so every calendar boundary here is computed in this zone.
BOGOTA = ZoneInfo("America/Bogota")

#: Where a resolved range came from, echoed back so a client can label what it
#: is showing without re-deriving it against its own clock.
ResolvedFrom = str  # "default" | "calendar" | "range" | "all"

DateOrDatetime = Union[date, datetime]


def now_colombian_time() -> datetime:
    """Returns the current datetime in the America/Bogota timezone."""
    return datetime.now(BOGOTA)


class PeriodError(ValueError):
    """A period selector that cannot be resolved into a range."""


class Period(NamedTuple):
    """An inclusive [date_from, date_to]; either end may be None (open)."""

    date_from: Optional[datetime]
    date_to: Optional[datetime]
    resolved_from: ResolvedFrom = "range"


def _start_of(day: date) -> datetime:
    return datetime.combine(day, time.min).replace(tzinfo=BOGOTA)


def _end_of(day: date) -> datetime:
    # The filters compare with <=, so the upper bound is the last instant of
    # the day rather than midnight of the next one.
    return datetime.combine(day, time.max).replace(tzinfo=BOGOTA)


def _whole_month(year: int, month: int, source: ResolvedFrom) -> Period:
    last = calendar.monthrange(year, month)[1]
    return Period(
        _start_of(date(year, month, 1)), _end_of(date(year, month, last)), source
    )


def _as_bound(value: Optional[DateOrDatetime], *, upper: bool) -> Optional[datetime]:
    """
    Normalise one end of a free range.

    A bare date carries no time of day, so it means the whole calendar day in
    Bogota -- the start of it for the lower bound, the end of it for the upper.
    Sending `2026-09-30` as an upper bound and having it mean midnight would
    silently drop that day's records, which is the failure this avoids.

    A naive timestamp is read in Bogota rather than in the server's zone, for
    the same reason the calendar boundaries are.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=BOGOTA)
        return value
    return _end_of(value) if upper else _start_of(value)


def resolve_period(
    *,
    year: Optional[int] = None,
    month: Optional[int] = None,
    day: Optional[int] = None,
    date_from: Optional[DateOrDatetime] = None,
    date_to: Optional[DateOrDatetime] = None,
    all_time: bool = False,
    today: Optional[date] = None,
) -> Period:
    """
    Turn a period selector into the range the filters actually use.

    The screens ask for a year, a month, a single day, an arbitrary range or
    explicitly for everything; the repositories only understand
    `column >= date_from AND column <= date_to`. This is the one place that
    translates between the two, so month lengths, leap years and the Bogota
    offset are worked out once instead of in every caller.

    Missing coarser units are filled from today, so `day=5` means the fifth of
    the current month and `month=3` means March of the current year. One rule,
    no special cases.

    With nothing supplied at all the answer is the current month. It used to be
    every record ever written, which is why a screen's total read as the whole
    history of the business instead of the period on display. All history is
    still available, but it has to be asked for by name (`all_time`) so it
    appears in the logs as an intent rather than as an absent parameter.

    Only one selector may be used at a time. Silently letting one win is how a
    filter ends up reporting a period nobody asked for.
    """
    calendar_selector = any(v is not None for v in (year, month, day))
    free_range = date_from is not None or date_to is not None

    chosen = [
        name
        for name, used in (
            ("period=all", all_time),
            ("year/month/day", calendar_selector),
            ("date_from/date_to", free_range),
        )
        if used
    ]
    if len(chosen) > 1:
        raise PeriodError(
            f"Pass only one period selector, got {' and '.join(chosen)}: "
            "they describe the same range."
        )

    if all_time:
        return Period(None, None, "all")

    if free_range:
        lower = _as_bound(date_from, upper=False)
        upper = _as_bound(date_to, upper=True)
        if lower is not None and upper is not None and lower > upper:
            lower, upper = upper, lower
        return Period(lower, upper, "range")

    ref = today or now_colombian_time().date()

    if month is not None and not 1 <= month <= 12:
        raise PeriodError(f"month must be between 1 and 12, got {month}")

    if day is not None:
        y = year if year is not None else ref.year
        m = month if month is not None else ref.month
        last = calendar.monthrange(y, m)[1]
        if not 1 <= day <= last:
            raise PeriodError(
                f"day {day} does not exist in {y:04d}-{m:02d} "
                f"(that month has {last} days)"
            )
        target = date(y, m, day)
        return Period(_start_of(target), _end_of(target), "calendar")

    if month is not None:
        return _whole_month(year if year is not None else ref.year, month, "calendar")

    if year is not None:
        return Period(
            _start_of(date(year, 1, 1)), _end_of(date(year, 12, 31)), "calendar"
        )

    return _whole_month(ref.year, ref.month, "default")
