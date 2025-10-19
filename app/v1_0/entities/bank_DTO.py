from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass(slots=True)
class BankDTO:
    id: int
    name: str
    balance: float
    created_at: datetime
    updated_at: Optional[datetime]
    account_number: Optional[str]
    
@dataclass(slots=True)
class SaleInvoiceBankDTO:
    account_number: str | None = None