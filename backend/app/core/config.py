from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Liman Salon API"
    environment: str = "development"
    debug: bool = False
    database_url: str
    jwt_secret_key: str = "dev-only-change-me-use-env-jwt-secret-key-32b"
    jwt_algorithm: str = "HS256"
    access_token_expire_seconds: int = 900
    public_booking_hold_seconds: int = 900
    media_storage_backend: str = "local"
    media_storage_root: str = "./data/media"
    media_max_upload_bytes: int = 5_242_880


@lru_cache
def get_settings() -> Settings:
    return Settings()
