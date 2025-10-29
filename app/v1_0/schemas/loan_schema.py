from pydantic import BaseModel, Field

class LoanCreate(BaseModel):
    """Create schema for a loan."""
    name: str = Field(..., min_length=1, max_length=120, description="Loan name")
    amount: float = Field(..., gt=0, description="Initial loan amount")

    model_config = {
        "json_schema_extra": {
            "example": {"name": "Working Capital", "amount": 5000.0}
        }
    }

class LoanUpdateAmount(BaseModel):
    """Update only the loan amount."""
    amount: float = Field(..., gt=0, description="New loan amount")

    model_config = {
        "json_schema_extra": {
            "example": {"amount": 7500.0}
        }
    }

class LoanApplyPaymentIn(BaseModel):
    loan_id: int = Field(..., gt=0)
    amount: float = Field(..., gt=0)
    bank_id: int = Field(..., gt=0)
    description: str | None = None

    model_config = {
        "json_schema_extra":{
            "examples": [
                {"loan_id": 12, "amount": 250000, "bank_id": 7, "description": "Pago cuota octubre"}
            ]
        }
    }