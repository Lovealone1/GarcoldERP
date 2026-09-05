"""
Server-side filtering for customers, suppliers, products and profits.

All four screens downloaded the whole table and filtered the copy in memory.
These tests cover the SQL each filter compiles to and the page_size contract.
"""

from datetime import datetime
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.dialects import postgresql

from app.v1_0.repositories.customer_repository import build_customer_filters
from app.v1_0.repositories.product_repository import build_product_filters
from app.v1_0.repositories.profit_repository import build_profit_filters
from app.v1_0.repositories.supplier_repository import build_supplier_filters
from app.v1_0.services import (
    CustomerService,
    ProductService,
    ProfitService,
    SupplierService,
)


def sql_all(filters) -> str:
    return " AND ".join(
        str(
            f.compile(
                dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
            )
        )
        for f in filters
    )


# =========================================================================== #
# CUSTOMERS
# =========================================================================== #
class TestCustomerFilters:
    def test_no_filters(self):
        assert build_customer_filters() == []

    def test_search_covers_the_visible_columns(self):
        rendered = sql_all(build_customer_filters(q="perez")).lower()
        for column in ("name", "tax_id", "email", "phone", "city"):
            assert column in rendered
        assert "%perez%" in rendered

    def test_a_numeric_term_also_matches_the_id(self):
        assert "= 9" in sql_all(build_customer_filters(q="9"))

    # The city filter is a multi-select in the UI.
    def test_cities_become_an_in_clause(self):
        rendered = sql_all(build_customer_filters(cities=["Cali", "Bogota"]))
        assert "IN" in rendered.upper()
        assert "Cali" in rendered and "Bogota" in rendered

    def test_blank_cities_are_dropped(self):
        assert build_customer_filters(cities=["", "   ", None]) == []

    def test_a_mixed_city_list_keeps_the_real_ones(self):
        rendered = sql_all(build_customer_filters(cities=["Cali", "", "  "]))
        assert "Cali" in rendered

    def test_pending_balance_yes_and_no(self):
        assert "> 0" in sql_all(build_customer_filters(pending_balance="yes"))
        assert "<= 0" in sql_all(build_customer_filters(pending_balance="no"))

    def test_an_unknown_pending_balance_is_ignored(self):
        assert build_customer_filters(pending_balance="maybe") == []

    @pytest.mark.parametrize("blank", ["", "   ", None])
    def test_a_blank_term_is_ignored(self, blank):
        assert build_customer_filters(q=blank) == []

    def test_filters_stack(self):
        assert (
            len(
                build_customer_filters(
                    q="perez", cities=["Cali"], pending_balance="yes"
                )
            )
            == 3
        )


# =========================================================================== #
# SUPPLIERS
# =========================================================================== #
class TestSupplierFilters:
    def test_no_filters(self):
        assert build_supplier_filters() == []

    def test_search_covers_the_visible_columns(self):
        rendered = sql_all(build_supplier_filters(q="acme")).lower()
        for column in ("name", "tax_id", "email", "phone", "city"):
            assert column in rendered

    def test_cities_become_an_in_clause(self):
        assert "IN" in sql_all(build_supplier_filters(cities=["Cali"])).upper()

    @pytest.mark.parametrize("blank", ["", "   ", None])
    def test_a_blank_term_is_ignored(self, blank):
        assert build_supplier_filters(q=blank) == []


# =========================================================================== #
# PRODUCTS
# =========================================================================== #
class TestProductFilters:
    def test_no_filters(self):
        assert build_product_filters() == []

    def test_search_covers_reference_description_and_barcode(self):
        rendered = sql_all(build_product_filters(q="tor")).lower()
        assert "reference" in rendered
        assert "description" in rendered
        assert "barcode" in rendered

    def test_estado_activos_and_inactivos(self):
        assert "true" in sql_all(build_product_filters(estado="activos")).lower()
        assert "false" in sql_all(build_product_filters(estado="inactivos")).lower()

    def test_an_unknown_estado_is_ignored(self):
        # "todos" is the UI's word for no filter.
        assert build_product_filters(estado="todos") == []

    def test_a_numeric_term_also_matches_the_id(self):
        assert "= 3" in sql_all(build_product_filters(q="3"))


# =========================================================================== #
# PROFITS
# =========================================================================== #
class TestProfitFilters:
    def test_no_filters(self):
        assert build_profit_filters() == []

    def test_search_matches_the_sale_number_as_a_substring(self):
        # Matches what the client-side version did.
        rendered = sql_all(build_profit_filters(q="12"))
        assert "%12%" in rendered
        assert "sale_id" in rendered.lower()

    def test_the_date_range_bounds_both_ends(self):
        rendered = sql_all(
            build_profit_filters(
                date_from=datetime(2026, 1, 1), date_to=datetime(2026, 2, 1)
            )
        )
        assert ">=" in rendered and "<=" in rendered

    @pytest.mark.parametrize("blank", ["", "   ", None])
    def test_a_blank_term_is_ignored(self, blank):
        assert build_profit_filters(q=blank) == []


# =========================================================================== #
# page_size contract
# =========================================================================== #
class TestPageSizeContract:
    """Every list service must default, honour and clamp page_size alike."""

    @pytest.mark.parametrize(
        "service_cls,repo_attr,method",
        [
            (CustomerService, "customer_repository", "list_paginated"),
            (SupplierService, "supplier_repository", "list_paginated"),
            (ProductService, "product_repository", "list_paginated"),
            (ProfitService, "profit_repository", "list_profits"),
        ],
    )
    async def test_defaults_honours_and_clamps(
        self, mocker, service_cls, repo_attr, method
    ):
        repo = mocker.Mock()
        repo.list_paginated = AsyncMock(return_value=([], 0, False))
        # Profits resolve customer names for the page in one extra query.
        repo.customer_names_for = AsyncMock(return_value={})

        service = service_cls.__new__(service_cls)
        setattr(service, repo_attr, repo)
        service.PAGE_SIZE = 8
        service.MAX_PAGE_SIZE = 100

        call = getattr(service, method)

        await call(1, None)
        assert repo.list_paginated.await_args.kwargs["limit"] == 8

        await call(1, None, page_size=30)
        assert repo.list_paginated.await_args.kwargs["limit"] == 30

        # Without a ceiling a single request could ask for the whole table.
        await call(1, None, page_size=50_000)
        assert repo.list_paginated.await_args.kwargs["limit"] == 100

    @pytest.mark.parametrize(
        "service_cls,repo_attr,method",
        [
            (CustomerService, "customer_repository", "list_paginated"),
            (SupplierService, "supplier_repository", "list_paginated"),
            (ProductService, "product_repository", "list_paginated"),
            (ProfitService, "profit_repository", "list_profits"),
        ],
    )
    async def test_offset_follows_the_effective_page_size(
        self, mocker, service_cls, repo_attr, method
    ):
        repo = mocker.Mock()
        repo.list_paginated = AsyncMock(return_value=([], 0, False))
        repo.customer_names_for = AsyncMock(return_value={})

        service = service_cls.__new__(service_cls)
        setattr(service, repo_attr, repo)
        service.PAGE_SIZE = 8
        service.MAX_PAGE_SIZE = 100

        await getattr(service, method)(3, None, page_size=20)
        assert repo.list_paginated.await_args.kwargs["offset"] == 40


class TestProfitCustomerNames:
    """
    The utilidades screen downloaded every profit and then issued one
    getSaleById per sale just to show a customer name. The name now travels
    with the row, resolved for the page in a single query.
    """

    def _service(self, repo):
        s = ProfitService.__new__(ProfitService)
        s.profit_repository = repo
        s.PAGE_SIZE = 16
        s.MAX_PAGE_SIZE = 100
        return s

    async def test_the_name_is_resolved_once_for_the_whole_page(self, mocker):
        rows = [
            mocker.Mock(id=1, sale_id=10, profit=5.0, created_at=datetime(2026, 1, 1)),
            mocker.Mock(id=2, sale_id=11, profit=7.0, created_at=datetime(2026, 1, 2)),
            mocker.Mock(id=3, sale_id=10, profit=9.0, created_at=datetime(2026, 1, 3)),
        ]
        repo = mocker.Mock()
        repo.list_paginated = AsyncMock(return_value=(rows, 3, False))
        repo.customer_names_for = AsyncMock(return_value={10: "Perez", 11: "Gomez"})

        result = await self._service(repo).list_profits(1, None)

        repo.customer_names_for.assert_awaited_once()
        assert [i.customer for i in result.items] == ["Perez", "Gomez", "Perez"]

    async def test_an_unresolved_sale_yields_none_rather_than_failing(self, mocker):
        rows = [mocker.Mock(id=1, sale_id=99, profit=5.0, created_at=datetime(2026, 1, 1))]
        repo = mocker.Mock()
        repo.list_paginated = AsyncMock(return_value=(rows, 1, False))
        repo.customer_names_for = AsyncMock(return_value={})

        result = await self._service(repo).list_profits(1, None)

        assert result.items[0].customer is None

    async def test_search_also_matches_the_customer_name(self):
        rendered = sql_all(build_profit_filters(q="perez")).lower()
        assert "customer" in rendered
        assert "%perez%" in rendered
