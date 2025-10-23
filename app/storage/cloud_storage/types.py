from enum import StrEnum
from typing import Optional

try:
    import filetype  # fallback puro-Python
except Exception:
    filetype = None


class ImageMIME(StrEnum):
    PNG = "image/png"
    JPEG = "image/jpeg"
    WEBP = "image/webp"


ALLOWED_IMAGE_MIME: set[str] = {m.value for m in ImageMIME}


def sniff_mime(data: bytes) -> Optional[str]:
    if filetype is not None:
        kind = filetype.guess(data)
        return kind.mime if kind else None
    return None


def is_allowed_image_bytes(data: bytes) -> bool:
    m = sniff_mime(data)
    return m in ALLOWED_IMAGE_MIME
