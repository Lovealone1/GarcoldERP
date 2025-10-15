from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime
from .page import PageDTO

@dataclass(slots=True)
class SaleDTO:
    id: int
    customer: str
    bank: str
    status: str
    total: float
    remaining_balance: float
    created_at: datetime

SalePageDTO = PageDTO[SaleDTO]