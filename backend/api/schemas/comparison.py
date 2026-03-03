"""Pydantic schemas for multi-driver session comparison."""

from __future__ import annotations

from pydantic import BaseModel


class CornerDeltaSchema(BaseModel):
    """Per-corner speed difference between two sessions."""

    corner_number: int
    speed_diff_mph: float  # positive = A faster
    a_min_speed_mph: float
    b_min_speed_mph: float


class SpeedTracePoint(BaseModel):
    """Speed vs distance data for a single lap."""

    distance_m: list[float]
    speed_mph: list[float]


class SkillDimensionSchema(BaseModel):
    """Aggregate skill scores derived from corner grades."""

    braking: float
    trail_braking: float
    throttle: float
    line: float


class ComparisonResult(BaseModel):
    """Full comparison of two sessions' best laps."""

    session_a_id: str
    session_b_id: str
    session_a_track: str
    session_b_track: str
    session_a_best_lap: float | None  # best lap time in seconds
    session_b_best_lap: float | None
    delta_s: float  # total time delta (positive = A faster)
    distance_m: list[float]  # distance points
    delta_time_s: list[float]  # delta at each point
    corner_deltas: list[CornerDeltaSchema]  # per-corner speed differences
    speed_traces: dict[str, SpeedTracePoint] | None = None
    skill_dimensions: dict[str, SkillDimensionSchema] | None = None
    ai_verdict: str | None = None
    session_a_weather_condition: str | None = None
    session_a_weather_temp_c: float | None = None
    session_b_weather_condition: str | None = None
    session_b_weather_temp_c: float | None = None
