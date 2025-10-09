from dataclasses import dataclass
from datetime import datetime
from .page import PageDTO

@dataclass(slots=True)
class PurchaseDTO:
    id: int
    supplier: str
    bank: str
    status: str
    total: float
    balance: float
    purchase_date: datetime

PurchasePageDTO = PageDTO[PurchaseDTO]
