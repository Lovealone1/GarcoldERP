from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class SalePaymentCreate(BaseModel):
    sale_id: int = Field(..., ge=1)
    bank_id: int = Field(..., ge=1)
    amount: float = Field(..., ge=0)

    created_at: Optional[datetime] = Field(default_factory=datetime.now)

    model_config = {
        "json_schema_extra": {
            "example": {
                "sale_id": 42,
                "bank_id": 3,
                "amount": 125000.0
            }
        }
    }