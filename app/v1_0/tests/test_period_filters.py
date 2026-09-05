"""
Calendar granularity on the filtered list and summary endpoints.

The totals these endpoints report used to cover every record ever written,
because with no date parameters the filter set was empty. A screen showing
September therefore printed the whole history of the business as its total.

`resolve_period` is the single translation from what the screens ask for
(a year, a month, a day) into what the repositories understand
(`column >= date_from AND column <= date_to`), so month lengths, leap years
and the Bogota offset are decided in one place.
"""

import dataclasses
from datetime import date, datetime, timezone

import pytest
from fastapi.routing import APIRoute

from app.utils.date_utils import BOGOTA, Period, PeriodError, resolve_period
from app.v1_0.routers.period_params import period_dto, totals_with_period
from app.v1_0.v1_router import v1_router

#: Fixed reference so "the current month" is assertable.
TODAY = date(2026, 9, 5)

#: Every endpoint that resolves a period, as (path, method).
PERIOD_ENDPOINTS = [
    "/v1/sales",
    "/v1/sales/summary",
    "/v1/purchases/",
    "/v1/purchases/summary",
    "/v1/expenses/page",
    "/v1/expenses/summary",
    "/v1/transactions",
    "/v1/transactions/summary",
    "/v1/profits/",
    "/v1/profits/summary",
]

PERIOD_PARAMS = {"year", "month", "day", "date_from", "date_to"}


def _bogota(y, m, d, *, end=False):
    return datetime(
        y, m, d, 23, 59, 59, 999999 if end else 0, tzinfo=BOGOTA
    ) if end else datetime(y, m, d, 0, 0, 0, tzinfo=BOGOTA)


class TestGranularity:
    def test_no_parameters_is_the_current_month_not_all_history(self):
        got = resolve_period(today=TODAY)
        assert got.date_from == _bogota(2026, 9, 1)
        assert got.date_to == _bogota(2026, 9, 30, end=True)

    def test_year_covers_the_whole_year(self):
        got = resolve_period(year=2026, today=TODAY)
        assert got.date_from == _bogota(2026, 1, 1)
        assert got.date_to == _bogota(2026, 12, 31, end=True)

    def test_year_and_month_covers_that_month(self):
        got = resolve_period(year=2026, month=2, today=TODAY)
        assert got.date_from == _bogota(2026, 2, 1)
        assert got.date_to == _bogota(2026, 2, 28, end=True)

    def test_february_in_a_leap_year_has_29_days(self):
        got = resolve_period(year=2024, month=2, today=TODAY)
        assert got.date_to == _bogota(2024, 2, 29, end=True)

    def test_a_single_day_starts_and_ends_on_that_day(self):
        got = resolve_period(year=2026, month=9, day=5, today=TODAY)
        assert got.date_from == _bogota(2026, 9, 5)
        assert got.date_to == _bogota(2026, 9, 5, end=True)

    @pytest.mark.parametrize(
        "kwargs, expected_from",
        [
            ({"month": 3}, date(2026, 3, 1)),          # year filled from today
            ({"day": 7}, date(2026, 9, 7)),            # year and month filled
            ({"year": 2025, "day": 7}, date(2025, 9, 7)),  # month filled
        ],
    )
    def test_missing_coarser_units_are_filled_from_today(self, kwargs, expected_from):
        got = resolve_period(today=TODAY, **kwargs)
        assert got.date_from.date() == expected_from

    def test_the_range_is_expressed_in_bogota_not_utc(self):
        """
        The server runs in UTC on Railway. Resolving against the server clock
        would shift the period a day every evening after 7pm local.
        """
        got = resolve_period(year=2026, month=9, day=5, today=TODAY)
        assert got.date_from.utcoffset().total_seconds() == -5 * 3600


class TestFreeRange:
    def test_an_explicit_range_passes_through(self):
        a = datetime(2020, 1, 1, tzinfo=timezone.utc)
        b = datetime(2021, 1, 1, tzinfo=timezone.utc)
        assert resolve_period(date_from=a, date_to=b, today=TODAY) == Period(a, b)

    def test_an_open_ended_range_stays_open(self):
        a = datetime(2020, 1, 1, tzinfo=timezone.utc)
        assert resolve_period(date_from=a, today=TODAY) == Period(a, None)

    def test_a_reversed_range_is_swapped(self):
        a = datetime(2021, 1, 1, tzinfo=timezone.utc)
        b = datetime(2020, 1, 1, tzinfo=timezone.utc)
        assert resolve_period(date_from=a, date_to=b, today=TODAY) == Period(b, a)


class TestRejected:
    def test_a_calendar_selector_cannot_be_combined_with_a_free_range(self):
        """
        Both describe the same range. Letting one silently win is how a filter
        ends up reporting a period nobody asked for.
        """
        with pytest.raises(PeriodError, match="only one period selector"):
            resolve_period(
                year=2026,
                date_from=datetime(2020, 1, 1, tzinfo=timezone.utc),
                today=TODAY,
            )

    def test_a_day_that_does_not_exist_in_the_month_is_rejected(self):
        with pytest.raises(PeriodError, match="does not exist"):
            resolve_period(year=2026, month=2, day=30, today=TODAY)

    def test_february_29_is_rejected_in_a_non_leap_year(self):
        with pytest.raises(PeriodError, match="does not exist"):
            resolve_period(year=2026, month=2, day=29, today=TODAY)

    def test_february_29_is_accepted_in_a_leap_year(self):
        got = resolve_period(year=2024, month=2, day=29, today=TODAY)
        assert got.date_from.date() == date(2024, 2, 29)

    def test_an_out_of_range_month_is_rejected(self):
        with pytest.raises(PeriodError, match="between 1 and 12"):
            resolve_period(month=13, today=TODAY)


class TestEveryEndpointExposesIt:
    """
    Asserted across the surface rather than per endpoint: the point of the
    shared dependency is that the frontend can send the same parameters to
    every resource, which only holds if none of them was missed.
    """

    def _routes(self):
        return {
            r.path: r
            for r in v1_router.routes
            if isinstance(r, APIRoute) and "GET" in r.methods
        }

    def _query_params(self, dependant):
        """
        Collect query params including those contributed by sub-dependencies.

        The period parameters reach an endpoint through Depends(period_range),
        so they are not on the endpoint's own dependant.
        """
        found = list(dependant.query_params)
        for sub in dependant.dependencies:
            found.extend(self._query_params(sub))
        return found

    @pytest.mark.parametrize("path", PERIOD_ENDPOINTS)
    def test_the_endpoint_accepts_the_period_parameters(self, path):
        route = self._routes().get(path)
        assert route is not None, f"{path} is not a registered GET route"
        names = {p.name for p in self._query_params(route.dependant)}
        missing = PERIOD_PARAMS - names
        assert not missing, f"{path} is missing {sorted(missing)}"

    def test_no_endpoint_takes_an_optional_date_range_without_granularity(self):
        """
        An *optional* date range with no calendar selector is what produced the
        original defect: send nothing and the filter set is empty, so the
        endpoint reports every record ever written.

        A required range (products/top) cannot fall back to all history, so it
        is not part of this class of bug.
        """
        offenders = []
        for path, route in self._routes().items():
            params = {p.name: p for p in self._query_params(route.dependant)}
            dates = [params[n] for n in ("date_from", "date_to") if n in params]
            if not dates or any(p.required for p in dates):
                continue
            if not {"year", "month", "day"} <= set(params):
                offenders.append(path)
        assert not offenders, (
            "optional date range with no calendar granularity: " f"{offenders}"
        )


class TestAllTime:
    """
    All history is still reachable, but only by name.

    Utilidades reports "what the business has made", not "this month". Before
    this it got that by sending nothing, which is exactly the defect; now it
    has to ask, so the intent shows up in the logs instead of being an absent
    parameter.
    """

    def test_period_all_returns_an_unbounded_range(self):
        got = resolve_period(all_time=True, today=TODAY)
        assert got == Period(None, None, "all")

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"year": 2026},
            {"month": 9},
            {"day": 5},
            {"date_from": datetime(2020, 1, 1, tzinfo=timezone.utc)},
        ],
    )
    def test_all_time_cannot_be_combined_with_another_selector(self, kwargs):
        with pytest.raises(PeriodError, match="only one period selector"):
            resolve_period(all_time=True, today=TODAY, **kwargs)


class TestResolvedFrom:
    """
    The response says which selector produced the range.

    A client cannot derive the label from its own clock: boundaries are
    resolved in Bogota and the browser runs in the viewer's zone.
    """

    @pytest.mark.parametrize(
        "kwargs, expected",
        [
            ({}, "default"),
            ({"year": 2026}, "calendar"),
            ({"year": 2026, "month": 9}, "calendar"),
            ({"year": 2026, "month": 9, "day": 5}, "calendar"),
            ({"date_from": date(2020, 1, 1)}, "range"),
            ({"all_time": True}, "all"),
        ],
    )
    def test_it_reports_the_selector_it_used(self, kwargs, expected):
        assert resolve_period(today=TODAY, **kwargs).resolved_from == expected


class TestDateOnlyBounds:
    """
    A bare date means the whole calendar day in Bogota.

    The frontend built its range with JS `.toISOString()`, which is always
    UTC: an upper bound of `2026-09-30` became `2026-09-30T05:00:00Z`, i.e.
    midnight in Bogota, silently dropping that entire day's records. A sale at
    20:00 on the 30th is 01:00 UTC on the 1st, and it went missing.
    """

    def test_a_bare_date_lower_bound_is_the_start_of_that_day(self):
        got = resolve_period(date_from=date(2026, 9, 1), today=TODAY)
        assert got.date_from == _bogota(2026, 9, 1)

    def test_a_bare_date_upper_bound_is_the_END_of_that_day(self):
        got = resolve_period(date_to=date(2026, 9, 30), today=TODAY)
        assert got.date_to == _bogota(2026, 9, 30, end=True)

    def test_a_late_evening_sale_falls_inside_a_bare_date_bound(self):
        """The row that used to go missing at a month edge."""
        got = resolve_period(
            date_from=date(2026, 9, 1), date_to=date(2026, 9, 30), today=TODAY
        )
        sale = datetime(2026, 9, 30, 20, 0, tzinfo=BOGOTA)
        assert got.date_from <= sale <= got.date_to

    def test_a_naive_timestamp_is_read_in_bogota_not_utc(self):
        got = resolve_period(date_from=datetime(2026, 9, 1, 8, 0), today=TODAY)
        assert got.date_from.utcoffset().total_seconds() == -5 * 3600

    def test_an_aware_timestamp_is_used_as_the_exact_instant(self):
        exact = datetime(2026, 9, 1, 5, 0, tzinfo=timezone.utc)
        assert resolve_period(date_from=exact, today=TODAY).date_from == exact


class TestTheResponseEchoesThePeriod:
    """
    Both the list envelope and the summary carry the resolved range, so a
    screen can label what it is showing without re-deriving it.
    """

    def _page_dto_fields(self):
        from app.v1_0.entities.page import PageDTO

        return {f.name for f in dataclasses.fields(PageDTO)}

    def test_the_pagination_envelope_carries_a_period(self):
        assert "period" in self._page_dto_fields()

    def test_the_period_is_optional_so_unrelated_pages_still_build(self):
        """
        Customers, suppliers and products share the same envelope and resolve
        no period; the field has to default rather than become required.
        """
        from app.v1_0.entities.page import PageDTO

        page = PageDTO(
            items=[], page=1, page_size=8, total=0, total_pages=1,
            has_next=False, has_prev=False,
        )
        assert page.period is None

    def test_the_summary_keeps_its_flat_totals_alongside_the_period(self):
        """A caller reading `total` or `count` must be unaffected."""
        body = totals_with_period({"total": 1500.0, "count": 12}, resolve_period(today=TODAY))
        assert body["total"] == 1500.0
        assert body["count"] == 12
        assert body["period"].resolved_from == "default"

    def test_the_echoed_range_matches_what_was_resolved(self):
        period = resolve_period(year=2026, month=9, today=TODAY)
        dto = period_dto(period)
        assert (dto.date_from, dto.date_to) == (period.date_from, period.date_to)
        assert dto.resolved_from == "calendar"
