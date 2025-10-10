from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

class ProfitCreate(BaseModel):
    """Input schema for creating a profit record."""
    sale_id: int = Field(..., ge=1)
    profit: float = Field(..., ge=0)
    created_at: Optional[datetime] = Field(default_factory=datetime.now)