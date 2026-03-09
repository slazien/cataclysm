"""Load track corner configs from PostgreSQL (admin-edited overrides)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.db.models import TrackCornerConfig


async def get_track_corners(
    track_slug: str,
    db: AsyncSession,
) -> list[dict] | None:
    """Load corners from DB if available, else return None.

    Caller falls back to ``track_db.py`` hardcoded corners when None.
    """
    result = await db.execute(
        select(TrackCornerConfig).where(TrackCornerConfig.track_slug == track_slug)
    )
    config = result.scalar_one_or_none()
    if config is None:
        return None
    return config.corners_json  # type: ignore[return-value]
