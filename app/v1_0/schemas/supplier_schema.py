from typing import Optional
from pydantic import BaseModel, Field, EmailStr
from datetime import datetime

class SupplierCreate(BaseModel):
    """Input schema to create a supplier."""
    name: str = Field(..., min_length=1, max_length=120)
    tax_id: Optional[str] = Field(None, max_length=50)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=30)
    address: Optional[str] = Field(None, max_length=200)
    city: Optional[str] = Field(None, max_length=80)
    created_at: datetime = Field(default_factory=datetime.now)
    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "ACME Imports",
                "tax_id": "901234567",
                "email": "billing@acme.com",
                "phone": "+573001112233",
                "address": "742 Evergreen Terrace",
                "city": "Bogotá"
            }
        }
    }

class SupplierUpdate(BaseModel):
    """Partial update schema for a supplier."""
    name: Optional[str] = Field(None, min_length=1, max_length=120)
    tax_id: Optional[str] = Field(None, max_length=50)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=30)
    address: Optional[str] = Field(None, max_length=200)
    city: Optional[str] = Field(None, max_length=80)