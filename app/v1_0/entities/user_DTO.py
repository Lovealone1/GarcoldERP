from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass(slots=True)
class UserDTO:
    id: int
    external_sub: str
    email: Optional[str]
    display_name: Optional[str]  
    role: Optional[str]          
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]
    
    