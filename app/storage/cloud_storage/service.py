import uuid
from fastapi import HTTPException
from app.core.settings import settings
from .types import ALLOWED_IMAGE_MIME, ImageMIME
from .r2_client import (
    BUCKET, PREFIX, build_key,
    presigned_put, presigned_get, view_url,
    delete_object, r2_client,
)

_EXT_BY_MIME = {
    ImageMIME.PNG.value: "png",
    ImageMIME.JPEG.value: "jpg",
    ImageMIME.WEBP.value: "webp",
}

class CloudStorageService:
    def __init__(self) -> None:
        self._bucket = BUCKET
        self._prefix = PREFIX

    def view_url(self, key: str) -> str:
        return view_url(key)

    def _new_key(self, prefix: str, *, ext: str) -> str:
        return build_key(prefix, f"{uuid.uuid4()}.{ext}")

    def presign_put(self, *, prefix: str, content_type: str, expires: int | None = None) -> tuple[str, str, dict]:
        if content_type not in ALLOWED_IMAGE_MIME:
            raise HTTPException(400, "tipo no permitido")
        ext = _EXT_BY_MIME[content_type]
        key = self._new_key(prefix, ext=ext)
        cache = "public, max-age=31536000, immutable"

        url = presigned_put(
            key,
            ttl_sec=expires,
            content_type=content_type,
            cache_control=cache,   
        )
        headers = {
            "Content-Type": content_type,
            "Cache-Control": cache,  
        }
        return key, url, headers

    def presigned_get_url(self, key: str, expires: int | None = None) -> str:
        return presigned_get(key, ttl_sec=expires)

    def head_object(self, key: str) -> dict:
        return r2_client().head_object(Bucket=self._bucket, Key=key)

    def delete(self, key: str) -> None:
        delete_object(key)
