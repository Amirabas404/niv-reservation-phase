"""Infrastructure settings loaded from environment / .env.

Business rules (prices, hours, deadlines, card number, report time) are NOT
stored here. They live in the SystemSettings table so the manager can change
them without redeploying.
"""

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    log_level: str = "INFO"
    timezone: str = Field(default="Asia/Tehran", description="Display/business timezone (IANA name)")

    database_url: str = Field(..., description="postgresql+asyncpg://user:pass@host:port/db")
    redis_url: str = "redis://localhost:6379/0"

    admin_service_token: SecretStr = Field(..., description="Shared secret for the management bot only")
    internal_service_token: SecretStr = Field(..., description="Shared secret for bot/worker -> backend calls")

    private_storage_dir: str = Field(default="./private_storage", description="Local private receipts folder")
    storage_provider: str = Field(default="local", description="local | r2")
    backup_time: str = "03:30"
    backup_retention_days: int = 30
    storage_provider: str = Field(default="local", description="local | r2")
    backup_time: str = "03:30"
    backup_retention_days: int = 30
    storage_endpoint_url: str | None = None
    storage_bucket: str | None = None
    storage_access_key: SecretStr | None = None
    storage_secret_key: SecretStr | None = None

    customer_bot_token: SecretStr | None = None
    management_bot_token: SecretStr | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
