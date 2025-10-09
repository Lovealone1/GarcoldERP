from dataclasses import dataclass
from datetime import datetime
from .page import PageDTO

@dataclass(slots=True)
class LoanDTO:
    """Loan response DTO."""
    id: int
    name: str
    amount: float
    created_at: datetime

LoanPageDTO = PageDTO[LoanDTO]