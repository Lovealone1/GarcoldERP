from typing import Dict, List, Tuple
from app.v1_0.helper.io.schemas import EntitySchema
from .normalizers import normalize_value

class HeaderMapper:
    def __init__(self, schema: EntitySchema, keep_unknown: bool = False):
        self.schema = schema
        self.keep_unknown = keep_unknown

    def apply(self, rows: List[dict]) -> Tuple[List[dict], List[dict]]:
        out: List[Dict] = []
        errs: List[Dict] = []
        aliases = self.schema.aliases
        valid = set(self.schema.field_names)

        for i, raw in enumerate(rows, start=2):
            mapped: Dict[str, object] = {}
            unknowns: Dict[str, object] = {}
            for k, v in raw.items():
                if k is None: continue
                canon = aliases.get(str(k).strip().lower())
                if canon:
                    mapped[canon] = normalize_value(canon, v)
                else:
                    if self.keep_unknown:
                        unknowns[str(k)] = v
            if self.keep_unknown and unknowns:
                mapped["_unknown"] = unknowns
            cleaned = {k: v for k, v in mapped.items() if k in valid or k == "_unknown"}
            out.append(cleaned)
        return out, errs
