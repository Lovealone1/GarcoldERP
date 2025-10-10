from dataclasses import dataclass
from datetime import datetime
from .page import PageDTO

@dataclass(slots=True)
class ProfitDTO:
    """Row for profit listing."""
    id: int
    sale_id: int
    profit: float
    created_at: datetime

ProfitPageDTO = PageDTO[ProfitDTO]