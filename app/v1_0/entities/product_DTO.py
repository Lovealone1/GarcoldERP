from dataclasses import dataclass
from datetime import datetime
from typing import List
from app.v1_0.dto.page import PageDTO

@dataclass(slots=True)
class ProductDTO:
    """Full product listing row."""
    id: int
    reference: str
    description: str
    quantity: int
    purchase_price: float
    sale_price: float
    is_active: bool
    created_at: datetime

ProductPageDTO = PageDTO[ProductDTO]