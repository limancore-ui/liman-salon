from functools import lru_cache
from typing import Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_JWT_SECRET_KEY = "dev-only-change-me-use-env-jwt-secret-key-32b"
DEV_BOOKING_MANAGE_TOKEN_PEPPER = (
    "dev-only-change-me-booking-manage-token-pepper-use-env"
)
_PRODUCTION_LIKE_ENVIRONMENTS = frozenset({"production", "staging"})


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
    jwt_secret_key: str = DEV_JWT_SECRET_KEY
    jwt_algorithm: str = "HS256"
    access_token_expire_seconds: int = 900
    public_booking_hold_seconds: int = 900
    booking_manage_token_pepper: str = DEV_BOOKING_MANAGE_TOKEN_PEPPER
    media_storage_backend: str = "local"
    media_storage_root: str = "./data/media"
    media_max_upload_bytes: int = 5_242_880

    @model_validator(mode="after")
    def _reject_dev_defaults_in_production(self) -> Self:
        env = self.environment.strip().lower()
        if env not in _PRODUCTION_LIKE_ENVIRONMENTS:
            return self

        problems: list[str] = []
        if self.debug:
            problems.append("debug must be false when environment is production or staging")
        if self.jwt_secret_key == DEV_JWT_SECRET_KEY:
            problems.append("jwt_secret_key must not use the development default")
        elif len(self.jwt_secret_key) < 32:
            problems.append("jwt_secret_key must be at least 32 characters")
        if self.booking_manage_token_pepper == DEV_BOOKING_MANAGE_TOKEN_PEPPER:
            problems.append(
                "booking_manage_token_pepper must not use the development default"
            )
        elif len(self.booking_manage_token_pepper) < 32:
            problems.append("booking_manage_token_pepper must be at least 32 characters")
        if problems:
            raise ValueError("; ".join(problems))
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
