from dataclasses import dataclass
from typing import Optional
from datetime import datetime

from .page import PageDTO

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
    barcode: Optional[str] = None
    barcode_type: Optional[str] = None


@dataclass
class SaleProductsDTO:
    """
    DTO para mostrar productos vendidos en un rango, con cantidad vendida.
    No incluye estado ni fecha de creación.
    """
    id: int
    reference: str
    description: str
    sold_quanity: int
    purchase_price: float
    sale_price: float
    
ProductPageDTO = PageDTO[ProductDTO]