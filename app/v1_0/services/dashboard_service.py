from datetime import date, timedelta, datetime
import calendar
import collections
from typing import Optional, Tuple, Mapping, Any, List, DefaultDict, Literal, Sequence
from sqlalchemy.ext.asyncio import AsyncSession

from app.v1_0.repositories import (
    SaleRepository, CustomerRepository,
    PurchaseRepository, SupplierRepository,
    BankRepository, ExpenseRepository, ProfitRepository,
    SaleItemRepository, ProductRepository,
    LoanRepository, InvestmentRepository,
)
from app.v1_0.entities import (
    Bucket as BucketDTO, 
    Granularity as GranularityDTO,
    RequestMetaDTO, SegmentMetaDTO,
    SalesSeriesItemDTO, SalesSeriesDTO, ARItemDTO, SalesBlockDTO,
    PurchasesSeriesItemDTO, PurchasesSeriesDTO, APItemDTO, PurchasesBlockDTO,
    ExpensesSeriesItemDTO, ExpensesSeriesDTO, ExpensesBlockDTO,
    ProfitSeriesItemDTO, ProfitSeriesDTO, ProfitBlockDTO,
    BankItemDTO, BanksSummaryDTO,
    TopProductItemDTO,
    CreditItemDTO, CreditsSummaryDTO,
    InvestmentItemDTO, InvestmentsSummaryDTO,
    FinalReportDTO,
)

class DashboardService:
    """
    English refactor of general report service.
    Sales & Profit segments are filterable by day / month / year.
    """

    def __init__(
        self,
        sale_repository: SaleRepository,
        customer_repository: CustomerRepository,
        purchase_repository: PurchaseRepository,
        supplier_repository: SupplierRepository,
        bank_repository: BankRepository,
        expense_repository: ExpenseRepository,
        profit_repository: ProfitRepository,
        sale_item_repository: SaleItemRepository,
        product_repository: ProductRepository,
        loan_repository: LoanRepository,
        investment_repository: InvestmentRepository,
    ) -> None:
        self.sale_repository = sale_repository
        self.customer_repository = customer_repository
        self.purchase_repository = purchase_repository
        self.supplier_repository = supplier_repository
        self.bank_repository = bank_repository
        self.expense_repository = expense_repository
        self.profit_repository = profit_repository
        self.sale_item_repository = sale_item_repository
        self.product_repository = product_repository
        self.loan_repository = loan_repository
        self.investment_repository = investment_repository


    def _compact(self, d: Mapping[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in d.items() if v is not None}

    async def _resolve_range(
        self,
        session: AsyncSession,
        bucket: BucketDTO,
        *,
        pivot: Optional[date] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        year: Optional[int] = None,
        month: Optional[int] = None,
        use_purchases: bool = False,
    ) -> Tuple[date, date]:
        today = pivot or date.today()

        if bucket == "week":
            if date_from and date_to:
                if date_from > date_to:
                    date_from, date_to = date_to, date_from
                return date_from, date_to
            end = today
            start = end - timedelta(days=6)
            return start, end

        if bucket == "month":
            y = year or today.year
            m = month or today.month
            start = date(y, m, 1)
            end = date(y, m, calendar.monthrange(y, m)[1])
            return start, end

        if bucket == "year":
            y = year or today.year
            return date(y, 1, 1), date(y, 12, 31)

        mn = await (self.purchase_repository.min_date(session=session) if use_purchases
                    else self.sale_repository.min_date(session=session))
        return (mn or today), today

    def _iter_days(self, start: date, end: date):
        d = start
        while d <= end:
            yield d
            d += timedelta(days=1)

    def _iter_months(self, start: date, end: date):
        y, m = start.year, start.month
        while (y < end.year) or (y == end.year and m <= end.month):
            yield (y, m)
            m += 1
            if m > 12:
                m = 1
                y += 1

    def _iter_years(self, start: date, end: date):
        for y in range(start.year, end.year + 1):
            yield y

    def _choose_granularity(self, bucket: BucketDTO, start: date, end: date) -> GranularityDTO:
        if bucket in ("week", "month"):
            return "day"
        if bucket == "year":
            return "month"
        years_span = end.year - start.year + 1
        return "year" if years_span >= 3 else "month"

    def _to_iso_date(self, raw: Any) -> Optional[str]:
        if raw is None:
            return None
        if isinstance(raw, datetime):
            return raw.date().isoformat()
        if isinstance(raw, date):
            return raw.isoformat()
        return str(raw)

    async def sales_segments(
        self,
        session: AsyncSession,
        *,
        bucket: BucketDTO,
        pivot: Optional[date] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        year: Optional[int] = None,
        month: Optional[int] = None,
    ) -> SalesSeriesDTO:
        start, end = await self._resolve_range(
            session, bucket, pivot=pivot, date_from=date_from, date_to=date_to, year=year, month=month
        )
        base = await self.sale_repository.sales_by_day(session=session, date_from=start, date_to=end)
        by_day = {r["date"]: {"total": float(r["total"]), "remaining_balance": float(r["remaining_balance"])} for r in base}

        gran: GranularityDTO = self._choose_granularity(bucket, start, end)
        series: List[SalesSeriesItemDTO] = []

        if gran == "day":
            for d in self._iter_days(start, end):
                k = d.isoformat()
                v = by_day.get(k, {"total": 0.0, "remaining_balance": 0.0})
                series.append(SalesSeriesItemDTO(date=k, total=v["total"], remaining_balance=v["remaining_balance"]))
        elif gran == "month":
            from collections import defaultdict
            agg = defaultdict(lambda: {"total": 0.0, "remaining_balance": 0.0})
            for k, v in by_day.items():
                mk = k[:7]
                agg[mk]["total"] += v["total"]
                agg[mk]["remaining_balance"] += v["remaining_balance"]
            for (y, m) in self._iter_months(start, end):
                mk = f"{y:04d}-{m:02d}"
                v = agg.get(mk, {"total": 0.0, "remaining_balance": 0.0})
                series.append(SalesSeriesItemDTO(date=mk, total=v["total"], remaining_balance=v["remaining_balance"]))
        else:
            from collections import defaultdict
            agg = defaultdict(lambda: {"total": 0.0, "remaining_balance": 0.0})
            for k, v in by_day.items():
                yk = k[:4]
                agg[yk]["total"] += v["total"]
                agg[yk]["remaining_balance"] += v["remaining_balance"]
            for y in self._iter_years(start, end):
                yk = f"{y:04d}"
                v = agg.get(yk, {"total": 0.0, "remaining_balance": 0.0})
                series.append(SalesSeriesItemDTO(date=yk, total=v["total"], remaining_balance=v["remaining_balance"]))

        meta = SegmentMetaDTO(
            bucket=bucket, granularity=gran, from_=start.isoformat(), to=end.isoformat(), segments=len(series)
        )
        return SalesSeriesDTO(meta=meta, series=series)

    async def accounts_receivable(self, session: AsyncSession) -> List[ARItemDTO]:
        rows = await self.sale_repository.accounts_receivable(session=session)
        cache: dict[int, str] = {}
        out: List[ARItemDTO] = []
        for r in rows:
            cid = r["customer_id"]
            name = cache.get(cid)
            if name is None:
                c = await self.customer_repository.get_by_id(cid, session=session)
                name = (getattr(c, "name", None) or "Desconocido") if c else "Desconocido"
                cache[cid] = name
            out.append(ARItemDTO(customer=name, total=float(r["total"]), remaining_balance=float(r["remaining_balance"]), date=r["date"]))
        return out

    async def purchases_segments(
        self,
        session: AsyncSession,
        *,
        bucket: BucketDTO,
        pivot: Optional[date] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        year: Optional[int] = None,
        month: Optional[int] = None,
    ) -> PurchasesSeriesDTO:
        start, end = await self._resolve_range(
            session, bucket, pivot=pivot, date_from=date_from, date_to=date_to, year=year, month=month, use_purchases=True
        )
        base = await self.purchase_repository.purchases_by_day(session=session, date_from=start, date_to=end)

        def k_of(r): f = r["date"]; return f.isoformat() if hasattr(f, "isoformat") else str(f)
        by_day = {k_of(r): {"total": float(r["total"]), "balance": float(r["balance"])} for r in base}

        gran: GranularityDTO = self._choose_granularity(bucket, start, end)
        series: List[PurchasesSeriesItemDTO] = []

        if gran == "day":
            for d in self._iter_days(start, end):
                k = d.isoformat()
                v = by_day.get(k, {"total": 0.0, "balance": 0.0})
                series.append(PurchasesSeriesItemDTO(date=k, total=v["total"], balance=v["balance"]))
        elif gran == "month":
            from collections import defaultdict
            agg = defaultdict(lambda: {"total": 0.0, "balance": 0.0})
            for k, v in by_day.items():
                mk = k[:7]
                agg[mk]["total"] += v["total"]
                agg[mk]["balance"] += v["balance"]
            for (y, m) in self._iter_months(start, end):
                mk = f"{y:04d}-{m:02d}"
                v = agg.get(mk, {"total": 0.0, "balance": 0.0})
                series.append(PurchasesSeriesItemDTO(date=mk, total=v["total"], balance=v["balance"]))
        else:
            from collections import defaultdict
            agg = defaultdict(lambda: {"total": 0.0, "balance": 0.0})
            for k, v in by_day.items():
                yk = k[:4]
                agg[yk]["total"] += v["total"]
                agg[yk]["balance"] += v["balance"]
            for y in self._iter_years(start, end):
                yk = f"{y:04d}"
                v = agg.get(yk, {"total": 0.0, "balance": 0.0})
                series.append(PurchasesSeriesItemDTO(date=yk, total=v["total"], balance=v["balance"]))

        meta = SegmentMetaDTO(bucket=bucket, granularity=gran, from_=start.isoformat(), to=end.isoformat(), segments=len(series))
        return PurchasesSeriesDTO(meta=meta, series=series)

    async def accounts_payable(self, session: AsyncSession) -> List[APItemDTO]:
        rows = await self.purchase_repository.accounts_payable(session=session)
        cache: dict[int, str] = {}
        out: List[APItemDTO] = []
        for r in rows:
            sid = r["supplier_id"]
            name = cache.get(sid)
            if name is None:
                s = await self.supplier_repository.get_by_id(sid, session=session)
                name = (getattr(s, "name", None) or "Desconocido") if s else "Desconocido"
                cache[sid] = name
            out.append(APItemDTO(supplier=name, total=float(r["total"]), balance=float(r["balance"]), date=r["date"]))
        return out

    async def expenses_segments(
        self,
        session: AsyncSession,
        *,
        bucket: BucketDTO,
        pivot: Optional[date] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        year: Optional[int] = None,
        month: Optional[int] = None,
    ) -> ExpensesSeriesDTO:
        start, end = await self._resolve_range(
            session, bucket, pivot=pivot, date_from=date_from, date_to=date_to, year=year, month=month
        )
        base = await self.expense_repository.expenses_by_day(session=session, date_from=start, date_to=end)

        by_day_total: dict[str, float] = collections.defaultdict(float)
        for r in base:
            by_day_total[r["date"]] += float(r["amount"] or 0.0)

        gran: GranularityDTO = self._choose_granularity(bucket, start, end)
        series: List[ExpensesSeriesItemDTO] = []

        if gran == "day":
            for d in self._iter_days(start, end):
                k = d.isoformat()
                series.append(ExpensesSeriesItemDTO(date=k, amount=float(by_day_total.get(k, 0.0))))
        elif gran == "month":
            agg_m: DefaultDict[str, float] = collections.defaultdict(float)
            for k, val in by_day_total.items():
                mk = k[:7]
                agg_m[mk] += val
            for (y, m) in self._iter_months(start, end):
                mk = f"{y:04d}-{m:02d}"
                series.append(ExpensesSeriesItemDTO(date=mk, amount=float(agg_m.get(mk, 0.0))))
        else:
            agg_y: DefaultDict[str, float] = collections.defaultdict(float)
            for k, val in by_day_total.items():
                yk = k[:4]
                agg_y[yk] += val
            for y in self._iter_years(start, end):
                yk = f"{y:04d}"
                series.append(ExpensesSeriesItemDTO(date=yk, amount=float(agg_y.get(yk, 0.0))))

        meta = SegmentMetaDTO(bucket=bucket, granularity=gran, from_=start.isoformat(), to=end.isoformat(), segments=len(series))
        return ExpensesSeriesDTO(meta=meta, series=series)
    
    async def profit_segments(
        self,
        session: AsyncSession,
        *,
        bucket: BucketDTO,
        pivot: Optional[date] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        year: Optional[int] = None,
        month: Optional[int] = None,
    ) -> ProfitSeriesDTO:
        start, end = await self._resolve_range(
            session, bucket, pivot=pivot, date_from=date_from, date_to=date_to, year=year, month=month
        )
        base = await self.profit_repository.profits_by_day(session=session, date_from=start, date_to=end)
        by_day = {r["date"]: float(r["profit"]) for r in base}

        gran: GranularityDTO = self._choose_granularity(bucket, start, end)
        series: List[ProfitSeriesItemDTO] = []

        if gran == "day":
            for d in self._iter_days(start, end):
                k = d.isoformat()
                series.append(ProfitSeriesItemDTO(date=k, profit=by_day.get(k, 0.0)))
        elif gran == "month":
            from collections import defaultdict
            agg = defaultdict(float)
            for k, v in by_day.items():
                mk = k[:7]
                agg[mk] += v
            for (y, m) in self._iter_months(start, end):
                mk = f"{y:04d}-{m:02d}"
                series.append(ProfitSeriesItemDTO(date=mk, profit=float(agg.get(mk, 0.0))))
        else:
            from collections import defaultdict
            agg = defaultdict(float)
            for k, v in by_day.items():
                yk = k[:4]
                agg[yk] += v
            for y in self._iter_years(start, end):
                yk = f"{y:04d}"
                series.append(ProfitSeriesItemDTO(date=yk, profit=float(agg.get(yk, 0.0))))

        meta = SegmentMetaDTO(bucket=bucket, granularity=gran, from_=start.isoformat(), to=end.isoformat(), segments=len(series))
        return ProfitSeriesDTO(meta=meta, series=series)

    async def banks_summary(self, session: AsyncSession) -> BanksSummaryDTO:
        banks = await self.bank_repository.list_banks(session=session)
        items = [BankItemDTO(name=b.name, balance=float(b.balance or 0.0)) for b in banks]
        total = float(sum(i.balance for i in items))
        return BanksSummaryDTO(banks=items, total=total)

    async def top_products(
        self,
        session: AsyncSession,
        *,
        bucket: BucketDTO,
        pivot: Optional[date] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        year: Optional[int] = None,
        month: Optional[int] = None,
        limit: Optional[int] = 10,
    ) -> List[TopProductItemDTO]:
        start, end = await self._resolve_range(
            session, bucket, pivot=pivot, date_from=date_from, date_to=date_to, year=year, month=month, use_purchases=False
        )
        rows = await self.sale_item_repository.top_products_by_quantity(session=session, date_from=start, date_to=end, limit=limit)
        cache: dict[int, str] = {}
        out: List[TopProductItemDTO] = []
        for r in rows:
            pid = int(r["product_id"])
            name = cache.get(pid)
            if name is None:
                prod = await self.product_repository.get_by_id(pid, session=session)
                name = (getattr(prod, "description", None) or getattr(prod, "name", None) or f"Product {pid}") if prod else f"Product {pid}"
                cache[pid] = name
            out.append(TopProductItemDTO(product_id=pid, product=name, total_quantity=float(r["total_quantity"] or 0.0)))
        return out

    async def credits_summary(self, session: AsyncSession) -> CreditsSummaryDTO:
        rows = await self.loan_repository.list_all(session=session)
        active = [c for c in rows if float(getattr(c, "amount", 0) or 0) > 0]
        items = [
            CreditItemDTO(
                name=c.name,
                amount=float(c.amount or 0),
                created_at=c.created_at.date() if hasattr(c.created_at, "date") else c.created_at,
            )
            for c in active
        ]
        total = float(sum(i.amount for i in items))
        return CreditsSummaryDTO(credits=items, total=total)

    async def investments_summary(self, session: AsyncSession) -> InvestmentsSummaryDTO:
        rows = await self.investment_repository.list_all(session=session)

        items: List[InvestmentItemDTO] = []
        for r in rows:
            due_iso = self._to_iso_date(getattr(r, "due_date", None))
            items.append(
                InvestmentItemDTO(
                    name=r.name,
                    balance=float(getattr(r, "balance", 0.0) or 0.0),
                    due_date=due_iso,
                )
            )

        total = float(sum(it.balance for it in items))
        return InvestmentsSummaryDTO(investments=items, total=total)

    async def final_report(
        self,
        session: AsyncSession,
        *,
        bucket: BucketDTO,
        pivot: Optional[date] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        year: Optional[int] = None,
        month: Optional[int] = None,
        top_limit: Optional[int] = 10,
    ) -> FinalReportDTO:
        sales_series = await self.sales_segments(session=session, bucket=bucket, pivot=pivot, date_from=date_from, date_to=date_to, year=year, month=month)
        ar = await self.accounts_receivable(session=session)

        purchases_series = await self.purchases_segments(session=session, bucket=bucket, pivot=pivot, date_from=date_from, date_to=date_to, year=year, month=month)
        ap = await self.accounts_payable(session=session)

        expenses_series = await self.expenses_segments(session=session, bucket=bucket, pivot=pivot, date_from=date_from, date_to=date_to, year=year, month=month)
        profit_series = await self.profit_segments(session=session, bucket=bucket, pivot=pivot, date_from=date_from, date_to=date_to, year=year, month=month)

        banks = await self.banks_summary(session=session)
        credits = await self.credits_summary(session=session)
        investments = await self.investments_summary(session=session)
        top = await self.top_products(session=session, bucket=bucket, pivot=pivot, date_from=date_from, date_to=date_to, year=year, month=month, limit=top_limit)

        total_sales = float(sum(s.total for s in sales_series.series))
        total_credit = float(sum(s.remaining_balance for s in sales_series.series))
        total_purchases = float(sum(s.total for s in purchases_series.series))
        total_payables = float(sum(s.balance for s in purchases_series.series))
        total_expenses = float(sum(s.amount for s in expenses_series.series))
        total_profit = float(sum(s.profit for s in profit_series.series))

        sales = SalesBlockDTO(total_sales=total_sales, total_credit=total_credit, series=sales_series, accounts_receivable=ar)
        purchases = PurchasesBlockDTO(total_purchases=total_purchases, total_payables=total_payables, series=purchases_series, accounts_payable=ap)
        expenses = ExpensesBlockDTO(total_expenses=total_expenses, series=expenses_series)
        profit = ProfitBlockDTO(total_profit=total_profit, series=profit_series)

        meta = RequestMetaDTO(
            bucket=bucket,
            pivot=pivot,
            date_from=date_from,
            date_to=date_to,
            year=year,
            month=month,
        )

        return FinalReportDTO(
            meta=meta.model_dump(exclude_none=True),
            sales=sales,
            purchases=purchases,
            expenses=expenses,
            profit=profit,
            banks=banks,
            credits=credits,
            investments=investments,
            top_products=top,
        )
