"""
Application configuration with environment variable loading.
Simplified configuration for the negotiation system (no MongoDB).
"""
from __future__ import annotations

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore extra fields from old configs
    )

    # Anthropic Configuration
    anthropic_api_key: str = ""

    # Application Settings
    debug: bool = True

    # Negotiation Settings
    max_negotiation_turns: int = 10
    deadlock_threshold: int = 3  # Consecutive no-progress turns before deadlock

    def validate_config(self) -> list[str]:
        """
        Validate configuration and return list of errors.
        Returns empty list if all required config is present.
        """
        errors = []

        if not self.anthropic_api_key or self.anthropic_api_key == "your-anthropic-api-key-here":
            errors.append(
                "ANTHROPIC_API_KEY is not set. "
                "Get your key at: https://console.anthropic.com/settings/keys"
            )

        return errors


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
