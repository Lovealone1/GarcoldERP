from dataclasses import dataclass
from typing import Optional

@dataclass(slots=True)
class ProfitItemDTO:
    sale_id: int
    product_id: int
    reference: Optional[str]
    description: Optional[str]
    quantity: int
    purchase_price: float
    sale_price: float
    profit_total: float