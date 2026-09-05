from typing import Literal, Optional, List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import AliasChoices, Field, SecretStr, field_validator, model_validator

MediaPolicy = Literal["public", "signed", "proxy"]

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    APP_NAME: str = "GarcoldERP API"
    APP_VERSION: str = "1.0.0"
    APP_ENV: Literal["local", "dev", "staging", "prod"] = "local"
    DEBUG: bool = False
    FRONTEND_URL: str = "http://localhost:3000"
    # Accepts CORS_ORIGIN too: the deployed .env spells it in the singular, so
    # the plural name silently fell back to "*" -- which for a financial API
    # meant every origin was allowed.
    CORS_ORIGINS: str = Field(default="*", validation_alias=AliasChoices("CORS_ORIGINS", "CORS_ORIGIN"))
    LOG_LEVEL: str = "INFO"

    # Auth / Supabase
    SUPABASE_URL: str = ""
    SUPABASE_JWT_SECRET: SecretStr = SecretStr("")
    SUPABASE_SERVICE_ROLE_KEY: SecretStr = SecretStr("")   

    # DB
    DATABASE_URL: SecretStr = SecretStr("")

    # R2
    CF_ACCOUNT_ID: str = ""
    R2_ACCESS_KEY_ID: SecretStr = SecretStr("")
    R2_SECRET_ACCESS_KEY: SecretStr = SecretStr("")
    R2_BUCKET: str = "garcold-erp"
    R2_PREFIX: str = "media-dev"

    # Media
    MEDIA_POLICY: MediaPolicy = "signed"
    MEDIA_PUBLIC_BASE: Optional[str] = None
    MEDIA_GET_TTL_SEC: int = 604800
    MEDIA_PUT_TTL_SEC: int = 600

    @field_validator("SUPABASE_URL")
    @classmethod
    def _normalize_supabase_url(cls, v: str) -> str:
        return (v or "").strip().rstrip("/")

    @field_validator(
        "DATABASE_URL",
        "R2_ACCESS_KEY_ID",
        "R2_SECRET_ACCESS_KEY",
        "SUPABASE_JWT_SECRET",
        "SUPABASE_SERVICE_ROLE_KEY",          
    )
    @classmethod
    def _required_secret(cls, v, info):
        if v is None or (hasattr(v, "get_secret_value") and v.get_secret_value() == ""):
            raise ValueError(f"{info.field_name} is required (set it in .env)")
        return v

    @field_validator("CF_ACCOUNT_ID", "R2_BUCKET", "SUPABASE_URL")
    @classmethod
    def _required_plain(cls, v, info):
        if not v:
            raise ValueError(f"{info.field_name} is required (set it in .env)")
        return v

    @field_validator("R2_PREFIX")
    @classmethod
    def _normalize_prefix(cls, v: str) -> str:
        return (v or "").strip().strip("/")

    @field_validator("MEDIA_GET_TTL_SEC", "MEDIA_PUT_TTL_SEC")
    @classmethod
    def _ttl_positive(cls, v: int, info):
        if v <= 0:
            raise ValueError(f"{info.field_name} must be > 0")
        return v

    @model_validator(mode="after")
    def _cross_checks(self):
        if self.MEDIA_POLICY == "public" and not self.MEDIA_PUBLIC_BASE:
            raise ValueError("MEDIA_PUBLIC_BASE is required when MEDIA_POLICY=public")
        if self.APP_ENV in ("staging", "prod") and self.CORS_ORIGINS.strip() == "*":
            raise ValueError(
                "CORS_ORIGINS must list explicit origins outside local/dev; "
                '"*" also forces allow_credentials off'
            )
        return self

    # ---------- helpers ----------
    @property
    def CORS_ORIGINS_LIST(self) -> List[str]:
        return ["*"] if self.CORS_ORIGINS.strip() == "*" else [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def R2_S3_ENDPOINT(self) -> str:
        return f"https://{self.CF_ACCOUNT_ID}.r2.cloudflarestorage.com"

    @property
    def MEDIA_PUBLIC_BASE_STRICT(self) -> Optional[str]:
        if self.MEDIA_POLICY == "public":
            return (self.MEDIA_PUBLIC_BASE or "").rstrip("/") or None
        return self.MEDIA_PUBLIC_BASE.rstrip("/") if self.MEDIA_PUBLIC_BASE else None

    @property
    def SUPABASE_ISS(self) -> str:
        return f"{self.SUPABASE_URL}/auth/v1"

    @property
    def SUPABASE_ADMIN_HEADERS(self) -> dict:
        key = self.SUPABASE_SERVICE_ROLE_KEY.get_secret_value()
        return {"Authorization": f"Bearer {key}", "apikey": key, "Content-Type": "application/json"}

settings = Settings()
