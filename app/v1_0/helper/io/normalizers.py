from typing import Any

TRUE_SET = {"true", "1", "yes", "y", "si", "sí", "on", "activo"}
FALSE_SET = {"false", "0", "no", "n", "off", "inactivo"}

def to_str(v: Any) -> str | None:
    if v is None: return None
    s = str(v).strip()
    return s if s != "" else None

def to_float(v: Any) -> float | None:
    if v is None: return None
    if isinstance(v, (int, float)): return float(v)
    s = str(v).strip()
    if s == "": return None
    s = s.replace(" ", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None

def to_int(v: Any) -> int | None:
    f = to_float(v)
    if f is None: return None
    i = int(f)
    return i if i == f else None

def to_bool(v: Any) -> bool | None:
    if v is None: return None
    if isinstance(v, bool): return v
    s = str(v).strip().lower()
    if s in TRUE_SET: return True
    if s in FALSE_SET: return False
    return None

def to_email(v: Any) -> str | None:
    s = to_str(v)
    return s.lower() if s else None

def normalize_value(field: str, v: Any) -> Any:
    if v is None: return None
    if field in {"email"}: return to_email(v)
    if field in {"is_active", "active"}: return to_bool(v)
    if field in {"price", "sale_price", "purchase_price", "tax_rate", "balance"}: return to_float(v)
    if field in {"quantity", "stock"}: return to_int(v)
    return to_str(v)
