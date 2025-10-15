from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime 

class PurchaseItemCreate(BaseModel):
    purchase_id: int = Field(..., ge=1)
    product_id: int = Field(..., ge=1)
    quantity: int = Field(..., ge=1)
    unit_price: float = Field(..., ge=0)

class PurchaseItemInput(BaseModel):
    product_id: int = Field(..., ge=1)
    quantity: int = Field(..., ge=1)
    unit_price: float = Field(..., ge=0)
    
class PurchaseCreate(BaseModel):
    supplier_id: int = Field(..., ge=1, description="Supplier ID")
    bank_id: int = Field(..., ge=1, description="Bank ID used for payments")
    status_id: int = Field(..., ge=1, description="Initial status ID")
    items: List[PurchaseItemInput] = Field(..., min_length=1, description="Purchase cart")

    model_config = {
        "json_schema_extra": {
            "example": {
                "supplier_id": 5,
                "bank_id": 2,
                "status_id": 1,
                "items": [
                    {"product_id": 10, "quantity": 3, "unit_price": 12.5},
                    {"product_id": 11, "quantity": 1, "unit_price": 99.9}
                ]
            }
        }
    }
    
class PurchaseInsert(BaseModel):
    """Core fields to persist a purchase (no items)."""
    supplier_id: int = Field(..., ge=1)
    bank_id: int = Field(..., ge=1)
    status_id: int = Field(..., ge=1)
    total: float = Field(..., ge=0.0)
    balance: Optional[float] = Field(None, ge=0.0)
    purchase_date: datetime = Field(default_factory=datetime.now)

    model_config = {
        "json_schema_extra": {
            "example": {
                "supplier_id": 5,
                "bank_id": 2,
                "status_id": 1,
                "total": 137.4,
                "balance": 137.4,
                "purchase_date": "2025-10-09T10:30:00"
            }
        }
    }