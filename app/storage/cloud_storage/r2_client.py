from typing import Optional
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, BotoCoreError
from app.core.settings import settings

def _client():
    return boto3.client(
        "s3",
        endpoint_url=settings.R2_S3_ENDPOINT,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID.get_secret_value(),
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY.get_secret_value(),
        region_name="auto",
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            retries={"max_attempts": 3, "mode": "standard"},
            connect_timeout=5,
            read_timeout=15,
        ),
    )

S3 = _client()

def r2_client():
    return S3

BUCKET = settings.R2_BUCKET
PREFIX = settings.R2_PREFIX 

def build_key(*parts: str) -> str:
    segs = [p.strip("/") for p in parts if p]
    return "/".join([p for p in ([PREFIX] + segs) if p])

def public_url(key: str) -> str:
    base = settings.MEDIA_PUBLIC_BASE_STRICT
    if not base:
        raise RuntimeError("MEDIA_PUBLIC_BASE no definida para policy 'public'")
    return f"{base.rstrip('/')}/{key.lstrip('/')}"

def presigned_get(key: str, ttl_sec: Optional[int] = None) -> str:
    return S3.generate_presigned_url(
        "get_object",
        Params={"Bucket": BUCKET, "Key": key},
        ExpiresIn=int(ttl_sec or settings.MEDIA_GET_TTL_SEC),
    )

def presigned_put(
    key: str,
    ttl_sec: Optional[int] = None,
    content_type: Optional[str] = None,
    cache_control: Optional[str] = None,
) -> str:
    params = {"Bucket": BUCKET, "Key": key}
    if content_type:
        params["ContentType"] = content_type
    if cache_control:
        params["CacheControl"] = cache_control
    return S3.generate_presigned_url("put_object", Params=params, ExpiresIn=int(ttl_sec or settings.MEDIA_PUT_TTL_SEC))

def view_url(key: str, ttl_sec: Optional[int] = None) -> str:
    policy = settings.MEDIA_POLICY
    if policy == "public":
        return public_url(key)
    if policy == "signed":
        return presigned_get(key, ttl_sec)
    return f"/media/proxy/{key}"

def get_object_stream(key: str):
    try:
        return S3.get_object(Bucket=BUCKET, Key=key)  
    except ClientError as e:
        code = (e.response.get("Error") or {}).get("Code")
        if code in ("NoSuchKey", "NotFound", "404"):
            return None
        raise
    except BotoCoreError:
        raise

def put_object_bytes(key: str, body: bytes, *, content_type: str, cache_control: str | None = None):
    S3.put_object(
        Bucket=BUCKET,
        Key=key,
        Body=body,
        ContentType=content_type,
        **({"CacheControl": cache_control} if cache_control else {}),
    )

def delete_object(key: str):
    S3.delete_object(Bucket=BUCKET, Key=key)