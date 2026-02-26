"""Application settings via pydantic-settings."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Cataclysm API configuration.

    Values are loaded from environment variables, falling back to a ``.env``
    file in the project root.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database
    database_url: str = "postgresql+asyncpg://cataclysm:cataclysm@localhost:5432/cataclysm"

    # External APIs
    anthropic_api_key: str = ""

    # CORS
    cors_origins: list[str] = ["http://localhost:3000"]

    # File storage
    session_data_dir: str = "data/session"
    coaching_data_dir: str = "data/coaching"

    # Upload limits
    max_upload_size_mb: int = 50

    # Debug mode
    debug: bool = False
