from dataclasses import dataclass
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


@dataclass
class SaleProductsDTO:
    """
    DTO para mostrar productos vendidos en un rango, con cantidad vendida.
    No incluye estado ni fecha de creación.
    """
    id: int
    referencia: str
    description: str
    sold_quanity: int
    purchase_price: float
    sale_price: float
    
ProductPageDTO = PageDTO[ProductDTO]