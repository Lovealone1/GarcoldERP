from dataclasses import dataclass
from datetime import date
from .page import PageDTO

@dataclass(slots=True)
class InvestmentDTO:
    id: int
    name: str
    balance: float
    maturity_date: date

InvestmentPageDTO = PageDTO[InvestmentDTO]