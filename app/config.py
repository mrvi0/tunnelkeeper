from __future__ import annotations

from functools import lru_cache

from pydantic import Field, model_validator
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

    sshd_generated_dir: str = Field(
        default="/etc/ssh/sshd_config.d/generated",
        alias="SSHD_GENERATED_DIR",
    )
    sshd_main_config: str = Field(default="/etc/ssh/sshd_config", alias="SSHD_MAIN_CONFIG")
    sshd_include_snippet: str = Field(
        default="Include /etc/ssh/sshd_config.d/*.conf",
        alias="SSHD_INCLUDE_SNIPPET",
    )
    sshd_reload_on_change: bool = Field(default=True, alias="SSHD_RELOAD_ON_CHANGE")

    enable_web_ui: bool = Field(default=True, alias="ENABLE_WEB_UI")
    enable_api: bool = Field(default=False, alias="ENABLE_API")
    api_token: str = Field(default="", alias="API_TOKEN")

    @model_validator(mode="after")
    def _validate_runtime_modes(self) -> Settings:
        if not self.enable_web_ui and not self.enable_api:
            raise ValueError("At least one of ENABLE_WEB_UI or ENABLE_API must be true.")
        if self.enable_api and len(self.api_token.strip()) < 16:
            raise ValueError("API_TOKEN is required (min 16 chars) when ENABLE_API=true.")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
