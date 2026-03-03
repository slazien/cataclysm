"""Pydantic schemas for the progress rate leaderboard."""

from __future__ import annotations

from pydantic import BaseModel


class ProgressEntry(BaseModel):
    """A single entry in the progress rate leaderboard."""

    rank: int
    user_name: str
    improvement_rate_s: float  # seconds improved per session (negative = getting faster)
    n_sessions: int
    best_lap_first: float  # best lap in first session
    best_lap_latest: float  # best lap in most recent session
    total_improvement_s: float


class ProgressLeaderboardResponse(BaseModel):
    """Response for progress rate leaderboard."""

    track_name: str
    entries: list[ProgressEntry]
    your_rank: int | None = None
    your_percentile: float | None = None  # 0-100, lower = better
