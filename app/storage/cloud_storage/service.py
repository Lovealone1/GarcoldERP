import uuid
from fastapi import HTTPException
from .r2_client import r2_client, BUCKET, PREFIX
from .types import ALLOWED_IMAGE_MIME, ImageMIME
from app.core.settings import settings

_EXT_BY_MIME = {
    ImageMIME.PNG.value: "png",
    ImageMIME.JPEG.value: "jpg",
    ImageMIME.WEBP.value: "webp",
}

class CloudStorageService:
    def __init__(self) -> None:
        self._bucket = BUCKET
        self._prefix = PREFIX

    def build_public_url(self, key: str) -> str:
        return f"https://{settings.CF_ACCOUNT_ID}.r2.cloudflarestorage.com/{self._bucket}/{key}"

    def _new_key(self, prefix: str, *, ext: str) -> str:
        return f"{self._prefix}/{prefix}/{uuid.uuid4()}.{ext}"

    def presign_put(self, *, prefix: str, content_type: str, expires: int = 300) -> tuple[str, str, dict]:
        if content_type not in ALLOWED_IMAGE_MIME:
            raise HTTPException(400, "tipo no permitido")
        ext = _EXT_BY_MIME[content_type]
        key = self._new_key(prefix, ext=ext)
        url = r2_client().generate_presigned_url(
            "put_object",
            Params={"Bucket": self._bucket, "Key": key, "ContentType": content_type},
            ExpiresIn=expires,
        )
        headers = {"Content-Type": content_type}
        return key, url, headers

    def delete_object(self, key: str) -> None:
        """Borra el objeto en R2."""
        r2_client().delete_object(Bucket=self._bucket, Key=key)

    def delete(self, key: str) -> None:
        self.delete_object(key)

    def head_object(self, key: str) -> dict:
        return r2_client().head_object(Bucket=self._bucket, Key=key)

    def presigned_get_url(self, key: str, expires: int = 300) -> str:
        return r2_client().generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=expires,
        )