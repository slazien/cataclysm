"""Schemas for Season Wrapped / Year in Review endpoint."""

from __future__ import annotations

from pydantic import BaseModel


class WrappedHighlight(BaseModel):
    """A notable achievement or stat from the year."""

    label: str
    value: str
    category: str  # "stat" | "achievement" | "milestone"


class WrappedResponse(BaseModel):
    """Annual personalized recap."""

    year: int
    total_sessions: int
    total_laps: int
    total_distance_km: float
    tracks_visited: list[str]
    total_track_time_hours: float
    biggest_improvement_track: str | None
    biggest_improvement_s: float | None
    best_consistency_score: float
    personality: str
    personality_description: str
    top_corner_grade: str | None
    highlights: list[WrappedHighlight]
