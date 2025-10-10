from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

class TransactionCreate(BaseModel):
    """Input schema for creating a bank transaction."""
    bank_id: int = Field(..., ge=1)
    amount: float = Field(..., ge=0)
    type_id: Optional[int] = Field(None, ge=1)
    description: Optional[str] = None
    is_auto: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.now)

    model_config = {
        "json_schema_extra": {
            "example": {
                "bank_id": 1,
                "amount": 150000.0,
                "type_id": 2,
                "description": "pago compra 123",
                "is_auto": True,
                "created_at": "2025-10-09T10:30:00"
            }
        }
    }
