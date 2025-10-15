from enum import StrEnum
import magic

class ImageMIME(StrEnum):
    PNG = "image/png"
    JPEG = "image/jpeg"
    WEBP = "image/webp"

ALLOWED_IMAGE_MIME: set[str] = {m.value for m in ImageMIME}

def sniff_mime(data: bytes) -> str | None:
    return magic.from_buffer(data, mime=True) if data else None

def is_allowed_image_bytes(data: bytes) -> bool:
    m = sniff_mime(data)
    return m in ALLOWED_IMAGE_MIME