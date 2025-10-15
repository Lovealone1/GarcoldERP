from decimal import Decimal
from pydantic import BaseModel, Field

class BankCreate(BaseModel):
    """Create schema for a bank. Name and initial balance only."""
    name: str = Field(..., min_length=1, max_length=120)
    balance: float = Field(..., ge=Decimal("0.00"), description="Initial balance")
    account_number: str | None = Field(None, max_length=50)

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "Test Bank",
                "balance": "0.00",
                "account_number": "001-234567-89"
            }
        }
    }

class BankUpdateBalance(BaseModel):
    """Update only the bank balance."""
    new_balance: float = Field(..., ge=Decimal("0.00"))

    model_config = {
        "json_schema_extra": {
            "example": {"new_balance": "12500.50"}
        }
    }
