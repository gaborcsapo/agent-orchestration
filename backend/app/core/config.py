"""
Application configuration with environment variable loading.
Provides helpful error messages for missing or invalid configuration.
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
    )

    # Anthropic Configuration
    anthropic_api_key: str = ""

    # Voyage AI Configuration (for embeddings)
    voyage_api_key: str = ""

    # Fireworks AI Configuration (for fast inference)
    fireworks_api_key: str = ""
    fireworks_vision_model: str = "accounts/jihjihk/deployedModels/llama-v3p2-11b-vision-instruct-s1ctllo1"
    fireworks_llm_model: str = "accounts/jihjihk/deployedModels/gpt-oss-120b-y2vj6irm"

    # MongoDB Configuration
    mongodb_uri: str = ""
    mongodb_db_name: str = "agent_orchestration"

    # Application Settings
    debug: bool = True

    def validate_config(self) -> list[str]:
        """
        Validate configuration and return list of errors.
        Returns empty list if all required config is present.
        """
        errors = []

        # Anthropic key is optional - we use Fireworks AI instead
        # if not self.anthropic_api_key:
        #     errors.append("ANTHROPIC_API_KEY is not set.")

        if not self.mongodb_uri or "username:password" in self.mongodb_uri:
            errors.append(
                "MONGODB_URI is not set or contains placeholder values. "
                "Get your connection string from MongoDB Atlas: https://cloud.mongodb.com"
            )

        if not self.voyage_api_key or self.voyage_api_key == "your-voyage-api-key-here":
            errors.append(
                "VOYAGE_API_KEY is not set. "
                "Get your key at: https://www.voyageai.com/"
            )

        if not self.fireworks_api_key or self.fireworks_api_key == "your-fireworks-api-key-here":
            errors.append(
                "FIREWORKS_API_KEY is not set. "
                "Get your key at: https://fireworks.ai/"
            )

        return errors


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
