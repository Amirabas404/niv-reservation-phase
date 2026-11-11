from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class BotSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    customer_bot_token: SecretStr
    backend_url: str = "http://localhost:8000"
    internal_service_token: SecretStr
    redis_url: str = "redis://localhost:6379/0"
    timezone: str = "Asia/Tehran"
    log_level: str = "INFO"
    webhook_base_url: str | None = None
    webhook_secret: SecretStr | None = None
    port: int = 8080


@lru_cache
def get_bot_settings() -> BotSettings:
    return BotSettings()
