from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from .page import PageDTO

@dataclass(slots=True)
class SupplierDTO:
    """Full row for supplier listing."""
    id: int
    name: str
    tax_id: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    address: Optional[str]
    city: Optional[str]
    created_at: datetime

@dataclass(slots=True)
class SupplierLiteDTO:
    """Minimal supplier reference."""
    id: int
    name: str

SupplierPageDTO = PageDTO[SupplierDTO]