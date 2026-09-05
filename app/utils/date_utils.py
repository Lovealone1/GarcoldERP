from __future__ import annotations

import calendar
from datetime import date, datetime, time
from typing import NamedTuple, Optional
from zoneinfo import ZoneInfo

#: The business runs on Colombian time. The server does not: on Railway it is
#: UTC, where 7pm in Bogota is already the next calendar day. Resolving "this
#: month" against the server clock would move the default period a day early
#: every evening, so every calendar boundary here is computed in this zone.
BOGOTA = ZoneInfo("America/Bogota")


def now_colombian_time() -> datetime:
    """Returns the current datetime in the America/Bogota timezone."""
    return datetime.now(BOGOTA)


class PeriodError(ValueError):
    """A calendar selector that cannot be resolved into a range."""


class Period(NamedTuple):
    """An inclusive [date_from, date_to]; either end may be None (open)."""

    date_from: Optional[datetime]
    date_to: Optional[datetime]


def _start_of(day: date) -> datetime:
    return datetime.combine(day, time.min).replace(tzinfo=BOGOTA)


def _end_of(day: date) -> datetime:
    # The filters compare with <=, so the upper bound is the last instant of
    # the day rather than midnight of the next one.
    return datetime.combine(day, time.max).replace(tzinfo=BOGOTA)


def _whole_month(year: int, month: int) -> Period:
    last = calendar.monthrange(year, month)[1]
    return Period(_start_of(date(year, month, 1)), _end_of(date(year, month, last)))


def resolve_period(
    *,
    year: Optional[int] = None,
    month: Optional[int] = None,
    day: Optional[int] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    today: Optional[date] = None,
) -> Period:
    """
    Turn a calendar selector into the range the filters actually use.

    The screens ask for a year, a month or a single day; the repositories only
    understand `column >= date_from AND column <= date_to`. This is the one
    place that translates between the two, so month lengths, leap years and the
    Bogota offset are worked out once instead of in every caller.

    Missing coarser units are filled from today, so `day=5` means the fifth of
    the current month and `month=3` means March of the current year. One rule,
    no special cases.

    With nothing supplied at all the answer is the current month. It used to be
    every record ever written, which is why a screen's total read as the whole
    history of the business instead of the period on display.

    `date_from`/`date_to` stay available for an arbitrary range, but combining
    them with a calendar selector raises: the two describe the same thing, and
    silently letting one win is how a filter ends up reporting a period nobody
    asked for.
    """
    calendar_selector = any(v is not None for v in (year, month, day))
    free_range = date_from is not None or date_to is not None

    if calendar_selector and free_range:
        raise PeriodError(
            "Pass either year/month/day or date_from/date_to, not both: "
            "they describe the same range."
        )

    if free_range:
        if date_from is not None and date_to is not None and date_from > date_to:
            date_from, date_to = date_to, date_from
        return Period(date_from, date_to)

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
        return Period(_start_of(target), _end_of(target))

    if month is not None:
        return _whole_month(year if year is not None else ref.year, month)

    if year is not None:
        return Period(_start_of(date(year, 1, 1)), _end_of(date(year, 12, 31)))

    return _whole_month(ref.year, ref.month)
