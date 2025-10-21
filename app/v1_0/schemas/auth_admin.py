from pydantic import BaseModel, EmailStr
from typing import List
from typing import Optional, Any, Dict

class InviteUserIn(BaseModel):
    email: EmailStr
    redirect_to: Optional[str] = None  # URL para flujo de invitación

class CreateUserIn(BaseModel):
    email: EmailStr
    password: str                     # requerido en creación directa
    user_metadata: Optional[Dict[str, Any]] = None
    app_metadata: Optional[Dict[str, Any]] = None

class AdminUserOut(BaseModel):
    id: str
    email: EmailStr
    created_at: Optional[str] = None
    confirmed_at: Optional[str] = None
    user_metadata: Dict[str, Any] = {}
    app_metadata: Dict[str, Any] = {}

class AdminUsersPage(BaseModel):
    items: List[AdminUserOut]
    page: int
    per_page: int
    has_next: bool