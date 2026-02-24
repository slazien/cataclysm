"""Pydantic schemas for cross-session trend endpoints."""

from __future__ import annotations

from pydantic import BaseModel


class SessionTrendEntry(BaseModel):
    """A single session's metrics within a trend series."""

    session_id: str
    session_date: str
    best_lap_time_s: float
    top3_avg_time_s: float
    avg_lap_time_s: float
    consistency_score: float
    n_laps: int
    n_clean_laps: int


class TrendAnalysisResponse(BaseModel):
    """Cross-session trend data for a single track."""

    track_name: str
    n_sessions: int
    sessions: list[SessionTrendEntry]
    best_lap_trend: list[float]
    top3_avg_trend: list[float]
    consistency_trend: list[float]
    theoretical_trend: list[float]
    corner_min_speed_trends: dict[int, list[float | None]]
    corner_brake_std_trends: dict[int, list[float | None]]
    corner_consistency_trends: dict[int, list[float | None]]


class MilestoneSchema(BaseModel):
    """A notable achievement detected across sessions."""

    session_id: str
    session_date: str
    category: str
    description: str
    value: float


class MilestoneResponse(BaseModel):
    """List of milestones for a track."""

    track_name: str
    milestones: list[MilestoneSchema]
