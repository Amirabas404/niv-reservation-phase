from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class ManagementBotSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    management_bot_token: SecretStr
    management_bot_backend_url: str = "http://localhost:8000"
    admin_service_token: SecretStr
    redis_url: str = "redis://localhost:6379/0"
    log_level: str = "INFO"
    webhook_base_url: str | None = None
    webhook_secret: SecretStr | None = None
    port: int = 8080
    notifier_actor_telegram_id: int = 0


@lru_cache
def get_management_settings() -> ManagementBotSettings:
    return ManagementBotSettings()
