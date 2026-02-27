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
