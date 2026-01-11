"""Configuration for Agent Backend."""
from __future__ import annotations
import os
from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Agent Backend settings loaded from environment variables."""

    # Agent identification
    agent_id: str = Field(default="A", alias="AGENT_ID")

    # API Keys
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")

    # MongoDB
    mongodb_uri: str = Field(default="mongodb://localhost:27017", alias="MONGODB_URI")
    mongodb_db_name: str = Field(default="agent_orchestration", alias="MONGODB_DB_NAME")

    # Arena URL for callbacks
    arena_url: str = Field(default="http://localhost:8000", alias="ARENA_URL")

    # Server
    port: int = Field(default=8001, alias="PORT")
    debug: bool = Field(default=True, alias="DEBUG")

    class Config:
        env_file = ".env"
        extra = "ignore"

    @property
    def audit_collection(self) -> str:
        """Get the audit collection name for this agent."""
        return f"agent_{self.agent_id.lower()}_audit"

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
