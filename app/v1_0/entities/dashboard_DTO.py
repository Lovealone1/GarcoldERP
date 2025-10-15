from dataclasses import dataclass
from datetime import date
from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel

Bucket = Literal["week", "month", "year", "all"]
Granularity = Literal["day", "month", "year"]

class RequestMetaDTO(BaseModel):
    bucket: Bucket
    pivot: Optional[date] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    year: Optional[int] = None
    month: Optional[int] = None

@dataclass(slots=True)
class SegmentMetaDTO:
    bucket: Bucket
    granularity: Granularity
    from_: str   
    to: str      
    segments: int

@dataclass(slots=True)
class SalesSeriesItemDTO:
    date: str
    total: float
    remaining_balance: float

@dataclass(slots=True)
class SalesSeriesDTO:
    meta: SegmentMetaDTO
    series: List[SalesSeriesItemDTO]

@dataclass(slots=True)
class ARItemDTO:
    customer: str
    total: float
    remaining_balance: float
    date: str

@dataclass(slots=True)
class SalesBlockDTO:
    total_sales: float
    total_credit: float
    series: SalesSeriesDTO
    accounts_receivable: List[ARItemDTO]

@dataclass(slots=True)
class PurchasesSeriesItemDTO:
    date: str
    total: float
    balance: float

@dataclass(slots=True)
class PurchasesSeriesDTO:
    meta: SegmentMetaDTO
    series: List[PurchasesSeriesItemDTO]

@dataclass(slots=True)
class APItemDTO:
    supplier: str
    total: float
    balance: float
    date: str

@dataclass(slots=True)
class PurchasesBlockDTO:
    total_purchases: float
    total_payables: float
    series: PurchasesSeriesDTO
    accounts_payable: List[APItemDTO]

@dataclass(slots=True)
class ExpensesSeriesItemDTO:
    date: str
    amount: float

@dataclass(slots=True)
class ExpensesSeriesDTO:
    meta: SegmentMetaDTO
    series: List[ExpensesSeriesItemDTO]

@dataclass(slots=True)
class ExpensesBlockDTO:
    total_expenses: float
    series: ExpensesSeriesDTO

@dataclass(slots=True)
class ProfitSeriesItemDTO:
    date: str
    profit: float

@dataclass(slots=True)
class ProfitSeriesDTO:
    meta: SegmentMetaDTO
    series: List[ProfitSeriesItemDTO]

@dataclass(slots=True)
class ProfitBlockDTO:
    total_profit: float
    series: ProfitSeriesDTO

@dataclass(slots=True)
class BankItemDTO:
    name: str
    balance: float

@dataclass(slots=True)
class BanksSummaryDTO:
    banks: List[BankItemDTO]
    total: float

@dataclass(slots=True)
class TopProductItemDTO:
    product_id: int
    product: str
    total_quantity: float

@dataclass(slots=True)
class CreditItemDTO:
    name: str
    amount: float
    created_at: date

@dataclass(slots=True)
class CreditsSummaryDTO:
    credits: List[CreditItemDTO]
    total: float

@dataclass(slots=True)
class InvestmentItemDTO:
    name: str
    balance: float
    due_date: Optional[str]  


@dataclass(slots=True)
class InvestmentsSummaryDTO:
    investments: List[InvestmentItemDTO]
    total: float


@dataclass(slots=True)
class FinalReportDTO:
    meta: Dict[str, Any]
    sales: SalesBlockDTO
    purchases: PurchasesBlockDTO
    expenses: ExpensesBlockDTO
    profit: ProfitBlockDTO
    banks: BanksSummaryDTO
    credits: CreditsSummaryDTO
    investments: InvestmentsSummaryDTO
    top_products: Optional[List[TopProductItemDTO]] = None
