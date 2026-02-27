"""Pydantic schemas for corner leaderboard endpoints."""

from __future__ import annotations

from pydantic import BaseModel


class CornerRecordInput(BaseModel):
    """Input data for recording a corner time from processed telemetry."""

    corner_number: int
    min_speed_mps: float
    sector_time_s: float
    lap_number: int


class CornerRecordEntry(BaseModel):
    """A single leaderboard entry for a corner."""

    rank: int
    user_name: str
    sector_time_s: float
    min_speed_mps: float
    session_date: str
    is_king: bool = False


class CornerKingEntry(BaseModel):
    """Current king of a specific corner."""

    corner_number: int
    user_name: str
    best_time_s: float


class LeaderboardResponse(BaseModel):
    """Response for per-corner leaderboard."""

    track_name: str
    corner_number: int
    entries: list[CornerRecordEntry]


class KingsResponse(BaseModel):
    """Response for all corner kings on a track."""

    track_name: str
    kings: list[CornerKingEntry]


class OptInRequest(BaseModel):
    """Request body for toggling leaderboard opt-in."""

    opt_in: bool


class OptInResponse(BaseModel):
    """Response for opt-in toggle."""

    leaderboard_opt_in: bool
