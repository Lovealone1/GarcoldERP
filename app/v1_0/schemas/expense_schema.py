from datetime import date
from pydantic import BaseModel, Field

class ExpenseCreate(BaseModel):
    """Create schema for an expense."""
    expense_category_id: int = Field(..., ge=1, description="Expense category ID")
    bank_id: int = Field(..., ge=1, description="Bank ID used for the payment")
    amount: float = Field(..., gt=0, description="Expense amount (> 0)")
    expense_date: date = Field(..., description="Date of the expense")

    model_config = {
        "json_schema_extra": {
            "example": {
                "expense_category_id": 2,
                "bank_id": 1,
                "amount": 138.75,
                "expense_date": "2025-10-09"
            }
        }
    }
