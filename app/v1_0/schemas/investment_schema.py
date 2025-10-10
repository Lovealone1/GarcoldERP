from datetime import date
from pydantic import BaseModel, Field

class InvestmentCreate(BaseModel):
    """Create schema for an investment."""
    name: str = Field(..., min_length=1, max_length=120, description="Investment name")
    balance: float = Field(..., gt=0, description="Initial balance")
    maturity_date: date = Field(..., description="Maturity date (YYYY-MM-DD)")

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "90-day CD",
                "balance": 10000.0,
                "maturity_date": "2025-12-31"
            }
        }
    }

class InvestmentUpdateBalance(BaseModel):
    """Update only the investment balance."""
    balance: float = Field(..., gt=0, description="New balance")

    model_config = {
        "json_schema_extra": {
            "example": {"balance": 12500.0}
        }
    }
