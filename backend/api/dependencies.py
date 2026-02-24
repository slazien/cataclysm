"""FastAPI dependency injection functions."""

from __future__ import annotations

from functools import lru_cache

from backend.api.config import Settings


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the singleton application settings."""
    return Settings()
