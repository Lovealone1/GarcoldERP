from typing import Optional
from pydantic import BaseModel, Field, EmailStr

class CustomerCreate(BaseModel):
    """Input schema to create a customer."""
    name: str = Field(..., min_length=1, max_length=120)
    tax_id: Optional[str] = Field(None, max_length=50)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=30)
    address: Optional[str] = Field(None, max_length=200)
    city: Optional[str] = Field(None, max_length=80)
    balance: float = Field(0.0, ge=0.0)

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "John Doe",
                "tax_id": "123456789",
                "email": "john@example.com",
                "phone": "+573007778888",
                "address": "123 Main St",
                "city": "Medellín",
                "balance": 0.0
            }
        }
    }

class CustomerUpdate(BaseModel):
    """Partial update schema for a customer."""
    name: Optional[str] = Field(None, min_length=1, max_length=120)
    tax_id: Optional[str] = Field(None, max_length=50)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=30)
    address: Optional[str] = Field(None, max_length=200)
    city: Optional[str] = Field(None, max_length=80)