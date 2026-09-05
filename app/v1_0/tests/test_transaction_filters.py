"""
Server-side filtering for the transactions list.

The screen used to download every page and filter in the browser -- hundreds
of sequential requests to show eight rows. These tests cover the SQL the
filters compile to, the page_size contract, and the router's parameter
mapping.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.dialects import postgresql

from app.v1_0.entities import TransactionPageDTO
from app.v1_0.repositories.transaction_repository import build_transaction_filters
from app.v1_0.routers.transaction_router import (
    list_transactions,
    transaction_filter_options,
)
from app.v1_0.services import TransactionService


def sql(expression) -> str:
    """Compiled SQL for one filter expression, with literals inlined."""
    return str(
        expression.compile(
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
        )
    )


def sql_all(filters) -> str:
    return " AND ".join(sql(f) for f in filters)


class TestNoFilters:
    def test_only_the_pinned_row_exclusion(self):
        filters = build_transaction_filters()
        assert len(filters) == 1
        # id == -1 is the synthetic opening-balance row.
        assert "-1" in sql(filters[0])

    @pytest.mark.parametrize("blank", ["", "   ", None])
    def test_a_blank_search_term_adds_nothing(self, blank):
        assert len(build_transaction_filters(q=blank)) == 1

    def test_origin_all_is_not_a_filter(self):
        # "all" is the UI's word for no filter; it must not become a WHERE.
        assert len(build_transaction_filters(origin="all")) == 1


class TestSearchTerm:
    def test_searches_description_bank_and_type(self):
        rendered = sql_all(build_transaction_filters(q="nequi"))
        assert "description" in rendered.lower()
        assert "%nequi%" in rendered
        # bank and type are matched through their relationships
        assert rendered.lower().count("exists") >= 2

    def test_is_case_insensitive(self):
        assert "ILIKE" in sql_all(build_transaction_filters(q="Nequi")).upper()

    def test_a_numeric_term_also_matches_the_row_id(self):
        # The UI lets you search by id.
        rendered = sql_all(build_transaction_filters(q="42"))
        assert "= 42" in rendered

    def test_a_non_numeric_term_does_not_match_ids(self):
        assert "bank_transaction.id = " not in sql_all(build_transaction_filters(q="abc"))

    def test_the_term_is_trimmed(self):
        assert "%nequi%" in sql_all(build_transaction_filters(q="  nequi  "))

    def test_a_term_with_a_wildcard_is_passed_through_as_data(self):
        # Bound as a literal, never concatenated into the statement.
        rendered = sql_all(build_transaction_filters(q="100%"))
        assert "%100%%" in rendered or "100%" in rendered


class TestExactFilters:
    def test_bank_matches_by_name(self):
        rendered = sql_all(build_transaction_filters(bank="Bancolombia"))
        assert "Bancolombia" in rendered
        assert "bank" in rendered.lower()

    def test_type_matches_by_name(self):
        assert "Ingreso" in sql_all(build_transaction_filters(type_name="Ingreso"))

    def test_origin_auto(self):
        rendered = sql_all(build_transaction_filters(origin="auto")).lower()
        assert "is_auto" in rendered
        assert "true" in rendered

    def test_origin_manual(self):
        rendered = sql_all(build_transaction_filters(origin="manual")).lower()
        assert "is_auto" in rendered
        assert "false" in rendered

    def test_an_unknown_origin_is_ignored(self):
        assert len(build_transaction_filters(origin="nonsense")) == 1


class TestDateRange:
    def test_from_and_to_bound_both_ends(self):
        filters = build_transaction_filters(
            date_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
            date_to=datetime(2026, 1, 31, tzinfo=timezone.utc),
        )
        rendered = sql_all(filters)
        assert ">=" in rendered
        assert "<=" in rendered

    def test_an_open_ended_range_is_allowed(self):
        assert len(build_transaction_filters(date_from=datetime(2026, 1, 1))) == 2
        assert len(build_transaction_filters(date_to=datetime(2026, 1, 1))) == 2


class TestCombining:
    def test_filters_stack(self):
        filters = build_transaction_filters(
            q="pago",
            bank="Nequi",
            type_name="Egreso",
            origin="manual",
            date_from=datetime(2026, 1, 1),
            date_to=datetime(2026, 2, 1),
        )
        # pinned-row exclusion + bank + type + origin + from + to + search
        assert len(filters) == 7


class TestPinnedRow:
    async def test_the_opening_balance_row_is_pinned_on_an_unfiltered_page(self, mocker):
        from app.v1_0.repositories.transaction_repository import TransactionRepository

        keyset = mocker.patch(
            "app.v1_0.repositories.transaction_repository.list_paginated_keyset",
            new_callable=AsyncMock,
            return_value=([], 0, False),
        )

        await TransactionRepository().list_paginated(session=None, offset=0, limit=8)

        assert keyset.await_args.kwargs["pin_enabled"] is True

    async def test_it_is_not_pinned_inside_a_filtered_result(self, mocker):
        # Pinning it would add a row that does not match the filter and inflate
        # the reported total.
        from app.v1_0.repositories.transaction_repository import TransactionRepository

        keyset = mocker.patch(
            "app.v1_0.repositories.transaction_repository.list_paginated_keyset",
            new_callable=AsyncMock,
            return_value=([], 0, False),
        )

        await TransactionRepository().list_paginated(
            session=None, offset=0, limit=8, bank="Nequi"
        )

        assert keyset.await_args.kwargs["pin_enabled"] is False


class TestServicePageSize:
    def _service(self, repo):
        service = TransactionService.__new__(TransactionService)
        service.tx_repo = repo
        service.PAGE_SIZE = 8
        service.MAX_PAGE_SIZE = 100
        return service

    async def test_defaults_to_the_configured_page_size(self, mocker):
        repo = mocker.Mock()
        repo.list_paginated = AsyncMock(return_value=([], 0, False))
        service = self._service(repo)

        await service.list_transactions(1, None)

        assert repo.list_paginated.await_args.kwargs["limit"] == 8

    async def test_honours_a_client_supplied_page_size(self, mocker):
        repo = mocker.Mock()
        repo.list_paginated = AsyncMock(return_value=([], 0, False))
        service = self._service(repo)

        await service.list_transactions(1, None, page_size=25)

        assert repo.list_paginated.await_args.kwargs["limit"] == 25

    async def test_clamps_an_oversized_page_size(self, mocker):
        # Otherwise one request could ask for the whole table and undo the
        # point of paginating at all.
        repo = mocker.Mock()
        repo.list_paginated = AsyncMock(return_value=([], 0, False))
        service = self._service(repo)

        await service.list_transactions(1, None, page_size=100_000)

        assert repo.list_paginated.await_args.kwargs["limit"] == 100

    async def test_offset_follows_the_effective_page_size(self, mocker):
        repo = mocker.Mock()
        repo.list_paginated = AsyncMock(return_value=([], 0, False))
        service = self._service(repo)

        await service.list_transactions(3, None, page_size=20)

        assert repo.list_paginated.await_args.kwargs["offset"] == 40

    async def test_forwards_every_filter(self, mocker):
        repo = mocker.Mock()
        repo.list_paginated = AsyncMock(return_value=([], 0, False))
        service = self._service(repo)

        await service.list_transactions(
            1,
            None,
            q="pago",
            bank="Nequi",
            type_name="Egreso",
            origin="manual",
            date_from=datetime(2026, 1, 1),
            date_to=datetime(2026, 2, 1),
        )

        kwargs = repo.list_paginated.await_args.kwargs
        assert kwargs["q"] == "pago"
        assert kwargs["bank"] == "Nequi"
        assert kwargs["type_name"] == "Egreso"
        assert kwargs["origin"] == "manual"
        assert kwargs["date_from"] == datetime(2026, 1, 1)
        assert kwargs["date_to"] == datetime(2026, 2, 1)

    async def test_reports_pagination_metadata_from_the_filtered_total(self, mocker):
        repo = mocker.Mock()
        repo.list_paginated = AsyncMock(return_value=([], 42, True))
        service = self._service(repo)

        result: TransactionPageDTO = await service.list_transactions(2, None, page_size=10)

        assert result.total == 42
        assert result.total_pages == 5
        assert result.page == 2
        assert result.has_next is True
        assert result.has_prev is True


class TestRouterMapping:
    async def test_origin_all_becomes_no_filter(self, mocker):
        service = mocker.Mock()
        service.list_transactions = AsyncMock(return_value=None)

        await list_transactions(
            page=1,
            page_size=None,
            q=None,
            bank=None,
            type=None,
            origin="all",
            date_from=None,
            date_to=None,
            db=None,
            service=service,
        )

        assert service.list_transactions.await_args.kwargs["origin"] is None

    @pytest.mark.parametrize("origin", ["auto", "manual"])
    async def test_a_real_origin_is_forwarded(self, mocker, origin):
        service = mocker.Mock()
        service.list_transactions = AsyncMock(return_value=None)

        await list_transactions(
            page=1,
            page_size=None,
            q=None,
            bank=None,
            type=None,
            origin=origin,
            date_from=None,
            date_to=None,
            db=None,
            service=service,
        )

        assert service.list_transactions.await_args.kwargs["origin"] == origin

    async def test_the_type_query_param_maps_to_type_name(self, mocker):
        # `type` shadows a builtin, so the service argument is named type_name.
        service = mocker.Mock()
        service.list_transactions = AsyncMock(return_value=None)

        await list_transactions(
            page=1,
            page_size=None,
            q=None,
            bank=None,
            type="Ingreso",
            origin="all",
            date_from=None,
            date_to=None,
            db=None,
            service=service,
        )

        assert service.list_transactions.await_args.kwargs["type_name"] == "Ingreso"


class TestFilterOptions:
    async def test_returns_the_names_present_in_the_data(self, mocker):
        service = mocker.Mock()
        service.list_filter_options = AsyncMock(
            return_value={"banks": ["Nequi"], "types": ["Ingreso", "Egreso"]}
        )

        result = await transaction_filter_options(db=None, service=service)

        assert result["banks"] == ["Nequi"]
        assert result["types"] == ["Ingreso", "Egreso"]
