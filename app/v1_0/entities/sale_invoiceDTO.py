from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from app.v1_0.entities import CustomerDTO, CompanyDTO, SaleInvoiceBankDTO


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
    bank: Optional[SaleInvoiceBankDTO]  
    customer: CustomerDTO
    company: CompanyDTO
    items: List[SaleItemViewDescDTO]