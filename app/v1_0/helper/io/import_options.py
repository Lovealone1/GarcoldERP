from dataclasses import dataclass
from typing import Literal, Optional

Entity = Literal["customers", "suppliers", "products"]
@dataclass
class ImportOptions:
    entity: Entity
    dry_run: bool = True
    delimiter: Optional[str] = None
    sheet: Optional[str] = None
    header_row: int = 1