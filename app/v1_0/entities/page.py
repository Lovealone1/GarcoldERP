from dataclasses import dataclass
from typing import Generic, List, Optional, TypeVar

from .period import PeriodDTO

T = TypeVar("T")

@dataclass(slots=True)
class PageDTO(Generic[T]):
    """Generic pagination envelope."""
    items: List[T]
    page: int
    page_size: int
    total: int
    total_pages: int
    has_next: bool
    has_prev: bool
    #: The range the server filtered on. Present on the endpoints that resolve
    #: a period; None on the ones that do not (customers, suppliers, products).
    period: Optional[PeriodDTO] = None