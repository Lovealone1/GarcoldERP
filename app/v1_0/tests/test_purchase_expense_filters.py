"""
Server-side filtering for purchases and expenses.

Purchases were filtered in the browser after downloading every page. Expenses
were worse: the client sent the filters, the endpoint ignored them, and the
screen filtered only the eight rows it was showing -- so the visible result and
its pagination disagreed with each other.
"""

from datetime import datetime
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.dialects import postgresql

from app.v1_0.repositories.expense_repository import (
    ExpenseRepository,
    build_expense_filters,
)
from app.v1_0.repositories.purchase_repository import (
    PurchaseRepository,
    build_purchase_filters,
)
from app.v1_0.routers.expense_router import (
    expense_filter_options,
    expense_summary,
    list_expenses_paginated,
)
from app.v1_0.routers.purchase_router import (
    list_purchases,
    purchase_filter_options,
    purchase_summary,
)
from app.v1_0.services import ExpenseService, PurchaseService
from app.utils.date_utils import Period


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
# PURCHASES
# =========================================================================== #
class TestPurchaseFilters:
    def test_no_filters_produces_nothing(self):
        assert build_purchase_filters() == []

    @pytest.mark.parametrize("blank", ["", "   ", None])
    def test_blank_search_adds_nothing(self, blank):
        assert build_purchase_filters(q=blank) == []

    def test_search_covers_supplier_bank_and_status(self):
        rendered = sql_all(build_purchase_filters(q="acme")).lower()
        assert "%acme%" in rendered
        assert rendered.count("exists") >= 3

    def test_numeric_search_also_matches_the_purchase_number(self):
        assert "= 12" in sql_all(build_purchase_filters(q="12"))

    def test_supplier_filters_by_name(self):
        assert "Acme" in sql_all(build_purchase_filters(supplier="Acme"))

    def test_status_and_bank_filter_by_name(self):
        rendered = sql_all(build_purchase_filters(status="Credito", bank="Nequi"))
        assert "Credito" in rendered
        assert "Nequi" in rendered

    def test_the_date_range_uses_purchase_date(self):
        rendered = sql_all(
            build_purchase_filters(
                date_from=datetime(2026, 1, 1), date_to=datetime(2026, 2, 1)
            )
        )
        assert "purchase_date" in rendered
        assert ">=" in rendered and "<=" in rendered

    def test_filters_stack(self):
        assert len(
            build_purchase_filters(
                q="acme",
                status="Credito",
                bank="Nequi",
                supplier="Acme",
                date_from=datetime(2026, 1, 1),
                date_to=datetime(2026, 2, 1),
            )
        ) == 6

    async def test_the_pinned_row_is_dropped_when_filtering(self, mocker):
        keyset = mocker.patch(
            "app.v1_0.repositories.purchase_repository.list_paginated_keyset",
            new_callable=AsyncMock,
            return_value=([], 0, False),
        )
        await PurchaseRepository().list_paginated(session=None, offset=0, limit=8)
        assert keyset.await_args.kwargs["pin_enabled"] is True

        await PurchaseRepository().list_paginated(
            session=None, offset=0, limit=8, bank="Nequi"
        )
        assert keyset.await_args.kwargs["pin_enabled"] is False


class TestPurchaseService:
    def _service(self, repo):
        s = PurchaseService.__new__(PurchaseService)
        s.purchase_repository = repo
        s.PAGE_SIZE = 8
        s.MAX_PAGE_SIZE = 100
        return s

    async def test_page_size_defaults_and_clamps(self, mocker):
        repo = mocker.Mock()
        repo.list_paginated = AsyncMock(return_value=([], 0, False))
        svc = self._service(repo)

        await svc.list_purchases(1, None)
        assert repo.list_paginated.await_args.kwargs["limit"] == 8

        await svc.list_purchases(1, None, page_size=50)
        assert repo.list_paginated.await_args.kwargs["limit"] == 50

        await svc.list_purchases(1, None, page_size=10_000)
        assert repo.list_paginated.await_args.kwargs["limit"] == 100

    async def test_forwards_filters(self, mocker):
        repo = mocker.Mock()
        repo.list_paginated = AsyncMock(return_value=([], 0, False))
        await self._service(repo).list_purchases(
            1, None, q="acme", status="Credito", bank="Nequi", supplier="Acme"
        )
        kwargs = repo.list_paginated.await_args.kwargs
        assert kwargs["q"] == "acme"
        assert kwargs["supplier"] == "Acme"


class TestPurchaseRouter:
    async def test_status_alias_maps_through(self, mocker):
        service = mocker.Mock()
        service.list_purchases = AsyncMock(return_value=mocker.Mock())

        await list_purchases(
            page=1,
            page_size=None,
            q=None,
            status_name="Credito",
            bank=None,
            supplier=None,
            period=Period(None, None),
            db=None,
            service=service,
        )

        assert service.list_purchases.await_args.kwargs["status"] == "Credito"

    async def test_summary_and_options(self, mocker):
        service = mocker.Mock()
        service.summarize_purchases = AsyncMock(
            return_value={"total": 900.0, "balance": 100.0, "count": 4}
        )
        service.list_filter_options = AsyncMock(
            return_value={"banks": ["Nequi"], "statuses": ["Credito"], "suppliers": ["Acme"]}
        )

        summary = await purchase_summary(
            q=None,
            status_name=None,
            bank=None,
            supplier=None,
            period=Period(None, None),
            db=None,
            service=service,
        )
        options = await purchase_filter_options(db=None, service=service)

        assert summary["total"] == 900.0
        assert options["suppliers"] == ["Acme"]


# =========================================================================== #
# EXPENSES
# =========================================================================== #
class TestExpenseFilters:
    def test_no_filters_produces_nothing(self):
        assert build_expense_filters() == []

    def test_category_and_bank_filter_by_name(self):
        rendered = sql_all(build_expense_filters(category="Arriendo", bank="Nequi"))
        assert "Arriendo" in rendered
        assert "Nequi" in rendered

    def test_search_covers_category_and_bank(self):
        rendered = sql_all(build_expense_filters(q="arri")).lower()
        assert "%arri%" in rendered
        assert rendered.count("exists") >= 2

    def test_numeric_search_also_matches_the_id(self):
        assert "= 5" in sql_all(build_expense_filters(q="5"))

    def test_the_date_range_uses_expense_date(self):
        rendered = sql_all(
            build_expense_filters(
                date_from=datetime(2026, 1, 1), date_to=datetime(2026, 2, 1)
            )
        )
        assert "expense_date" in rendered

    @pytest.mark.parametrize("blank", ["", "  ", None])
    def test_blank_values_add_nothing(self, blank):
        assert build_expense_filters(q=blank, category=blank, bank=blank) == []

    async def test_the_pinned_row_is_dropped_when_filtering(self, mocker):
        keyset = mocker.patch(
            "app.v1_0.repositories.expense_repository.list_paginated_keyset",
            new_callable=AsyncMock,
            return_value=([], 0, False),
        )
        await ExpenseRepository().list_paginated(session=None, offset=0, limit=8)
        assert keyset.await_args.kwargs["pin_enabled"] is True

        await ExpenseRepository().list_paginated(
            session=None, offset=0, limit=8, category="Arriendo"
        )
        assert keyset.await_args.kwargs["pin_enabled"] is False


class TestExpenseRouter:
    # The client already sent these; the endpoint used to ignore them.
    async def test_filters_reach_the_service(self, mocker):
        service = mocker.Mock()
        service.list_paginated = AsyncMock(return_value=mocker.Mock())

        await list_expenses_paginated(
            page=2,
            page_size=20,
            q="arri",
            category="Arriendo",
            bank="Nequi",
            period=Period(datetime(2026, 1, 1), datetime(2026, 2, 1)),
            db=None,
            service=service,
        )

        kwargs = service.list_paginated.await_args.kwargs
        assert kwargs["q"] == "arri"
        assert kwargs["category"] == "Arriendo"
        assert kwargs["bank"] == "Nequi"
        assert kwargs["page_size"] == 20
        assert kwargs["date_from"] == datetime(2026, 1, 1)

    async def test_summary_and_options(self, mocker):
        service = mocker.Mock()
        service.summarize_expenses = AsyncMock(return_value={"total": 250.0, "count": 3})
        service.list_filter_options = AsyncMock(
            return_value={"categories": ["Arriendo"], "banks": ["Nequi"]}
        )

        summary = await expense_summary(
            q=None, category=None, bank=None, period=Period(None, None),
            db=None, service=service,
        )
        options = await expense_filter_options(db=None, service=service)

        assert summary["total"] == 250.0
        assert options["categories"] == ["Arriendo"]


class TestWhitespaceNormalisation:
    """
    A form field holding only spaces means "no filter", not "match a name made
    of spaces". Free-text search already trimmed; the exact-match filters did
    not, so clearing a dropdown to whitespace silently returned nothing.
    """

    @pytest.mark.parametrize("blank", ["", "   ", "	", None])
    def test_transactions(self, blank):
        from app.v1_0.repositories.transaction_repository import (
            build_transaction_filters,
        )

        # Only the pinned-row exclusion survives.
        assert len(build_transaction_filters(bank=blank, type_name=blank, q=blank)) == 1

    @pytest.mark.parametrize("blank", ["", "   ", "	", None])
    def test_sales(self, blank):
        from app.v1_0.repositories.sale_repository import build_sale_filters

        assert build_sale_filters(status=blank, bank=blank, q=blank) == []

    @pytest.mark.parametrize("blank", ["", "   ", "	", None])
    def test_purchases(self, blank):
        assert (
            build_purchase_filters(status=blank, bank=blank, supplier=blank, q=blank)
            == []
        )

    @pytest.mark.parametrize("blank", ["", "   ", "	", None])
    def test_expenses(self, blank):
        assert build_expense_filters(category=blank, bank=blank, q=blank) == []

    def test_a_real_value_with_padding_is_still_matched(self):
        assert "Nequi" in sql_all(build_expense_filters(bank="  Nequi  "))
