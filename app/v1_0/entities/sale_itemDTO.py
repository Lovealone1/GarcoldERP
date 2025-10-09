from dataclasses import dataclass

@dataclass(slots=True)
class SaleItemDTO:
    product_id: int
    quantity: int
    unit_price: float
    total: float
    sale_id: int

@dataclass(slots=True)
class SaleItemViewDTO:
    sale_id: int
    product_reference: str
    quantity: int
    unit_price: float
    total: float
