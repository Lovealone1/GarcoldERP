from dataclasses import dataclass
from datetime import datetime
from .page import PageDTO

@dataclass(slots=True)
class ExpenseDTO:
    id: int
    expense_category_id: int
    amount: float
    bank_id: int
    expense_date: datetime

@dataclass(slots=True)
class ExpenseViewDTO:
    id: int
    category_name: str
    amount: float
    bank_name: str
    expense_date: datetime

ExpensePageDTO = PageDTO[ExpenseViewDTO]