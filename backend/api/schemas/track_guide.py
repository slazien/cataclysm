"""Pydantic schemas for the track guide endpoint."""

from __future__ import annotations

from pydantic import BaseModel


class TrackGuideCorner(BaseModel):
    """Full corner detail for the track guide."""

    number: int
    name: str
    fraction: float
    direction: str | None = None
    corner_type: str | None = None
    elevation_trend: str | None = None
    camber: str | None = None
    blind: bool = False
    coaching_notes: str | None = None
    character: str | None = None


class KeyCorner(BaseModel):
    """A Type A corner where exit speed is critical."""

    number: int
    name: str
    straight_after_m: float
    coaching_notes: str | None = None
    direction: str | None = None
    blind: bool = False
    camber: str | None = None


class TrackPeculiarity(BaseModel):
    """A corner with a notable characteristic."""

    corner_number: int
    corner_name: str
    description: str


class TrackGuideLandmark(BaseModel):
    """A visual landmark around the track."""

    name: str
    distance_m: float
    landmark_type: str
    description: str | None = None


class TrackGuideResponse(BaseModel):
    """Full track guide response for the Track Briefing Card."""

    track_name: str
    length_m: float | None = None
    elevation_range_m: float | None = None
    country: str = ""
    n_corners: int
    corners: list[TrackGuideCorner]
    key_corners: list[KeyCorner]
    peculiarities: list[TrackPeculiarity]
    landmarks: list[TrackGuideLandmark]
