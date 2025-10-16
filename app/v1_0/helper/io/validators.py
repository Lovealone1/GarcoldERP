from __future__ import annotations
from typing import Any, Dict, List
from app.v1_0.helper.io.schemas import EntitySchema
from .normalizers import to_float, to_int, to_bool

def _err(row: int, field: str, code: str, message: str, value: Any = None, level: str = "error") -> Dict[str, Any]:
    return {"row": row, "field": field, "code": code, "message": message, "value": value, "level": level}

def validate_rows(rows: List[Dict[str, Any]], schema: EntitySchema) -> List[Dict[str, Any]]:
    errors: List[Dict[str, Any]] = []
    for r_idx, row in enumerate(rows, start=2): 
        for req in schema.required:
            if row.get(req) in (None, ""):
                errors.append(_err(r_idx, req, "required", "Campo requerido ausente"))
        for f in schema.fields:
            val = row.get(f.name, None)
            if val in (None, ""):
                continue
            t = f.type
            if t == "number" and to_float(val) is None:
                errors.append(_err(r_idx, f.name, "type", "Debe ser numérico", val))
            elif t == "int":
                iv = to_int(val)
                if iv is None:
                    errors.append(_err(r_idx, f.name, "type", "Debe ser entero", val))
                else:
                    row[f.name] = iv  
            elif t == "email":
                s = str(val)
                if "@" not in s or s.startswith("@") or s.endswith("@"):
                    errors.append(_err(r_idx, f.name, "format", "Email inválido", val))
            elif t == "bool":
                if to_bool(val) is None:
                    errors.append(_err(r_idx, f.name, "type", "Debe ser booleano", val))
    return errors
