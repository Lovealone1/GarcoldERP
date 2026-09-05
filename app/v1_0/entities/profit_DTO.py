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
    #: Resolved here so the screen does not have to fetch each sale to show a
    #: name. It previously issued one request per sale to fill this in.
    customer: str | None = None

ProfitPageDTO = PageDTO[ProfitDTO]