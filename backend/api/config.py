"""Application settings via pydantic-settings."""

from __future__ import annotations

import json

from pydantic_settings import BaseSettings, SettingsConfigDict


def _parse_cors_origins(raw: str) -> list[str]:
    """Parse a CORS origins string, tolerating non-JSON formats.

    Railway's CLI strips inner quotes, turning valid JSON like
    ``["https://a.com"]`` into ``[https://a.com]``.  This handles:
    - Valid JSON arrays: ``["https://a.com","https://b.com"]``
    - Bracketed non-JSON: ``[https://a.com,https://b.com]``
    - Comma-separated: ``https://a.com,https://b.com``
    """
    # Try JSON first
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(x) for x in parsed]
    except (json.JSONDecodeError, ValueError):
        pass

    # Strip brackets and split on commas
    stripped = raw.strip("[] ")
    return [s.strip().strip('"').strip("'") for s in stripped.split(",") if s.strip()]


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

    # CORS — stored as raw string to avoid pydantic-settings' strict JSON
    # parsing of list types, which breaks when Railway strips inner quotes.
    cors_origins_raw: str = '["http://localhost:3000"]'

    # File storage
    session_data_dir: str = "data/session"
    coaching_data_dir: str = "data/coaching"
    equipment_data_dir: str = "data/equipment"

    # Upload limits
    max_upload_size_mb: int = 50

    # Auth
    nextauth_secret: str = ""

    # Debug mode
    debug: bool = False

    # QA testing: bypass OAuth entirely, return a fake dev user for all requests
    dev_auth_bypass: bool = False

    @property
    def cors_origins(self) -> list[str]:
        """Parse CORS origins from the raw string, tolerating Railway's format quirks."""
        return _parse_cors_origins(self.cors_origins_raw)
