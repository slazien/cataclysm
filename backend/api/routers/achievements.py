"""Achievement endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.db.database import get_db
from backend.api.dependencies import AuthenticatedUser, get_current_user
from backend.api.schemas.achievement import (
    AchievementListResponse,
    AchievementSchema,
    NewAchievementsResponse,
)
from backend.api.services.achievement_engine import (
    get_recent_achievements,
    get_user_achievements,
)

router = APIRouter()


@router.get("", response_model=AchievementListResponse)
async def list_achievements(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AchievementListResponse:
    """Return all achievements with unlock status for the current user."""
    rows = await get_user_achievements(db, current_user.user_id)
    return AchievementListResponse(
        achievements=[AchievementSchema(**r) for r in rows],  # type: ignore[arg-type]
    )


@router.get("/recent", response_model=NewAchievementsResponse)
async def recent_achievements(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> NewAchievementsResponse:
    """Return newly unlocked achievements and mark them as seen."""
    rows = await get_recent_achievements(db, current_user.user_id)
    return NewAchievementsResponse(
        newly_unlocked=[AchievementSchema(**r) for r in rows],  # type: ignore[arg-type]
    )
