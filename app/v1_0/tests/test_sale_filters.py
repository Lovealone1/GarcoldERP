"""
Server-side filtering for the sales list.

The screen used to walk every page to build a local copy and filter that.
These tests cover the SQL each filter compiles to, the page_size contract,
and the router's parameter mapping.
"""

from datetime import datetime
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.dialects import postgresql

from app.v1_0.entities import SalePageDTO
from app.v1_0.repositories.sale_repository import SaleRepository, build_sale_filters
from app.v1_0.routers.sale_router import list_sales, sale_filter_options, sale_summary
from app.v1_0.services import SaleService
from app.utils.date_utils import Period


def sql(expression) -> str:
    return str(
        expression.compile(
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
        )
    )


def sql_all(filters) -> str:
    return " AND ".join(sql(f) for f in filters)


class TestNoFilters:
    def test_nothing_is_added(self):
        assert build_sale_filters() == []

    @pytest.mark.parametrize("blank", ["", "   ", None])
    def test_a_blank_term_adds_nothing(self, blank):
        assert build_sale_filters(q=blank) == []

    @pytest.mark.parametrize("blank", ["", None])
    def test_blank_status_and_bank_add_nothing(self, blank):
        assert build_sale_filters(status=blank, bank=blank) == []


class TestSearchTerm:
    def test_searches_customer_bank_and_status(self):
        rendered = sql_all(build_sale_filters(q="perez")).lower()
        assert "%perez%" in rendered
        assert rendered.count("exists") >= 3

    def test_is_case_insensitive(self):
        assert "ILIKE" in sql_all(build_sale_filters(q="Perez")).upper()

    def test_a_numeric_term_also_matches_the_sale_number(self):
        assert "= 7" in sql_all(build_sale_filters(q="7"))

    def test_a_non_numeric_term_does_not_match_ids(self):
        assert "sale.id = " not in sql_all(build_sale_filters(q="perez"))

    def test_the_term_is_trimmed(self):
        assert "%perez%" in sql_all(build_sale_filters(q="  perez  "))


class TestExactFilters:
    def test_status_matches_by_name(self):
        assert "Cancelada" in sql_all(build_sale_filters(status="Cancelada"))

    def test_bank_matches_by_name(self):
        assert "Nequi" in sql_all(build_sale_filters(bank="Nequi"))

    def test_date_range_bounds_both_ends(self):
        rendered = sql_all(
            build_sale_filters(
                date_from=datetime(2026, 1, 1), date_to=datetime(2026, 2, 1)
            )
        )
        assert ">=" in rendered
        assert "<=" in rendered

    def test_filters_stack(self):
        filters = build_sale_filters(
            q="perez",
            status="Cancelada",
            bank="Nequi",
            date_from=datetime(2026, 1, 1),
            date_to=datetime(2026, 2, 1),
        )
        assert len(filters) == 5


class TestPinnedRow:
    async def test_pinned_on_an_unfiltered_page(self, mocker):
        keyset = mocker.patch(
            "app.v1_0.repositories.sale_repository.list_paginated_keyset",
            new_callable=AsyncMock,
            return_value=([], 0, False),
        )
        await SaleRepository().list_paginated(session=None, offset=0, limit=8)
        assert keyset.await_args.kwargs["pin_enabled"] is True

    async def test_not_pinned_inside_a_filtered_result(self, mocker):
        keyset = mocker.patch(
            "app.v1_0.repositories.sale_repository.list_paginated_keyset",
            new_callable=AsyncMock,
            return_value=([], 0, False),
        )
        await SaleRepository().list_paginated(session=None, offset=0, limit=8, bank="Nequi")
        assert keyset.await_args.kwargs["pin_enabled"] is False

    async def test_filters_reach_the_keyset_query(self, mocker):
        keyset = mocker.patch(
            "app.v1_0.repositories.sale_repository.list_paginated_keyset",
            new_callable=AsyncMock,
            return_value=([], 0, False),
        )
        await SaleRepository().list_paginated(
            session=None, offset=0, limit=8, status="Cancelada"
        )
        # pinned-row exclusion plus the status filter
        assert len(keyset.await_args.kwargs["base_filters"]) == 2


class TestServicePageSize:
    def _service(self, repo):
        service = SaleService.__new__(SaleService)
        service.sale_repository = repo
        service.PAGE_SIZE = 8
        service.MAX_PAGE_SIZE = 100
        return service

    async def test_defaults_to_the_configured_size(self, mocker):
        repo = mocker.Mock()
        repo.list_paginated = AsyncMock(return_value=([], 0, False))
        await self._service(repo).list_sales(1, None)
        assert repo.list_paginated.await_args.kwargs["limit"] == 8

    async def test_honours_a_client_supplied_size(self, mocker):
        repo = mocker.Mock()
        repo.list_paginated = AsyncMock(return_value=([], 0, False))
        await self._service(repo).list_sales(1, None, page_size=25)
        assert repo.list_paginated.await_args.kwargs["limit"] == 25

    async def test_clamps_an_oversized_size(self, mocker):
        repo = mocker.Mock()
        repo.list_paginated = AsyncMock(return_value=([], 0, False))
        await self._service(repo).list_sales(1, None, page_size=99_999)
        assert repo.list_paginated.await_args.kwargs["limit"] == 100

    async def test_offset_follows_the_effective_size(self, mocker):
        repo = mocker.Mock()
        repo.list_paginated = AsyncMock(return_value=([], 0, False))
        await self._service(repo).list_sales(4, None, page_size=10)
        assert repo.list_paginated.await_args.kwargs["offset"] == 30

    async def test_forwards_every_filter(self, mocker):
        repo = mocker.Mock()
        repo.list_paginated = AsyncMock(return_value=([], 0, False))
        await self._service(repo).list_sales(
            1,
            None,
            q="perez",
            status="Cancelada",
            bank="Nequi",
            date_from=datetime(2026, 1, 1),
            date_to=datetime(2026, 2, 1),
        )
        kwargs = repo.list_paginated.await_args.kwargs
        assert kwargs["q"] == "perez"
        assert kwargs["status"] == "Cancelada"
        assert kwargs["bank"] == "Nequi"

    async def test_pagination_metadata_reflects_the_filtered_total(self, mocker):
        repo = mocker.Mock()
        repo.list_paginated = AsyncMock(return_value=([], 33, True))
        result: SalePageDTO = await self._service(repo).list_sales(2, None, page_size=10)
        assert result.total == 33
        assert result.total_pages == 4
        assert result.has_next is True
        assert result.has_prev is True


class TestRouterMapping:
    async def test_the_status_query_param_maps_to_status(self, mocker):
        # `status` collides with the imported fastapi.status module in this
        # router, so the parameter is aliased.
        service = mocker.Mock()
        service.list_sales = AsyncMock(return_value=None)

        await list_sales(
            page=1,
            page_size=None,
            q=None,
            status_name="Cancelada",
            bank=None,
            period=Period(None, None),
            db=None,
            service=service,
        )

        assert service.list_sales.await_args.kwargs["status"] == "Cancelada"

    async def test_forwards_page_size_and_dates(self, mocker):
        service = mocker.Mock()
        service.list_sales = AsyncMock(return_value=None)

        await list_sales(
            page=2,
            page_size=20,
            q="x",
            status_name=None,
            bank="Nequi",
            period=Period(datetime(2026, 1, 1), datetime(2026, 2, 1)),
            db=None,
            service=service,
        )

        kwargs = service.list_sales.await_args.kwargs
        assert kwargs["page_size"] == 20
        assert kwargs["bank"] == "Nequi"
        assert kwargs["date_from"] == datetime(2026, 1, 1)


class TestSummaryAndOptions:
    async def test_summary_returns_totals(self, mocker):
        service = mocker.Mock()
        service.summarize_sales = AsyncMock(
            return_value={"total": 1500.0, "remaining_balance": 300.0, "count": 12}
        )

        result = await sale_summary(
            q=None,
            status_name=None,
            bank=None,
            period=Period(None, None),
            db=None,
            service=service,
        )

        assert result["total"] == 1500.0
        assert result["count"] == 12

    async def test_summary_forwards_the_filters(self, mocker):
        service = mocker.Mock()
        service.summarize_sales = AsyncMock(return_value={})

        await sale_summary(
            q="perez",
            status_name="Cancelada",
            bank="Nequi",
            period=Period(None, None),
            db=None,
            service=service,
        )

        kwargs = service.summarize_sales.await_args.kwargs
        assert kwargs["q"] == "perez"
        assert kwargs["status"] == "Cancelada"

    async def test_filter_options_are_returned(self, mocker):
        service = mocker.Mock()
        service.list_filter_options = AsyncMock(
            return_value={"banks": ["Nequi"], "statuses": ["Cancelada", "Credito"]}
        )

        result = await sale_filter_options(db=None, service=service)

        assert result["banks"] == ["Nequi"]
        assert result["statuses"] == ["Cancelada", "Credito"]
