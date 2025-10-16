from dataclasses import dataclass
from typing import List, Dict, Optional

@dataclass(frozen=True)
class FieldSpec:
    name: str
    required: bool = False
    type: Optional[str] = None  

@dataclass(frozen=True)
class EntitySchema:
    entity: str
    fields: List[FieldSpec]
    unique_keys: List[str]
    aliases: Dict[str, str]    

    @property
    def required(self) -> List[str]:
        return [f.name for f in self.fields if f.required]

    @property
    def field_names(self) -> List[str]:
        return [f.name for f in self.fields]
