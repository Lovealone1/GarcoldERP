from pydantic import BaseModel

class RolePermissionsBulkIn(BaseModel):
    codes: list[str]
    active: bool = True  

class RolePermissionStateIn(BaseModel):
    active: bool

class RolePermissionOut(BaseModel):
    code: str
    description: str | None = None
    active: bool