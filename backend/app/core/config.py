from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Japonica CRM"
    app_env: str = "development"
    api_prefix: str = "/api/v1"
    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/japonica_crm"
    )
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret_key: str = "change-me-access-secret"
    jwt_refresh_secret_key: str = "change-me-refresh-secret"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30
    inbound_api_key: str = "inbound-secret-key-change-me"
    telegram_bot_token: str = ""
    telegram_webhook_secret: str = "tg-webhook-secret"
    ai_backend: str = "disabled"
    qwen_api_url: str = ""
    qwen_api_key: str = ""
    qwen_model: str = "qwen-plus"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"
    ai_timeout_seconds: float = 20.0
    cookie_secure: bool = False
    cookie_samesite: str = "lax"
    auth_rate_limit_requests: int = 5
    auth_rate_limit_window_seconds: int = 60
    refresh_rate_limit_requests: int = 20
    refresh_rate_limit_window_seconds: int = 60
    inbound_rate_limit_requests: int = 60
    inbound_rate_limit_window_seconds: int = 60
    telegram_link_rate_limit_requests: int = 10
    telegram_link_rate_limit_window_seconds: int = 300
    telegram_webhook_rate_limit_requests: int = 120
    telegram_webhook_rate_limit_window_seconds: int = 60
    nginx_server_name: str = "localhost"
    letsencrypt_email: str = "admin@example.com"
    storage_backend: str = "local"
    storage_path: str = "/app/storage/private"
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://localhost:8080",
        ]
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("cookie_samesite")
    @classmethod
    def validate_cookie_samesite(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"lax", "strict", "none"}:
            raise ValueError("cookie_samesite must be one of: lax, strict, none")
        return normalized


@lru_cache
def get_settings() -> Settings:
    return Settings()
