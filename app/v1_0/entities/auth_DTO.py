
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

@dataclass(frozen=True)
class AuthSyncDTO:
    email: Optional[str] = None
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AuthSyncDTO":
        return cls(
            email=d.get("email"),
            display_name=d.get("display_name"),
            avatar_url=d.get("avatar_url"),
        )
        
@dataclass(frozen=True)
class RoleOut:
    id: int
    code: str

@dataclass(frozen=True)
class MeDTO:
    user_id: str
    email: Optional[str] = None
    display_name: Optional[str] = None
    role: RoleOut | None = None
    permissions: List[str] = field(default_factory=list)