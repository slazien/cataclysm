"""Achievement endpoints."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.db.database import get_db
from backend.api.dependencies import AuthenticatedUser, get_current_user, get_user_or_anon
from backend.api.schemas.achievement import (
    AchievementListResponse,
    AchievementSchema,
    NewAchievementsResponse,
)
from backend.api.services.achievement_engine import (
    check_achievements,
    get_recent_achievements,
    get_user_achievements,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("", response_model=AchievementListResponse)
async def list_achievements(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AchievementListResponse:
    """Return all achievements with unlock status for the current user.

    Re-evaluates criteria first so achievements earned before the system
    was introduced (or between uploads) are caught up.
    """
    logger.debug("Checking achievements for user %s", current_user.user_id)
    await check_achievements(db, current_user.user_id)
    await db.commit()
    rows = await get_user_achievements(db, current_user.user_id)
    return AchievementListResponse(
        achievements=[AchievementSchema(**r) for r in rows],  # type: ignore[arg-type]
    )


@router.get("/recent", response_model=NewAchievementsResponse)
async def recent_achievements(
    current_user: Annotated[AuthenticatedUser, Depends(get_user_or_anon)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> NewAchievementsResponse:
    """Return newly unlocked achievements and mark them as seen."""
    if current_user.user_id == "anon":
        return NewAchievementsResponse(newly_unlocked=[])
    rows = await get_recent_achievements(db, current_user.user_id)
    return NewAchievementsResponse(
        newly_unlocked=[AchievementSchema(**r) for r in rows],  # type: ignore[arg-type]
    )
