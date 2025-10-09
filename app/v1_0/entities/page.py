from dataclasses import dataclass
from typing import Generic, List, TypeVar

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