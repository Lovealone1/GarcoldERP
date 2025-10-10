from pydantic import BaseModel, Field

class PaymentCreate(BaseModel):
    """Generic payment create schema (works for sales and purchases)."""
    bank_id: int = Field(..., ge=1)
    amount: float = Field(..., gt=0)

    model_config = {
        "json_schema_extra": {"example": {"bank_id": 1, "amount": 250.0}}
    }