from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime

class SaleItemInput(BaseModel):
    product_id: int = Field(..., ge=1)
    quantity: int = Field(..., ge=1)
    unit_price: float = Field(..., ge=0)

class SaleCreate(BaseModel):
    customer_id: int = Field(..., ge=1)
    bank_id: int = Field(..., ge=1)
    status_id: int = Field(..., ge=1)
    items: List[SaleItemInput] = Field(..., min_length=1)

class SaleItemCreate(BaseModel):
    sale_id: int = Field(..., ge=1)
    product_id: int = Field(..., ge=1)
    quantity: int = Field(..., ge=1)
    unit_price: float = Field(..., ge=0)

class SaleInsert(BaseModel):
    customer_id: int = Field(..., ge=1)
    bank_id: int = Field(..., ge=1)
    total: float = Field(..., ge=0.0)
    status_id: int = Field(..., ge=1)
    remaining_balance: Optional[float] = Field(None, ge=0.0)
    created_at: datetime = Field(default_factory=datetime.now)