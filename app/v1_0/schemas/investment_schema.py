from datetime import date
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal
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
    investment_id: int = Field(..., gt=0, description="ID de la inversión")
    amount: float = Field(..., gt=0, description="Monto a adicionar al saldo")
    kind: Literal["interest", "topup"] = Field(
        "interest",
        description="Tipo de movimiento: 'interest' suma interés, 'topup' aporta capital desde un banco"
    )
    source_bank_id: Optional[int] = Field(
        None, gt=0, description="Banco de origen para 'topup'"
    )
    description: Optional[str] = Field(
        None, description="Descripción opcional para la transacción"
    )

    model_config = {
        "json_schema_extra":{
                "examples": [
                    {"investment_id": 42, "amount": 150000.0, "kind": "interest"},
                    {"investment_id": 42, "amount": 500000.0, "kind": "topup", "source_bank_id": 7}
                ]
            }
        }

    @field_validator("source_bank_id")
    @classmethod
    def _require_bank_on_topup(cls, v, info):
        kind = info.data.get("kind")
        if kind == "topup" and not v:
            raise ValueError("source_bank_id es requerido cuando kind='topup'")
        return v

class InvestmentWithdrawIn(BaseModel):
    investment_id: int = Field(..., gt=0, description="ID de la inversión")
    kind: Literal["partial", "full"] = Field("partial", description="partial|full")
    amount: Optional[float] = Field(None, gt=0, description="Requerido si kind=partial")
    destination_bank_id: Optional[int] = Field(
        None, gt=0, description="Banco a acreditar. Por defecto el bank_id de la inversión"
    )
    description: Optional[str] = None

    model_config = {"json_schema_extra":{
        "examples": [
            {"investment_id": 42, "kind": "partial", "amount": 250000, "destination_bank_id": 7},
            {"investment_id": 42, "kind": "full"} 
        ]
    }}

    @field_validator("amount")
    @classmethod
    def _require_amount_on_partial(cls, v, info):
        if info.data.get("kind") == "partial" and v is None:
            raise ValueError("amount es requerido cuando kind='partial'")
        return v