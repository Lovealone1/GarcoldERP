from dataclasses import dataclass
from datetime import datetime

@dataclass(slots=True)
class PurchasePaymentDTO:
    id: int
    purchase_id: int
    bank_id: int
    amount: float
    created_at: datetime

@dataclass(slots=True)
class PurchasePaymentViewDTO:
    id: int
    purchase_id: int
    bank: str
    remaining_balance: float
    amount_paid: float
    created_at: datetime
