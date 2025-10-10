from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class PurchasePaymentCreate(BaseModel):
    purchase_id: int = Field(..., ge=1)
    bank_id: int = Field(..., ge=1)
    amount: float = Field(..., ge=0)

    created_at: Optional[datetime] = Field(default_factory=datetime.now)

    model_config = {
        "json_schema_extra": {
            "example": {
                "purchase_id": 12,
                "bank_id": 5,
                "amount": 350000.0,
            }
        }
    }
