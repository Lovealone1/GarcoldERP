from dataclasses import asdict, is_dataclass
from datetime import datetime, date
from typing import Any, Dict, Iterable, List, Literal

CUSTOMER_FIELDS = ["id", "tax_id", "name", "address", "city", "phone", "email", "balance", "created_at"]
PRODUCT_FIELDS  = ["id", "reference", "description", "quantity", "purchase_price", "sale_price", "is_active", "created_at"]
SUPPLIER_FIELDS = ["id", "tax_id", "name", "address", "city", "phone", "email", "created_at"]

NUMERIC_FIELDS: Dict[str, set[str]] = {
    "customers": {"balance"},
    "products": {"quantity", "purchase_price", "sale_price"},
    "suppliers": set(),
}
FileFmt = Literal["csv", "xlsx"]
def _to_dict(obj: Any) -> Dict[str, Any]:
    if is_dataclass(obj) and not isinstance(obj, type):
        return asdict(obj)
    if hasattr(obj, "model_dump"):
        return obj.model_dump()  # type: ignore[call-arg]
    if isinstance(obj, dict):
        return obj
    return {k: getattr(obj, k) for k in dir(obj) if not k.startswith("_")}

def _cast(v: Any, *, numeric: bool) -> Any:
    if v is None:
        return 0 if numeric else ""
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(v, date):
        return v.isoformat()
    return v

def rows_from_dtos(dtos: Iterable[Any], fields: List[str], *, entity: str) -> List[Dict]:
    nums = NUMERIC_FIELDS.get(entity, set())
    out: List[Dict] = []
    for obj in dtos:
        base = _to_dict(obj)
        row: Dict[str, Any] = {}
        for k in fields:
            row[k] = _cast(base.get(k), numeric=(k in nums))
        out.append(row)
    return out
