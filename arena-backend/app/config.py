"""Configuration for Arena Backend."""
from __future__ import annotations
from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Arena Backend settings loaded from environment variables."""

    # API Keys
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")

    # MongoDB
    mongodb_uri: str = Field(default="mongodb://localhost:27017", alias="MONGODB_URI")
    mongodb_db_name: str = Field(default="agent_orchestration", alias="MONGODB_DB_NAME")

    # Agent Backend URLs
    agent_a_url: str = Field(default="http://localhost:8001", alias="AGENT_A_URL")
    agent_b_url: str = Field(default="http://localhost:8002", alias="AGENT_B_URL")

    # Server
    port: int = Field(default=8000, alias="PORT")
    debug: bool = Field(default=True, alias="DEBUG")

    # Negotiation settings
    max_turns: int = Field(default=10, alias="MAX_NEGOTIATION_TURNS")

    class Config:
        env_file = ".env"
        extra = "ignore"

    def validate_config(self) -> list[str]:
        """Validate configuration and return list of errors."""
        errors = []
        if not self.anthropic_api_key:
            errors.append("ANTHROPIC_API_KEY is not set")
        if not self.mongodb_uri:
            errors.append("MONGODB_URI is not set")
        return errors


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
