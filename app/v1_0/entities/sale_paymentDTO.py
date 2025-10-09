from dataclasses import dataclass
from datetime import datetime

@dataclass(slots=True)
class SalePaymentDTO:
    id: int
    sale_id: int
    bank_id: int
    amount: float
    created_at: datetime

@dataclass(slots=True)
class SalePaymentViewDTO:
    id: int
    sale_id: int
    bank: str
    remaining_balance: float
    amount_paid: float
    created_at: datetime
