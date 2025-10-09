from dataclasses import dataclass
from datetime import datetime
from app.v1_0.dto.page import PageDTO

@dataclass(slots=True)
class SaleDTO:
    id: int
    customer: str
    bank: str
    status: str
    total: float
    remaining_balance: float
    date: datetime

SalePageDTO = PageDTO[SaleDTO]