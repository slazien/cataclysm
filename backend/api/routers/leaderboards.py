"""Corner leaderboard endpoints -- King of the Corner."""

from __future__ import annotations

import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.db.database import get_db
from backend.api.dependencies import AuthenticatedUser, get_user_or_anon
from backend.api.schemas.leaderboard import (
    KingsResponse,
    LeaderboardResponse,
)
from backend.api.services.leaderboard_store import (
    get_corner_leaderboard,
    get_kings,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/{track}/corners", response_model=LeaderboardResponse)
async def corner_leaderboard(
    track: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_user_or_anon)],
    db: Annotated[AsyncSession, Depends(get_db)],
    corner: Annotated[int, Query(description="Corner number", ge=1)],
    limit: Annotated[int, Query(description="Max entries", ge=1, le=50)] = 10,
    category: Annotated[
        Literal["sector_time", "min_speed", "brake_point", "consistency"],
        Query(description="Ranking metric"),
    ] = "sector_time",
) -> LeaderboardResponse:
    """Get per-corner rankings for a track."""
    logger.debug("Leaderboard query: track=%s corner=%d category=%s", track, corner, category)
    entries = await get_corner_leaderboard(db, track, corner, limit=limit, category=category)
    return LeaderboardResponse(
        track_name=track,
        corner_number=corner,
        entries=entries,
    )


@router.get("/{track}/kings", response_model=KingsResponse)
async def corner_kings(
    track: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_user_or_anon)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> KingsResponse:
    """Get current kings for all corners on a track."""
    kings = await get_kings(db, track)
    return KingsResponse(track_name=track, kings=kings)
