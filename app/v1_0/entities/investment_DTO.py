from dataclasses import dataclass
from datetime import date
from typing import List
from app.v1_0.dto.page import PageDTO

@dataclass(slots=True)
class InvestmentDTO:
    id: int
    name: str
    balance: float
    maturity_date: date

InvestmentPageDTO = PageDTO[InvestmentDTO]