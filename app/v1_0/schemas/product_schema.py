from typing import List
from datetime import date
from pydantic import BaseModel, Field

class ProductUpsert(BaseModel):
    """Schema used for both create and update of a product."""
    reference: str = Field(..., min_length=1, max_length=120, description="Unique product code")
    description: str = Field(..., min_length=1, max_length=255, description="Product description")
    purchase_price: float = Field(..., ge=0.0, description="Unit purchase price")
    sale_price: float = Field(..., ge=0.0, description="Unit sale price")
    quantity: int = Field(..., ge=0, description="Initial stock quantity")

    model_config = {
        "json_schema_extra": {
            "example": {
                "reference": "SKU-001",
                "description": "Standard widget",
                "purchase_price": 12.5,
                "sale_price": 19.99,
                "quantity": 100
            }
        }
    }

class ProductRangeQuery(BaseModel):
    """Filter products by inclusive date range and product IDs."""
    date_from: date = Field(..., description="Inclusive start date")
    date_to: date = Field(..., description="Inclusive end date")
    product_ids: List[int] = Field(..., min_items=1, description="Product IDs to query")

    model_config = {
        "json_schema_extra": {
            "example": {
                "date_from": "2025-01-01",
                "date_to": "2025-12-31",
                "product_ids": [1, 2, 3]
            }
        }
    }
