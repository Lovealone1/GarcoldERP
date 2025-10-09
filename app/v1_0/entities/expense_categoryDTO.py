from dataclasses import dataclass

@dataclass(slots=True)
class ExpenseCategoryDTO:
    id: int
    name: str