import boto3
from app.core.settings import settings

def assert_r2_config():
    ok = (
        settings.CF_ACCOUNT_ID
        and settings.R2_ACCESS_KEY_ID
        and settings.R2_SECRET_ACCESS_KEY
        and settings.R2_BUCKET
    )
    if not ok:
        raise RuntimeError("R2 no configurado en .env")

def r2_client():
    assert_r2_config()
    return boto3.client(
        "s3",
        endpoint_url=f"https://{settings.CF_ACCOUNT_ID}.r2.cloudflarestorage.com",
        aws_access_key_id=settings.R2_ACCESS_KEY_ID.get_secret_value(),
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY.get_secret_value(),
        region_name="auto",
    )

BUCKET = settings.R2_BUCKET
PREFIX = settings.R2_PREFIX.rstrip("/")  
