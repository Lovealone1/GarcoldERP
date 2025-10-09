from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from app.v1_0.dto.page import PageDTO

@dataclass(slots=True)
class TransactionDTO:
    id: int
    bank_id: int
    amount: float
    type_id: int
    description: Optional[str]
    created_at: datetime

@dataclass(slots=True)
class TransactionViewDTO:
    id: int
    bank: str
    amount: float
    type_str: str
    description: Optional[str]
    created_at: datetime

TransactionPageDTO = PageDTO[TransactionViewDTO]
