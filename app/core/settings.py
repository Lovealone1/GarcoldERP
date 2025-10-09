from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # === App ===
    APP_NAME: str = "GarcoldERP API"
    APP_VERSION: str = "1.0.0"
    APP_ENV: str = "local"
    DEBUG: bool = False
    FRONTEND_URL: str = "http://localhost:3000"

    # === Database (Supabase) ===
    DATABASE_URL: str

    # === Auth (Supabase) ===
    SUPABASE_URL: str
    SUPABASE_JWKS_URL: str
    SUPABASE_AUD: str = "authenticated"
    SUPABASE_ISS: str

    # === Security / CORS ===
    CORS_ORIGINS: str = "*"
    LOG_LEVEL: str = "INFO"

settings = Settings()
