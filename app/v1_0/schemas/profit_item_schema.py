from pydantic import BaseModel, Field
from typing import Optional

class SaleProfitDetailCreate(BaseModel):
    """Input schema for creating a sale profit detail record."""
    sale_id: int = Field(..., ge=1)
    product_id: int = Field(..., ge=1)
    reference: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=255)
    quantity: int = Field(..., ge=1)
    purchase_price: float = Field(..., ge=0)
    sale_price: float = Field(..., ge=0)
    total_profit: float = Field(..., ge=0)

