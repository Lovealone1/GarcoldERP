from typing import Literal, Dict, Any
from enum import StrEnum
from pydantic import BaseModel, Field

ContentTypeImage = Literal["image/png", "image/jpeg", "image/webp"]

class MediaKindDTO(StrEnum):
    AVATAR = "AVATAR"
    PRODUCT = "PRODUCT"
    INVOICE = "INVOICE"

class PresignRequestDTO(BaseModel):
    content_type: ContentTypeImage
    max_mb: int = Field(5, ge=1, le=20)

class PresignResponseDTO(BaseModel):
    key: str
    url: str
    fields: Dict[str, Any]

class MediaConfirmInDTO(BaseModel):
    key: str
    public_url: str
    content_type: ContentTypeImage
    bytes: int | None = Field(default=None, ge=0)
    checksum: str | None = None

class MediaOutDTO(BaseModel):
    id: int
    kind: MediaKindDTO
    key: str
    public_url: str