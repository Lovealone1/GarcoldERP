from dataclasses import dataclass
from datetime import datetime

@dataclass(slots=True)
class PurchaseItemDTO:
    product_id: int
    quantity: int
    unit_price: float
    total: float
    purchase_id: int

@dataclass(slots=True)
class PurchaseItemViewDTO:
    purchase_id: int
    product_reference: str
    quantity: int
    unit_price: float
    total: float