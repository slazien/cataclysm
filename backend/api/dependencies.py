"""FastAPI dependency injection functions."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.config import Settings
from backend.api.db.database import async_session_factory


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the singleton application settings."""
    return Settings()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session for request-scoped DI."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
