from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_host: str = Field(default="127.0.0.1", alias="APP_HOST")
    app_port: int = Field(default=8080, alias="APP_PORT")
    database_url: str = Field(default="sqlite:///./database/tunnelkeeper.db", alias="DATABASE_URL")
    session_secret_key: str = Field(default="dev-only-secret-key", alias="SESSION_SECRET_KEY")
    session_max_idle_seconds: int = Field(default=1800, alias="SESSION_MAX_IDLE_SECONDS")
    login_rate_limit_attempts: int = Field(default=5, alias="LOGIN_RATE_LIMIT_ATTEMPTS")
    login_rate_limit_window_seconds: int = Field(default=300, alias="LOGIN_RATE_LIMIT_WINDOW_SECONDS")
    readonly_mode: bool = Field(default=False, alias="READONLY_MODE")
    secure_cookies: bool = Field(default=False, alias="SECURE_COOKIES")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
