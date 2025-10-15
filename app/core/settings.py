from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr, field_validator

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "GarcoldERP API"
    APP_VERSION: str = "1.0.0"
    APP_ENV: str = "local"
    DEBUG: bool = False
    FRONTEND_URL: str = "http://localhost:3000"
    CORS_ORIGINS: str = "*"
    LOG_LEVEL: str = "INFO"

    DATABASE_URL: SecretStr = SecretStr("")

    CF_ACCOUNT_ID: str = ""
    R2_ACCESS_KEY_ID: SecretStr = SecretStr("")
    R2_SECRET_ACCESS_KEY: SecretStr = SecretStr("")
    R2_BUCKET: str = "garcold-erp"
    R2_PREFIX: str = "media-dev"

    @field_validator("DATABASE_URL", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY")
    @classmethod
    def _required(cls, v, info):
        if v is None or (hasattr(v, "get_secret_value") and v.get_secret_value() == ""):
            raise ValueError(f"{info.field_name} is required (set it in .env)")
        return v

settings = Settings()
