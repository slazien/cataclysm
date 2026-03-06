"""Pydantic schemas for session sharing and comparison."""

from __future__ import annotations

from pydantic import BaseModel


class ShareCreateRequest(BaseModel):
    """Request body for creating a share link."""

    session_id: str


class ShareCreateResponse(BaseModel):
    """Response after creating a share link."""

    token: str
    share_url: str
    track_name: str
    expires_at: str


class ShareMetadata(BaseModel):
    """Public metadata for a share token (no auth required)."""

    token: str
    track_name: str
    inviter_name: str
    best_lap_time_s: float | None
    created_at: str
    expires_at: str
    is_expired: bool


class PublicSessionView(BaseModel):
    """Rich public view data for a shared session."""

    token: str
    track_name: str
    session_date: str
    driver_name: str
    is_expired: bool
    best_lap_time_s: float | None = None
    n_laps: int | None = None
    consistency_score: float | None = None  # 0-100
    session_score: float | None = None  # 0-100
    top_speed_mph: float | None = None
    skill_braking: float | None = None  # 0-100
    skill_trail_braking: float | None = None
    skill_throttle: float | None = None
    skill_line: float | None = None
    coaching_summary: str | None = None
    track_coords: dict[str, list[float]] | None = None


class ShareComparisonResponse(BaseModel):
    """Comparison result from a share upload."""

    token: str
    session_a_id: str
    session_b_id: str
    session_a_track: str
    session_b_track: str
    session_a_best_lap: float | None
    session_b_best_lap: float | None
    delta_s: float
    distance_m: list[float]
    delta_time_s: list[float]
    corner_deltas: list[dict[str, object]]
    speed_traces: dict[str, object] | None = None
    skill_dimensions: dict[str, object] | None = None
    ai_verdict: str | None = None
    track_coords: dict[str, list[float]] | None = None
