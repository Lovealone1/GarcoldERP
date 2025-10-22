from dataclasses import dataclass
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import List, Optional
from pydantic import field_serializer
from app.v1_0.entities import CustomerDTO, CompanyDTO, SaleInvoiceBankDTO

_TZ = ZoneInfo("America/Bogota")

def _to_local(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(_TZ)

@dataclass(slots=True)
class SaleItemViewDescDTO:
    sale_id: int
    product_reference: str
    product_description: str
    quantity: int
    unit_price: float
    total: float


@dataclass(slots=True)
class SaleInvoiceDTO:
    sale_id: int
    date: datetime
    status: str
    total: float
    remaining_balance: float
    account_number: Optional[SaleInvoiceBankDTO]  
    customer: CustomerDTO
    company: CompanyDTO
    items: List[SaleItemViewDescDTO]
    @field_serializer("date")
    def ser_date(self, dt: datetime) -> str:
        return _to_local(dt).strftime("%Y-%m-%d %H:%M")