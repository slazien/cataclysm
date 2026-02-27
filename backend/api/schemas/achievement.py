"""Pydantic schemas for achievement endpoints."""

from __future__ import annotations

from pydantic import BaseModel


class AchievementSchema(BaseModel):
    """A single achievement with unlock status."""

    id: str
    name: str
    description: str
    criteria_type: str
    criteria_value: float
    tier: str
    icon: str
    unlocked: bool = False
    session_id: str | None = None
    unlocked_at: str | None = None


class AchievementListResponse(BaseModel):
    """Response for listing all achievements."""

    achievements: list[AchievementSchema]


class NewAchievementsResponse(BaseModel):
    """Response for recently unlocked achievements."""

    newly_unlocked: list[AchievementSchema]
