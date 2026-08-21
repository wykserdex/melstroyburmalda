"""Application configuration loaded from environment variables.

CLI flags override values loaded from .env at runtime (see main.py).
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strict typed configuration. No defaults for secrets."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Runtime -------------------------------------------------------------
    environment: Literal["development", "staging", "production"] = "development"
    log_level: str = "INFO"
    log_json: bool = False

    # --- Telegram ------------------------------------------------------------
    telegram_api_id: int = Field(..., description="Telegram API ID from my.telegram.org")
    telegram_api_hash: str = Field(..., min_length=10)
    telegram_session: str = Field(default="outreach", description="Telethon session name")
    telegram_string_session: str | None = Field(default=None, description="Optional pre-made StringSession")

    # --- Management bot ------------------------------------------------------
    bot_token: str | None = None
    bot_allowed_users: str = Field(default="", description="Comma-separated user IDs allowed to use bot")

    # --- LLM -----------------------------------------------------------------
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:14b"
    ollama_timeout_seconds: float = 60.0

    # --- Database ------------------------------------------------------------
    database_url: str = "postgresql+asyncpg://outreach:outreach@localhost:5432/outreach"

    # --- Search / scanning ---------------------------------------------------
    keywords: str = "барахолка,объявления,вакансии,работа,услуги"
    cities: str = ""
    min_subscribers: int = 200
    max_sample_messages: int = 50
    excluded_channels: str = ""
    excluded_keywords: str = ""

    # --- Rate limits ---------------------------------------------------------
    daily_message_limit: int = 40
    min_delay_seconds: int = 120
    max_delay_seconds: int = 600
    per_recipient_cooldown_hours: int = 24
    global_hourly_limit: int = 20

    # --- Qualification -------------------------------------------------------
    relevance_threshold: float = 0.6
    confidence_threshold: float = 0.75

    # --- Workflow ------------------------------------------------------------
    auto_approve: bool = False
    approval_timeout_hours: int = 48
    followup_delay_hours: int = 72
    max_followups: int = 1

    # --- Retries -------------------------------------------------------------
    max_retries: int = 5
    retry_base_delay: float = 2.0
    retry_max_delay: float = 600.0

    # --- LLM / generation ----------------------------------------------------
    prompt_version: str = "v1"
    similarity_threshold: float = 0.8

    # --- CLI overrides (set by main.py) --------------------------------------
    dry_run: bool = False
    cli_limit: int | None = None
    cli_keywords: list[str] | None = None
    cli_min_subscribers: int | None = None

    # --- Helpers -------------------------------------------------------------
    @property
    def keyword_list(self) -> list[str]:
        src = self.cli_keywords if self.cli_keywords else self._split(self.keywords)
        return [k.strip().lower() for k in src if k.strip()]

    @property
    def city_list(self) -> list[str]:
        return [c.strip() for c in self._split(self.cities) if c.strip()]

    @property
    def excluded_channel_list(self) -> list[str]:
        return [c.strip().lower() for c in self._split(self.excluded_channels) if c.strip()]

    @property
    def excluded_keyword_list(self) -> list[str]:
        return [k.strip().lower() for k in self._split(self.excluded_keywords) if k.strip()]

    @property
    def bot_allowed_user_ids(self) -> list[int]:
        return [int(x) for x in self._split(self.bot_allowed_users) if x.strip()]

    @staticmethod
    def _split(value: str) -> list[str]:
        if not value:
            return []
        return [p for p in value.replace("\n", ",").split(",") if p.strip()]

    @field_validator("relevance_threshold", "confidence_threshold", "similarity_threshold")
    @classmethod
    def _validate_threshold(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("threshold must be in [0, 1]")
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


def reset_settings_cache() -> None:
    """Used in tests to re-read env after mutation."""
    get_settings.cache_clear()


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]
