from pydantic import BaseModel

class RoleDTO(BaseModel):
    id: int
    code: str
