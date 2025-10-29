from datetime import date
from pydantic import BaseModel, Field

class InvestmentCreate(BaseModel):
    """Create schema for an investment."""
    name: str = Field(..., min_length=1, max_length=120, description="Investment name")
    balance: float = Field(..., gt=0, description="Initial balance")
    maturity_date: date = Field(..., description="Maturity date (YYYY-MM-DD)")
    bank_id: int = Field(..., ge=1, description="Bank ID to bind this investment")

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "90-day CD",
                "balance": 10000.0,
                "maturity_date": "2025-12-31",
                "bank_id": 1
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

class InvestmentAddBalanceIn(BaseModel):
    investment_id: int = Field(..., description="ID de la inversión")
    amount: float = Field(..., description="Monto a adicionar al saldo")

    model_config = {
        "json_schema_extra":{
            "examples": [
                {"investment_id": 42, "amount": 150000.0}
            ]
        }
    }
    