"""Pydantic schemas for analysis endpoints."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class CornerSchema(BaseModel):
    """Single corner with extracted KPIs."""

    number: int
    entry_distance_m: float
    exit_distance_m: float
    apex_distance_m: float
    min_speed_mph: float
    brake_point_m: float | None = None
    peak_brake_g: float | None = None
    throttle_commit_m: float | None = None
    apex_type: str


class CornerResponse(BaseModel):
    """Corners detected on the best lap."""

    session_id: str
    lap_number: int
    corners: list[CornerSchema]


class AllLapsCornerResponse(BaseModel):
    """Corner KPIs for every lap in the session."""

    session_id: str
    laps: dict[str, list[CornerSchema]]


class ConsistencyResponse(BaseModel):
    """Session consistency metrics (serialized dataclass)."""

    session_id: str
    data: dict[str, Any]


class GripResponse(BaseModel):
    """Grip limit estimation results (serialized dataclass)."""

    session_id: str
    data: dict[str, Any]


class GainsResponse(BaseModel):
    """Three-tier gain estimation results (serialized dataclass)."""

    session_id: str
    data: dict[str, Any]


class IdealLapResponse(BaseModel):
    """Composite ideal lap stitched from best segments."""

    session_id: str
    distance_m: list[float]
    speed_mph: list[float]
    segment_sources: list[list[Any]]


class DeltaResponse(BaseModel):
    """Delta-T between two laps at each distance point."""

    session_id: str
    ref_lap: int
    comp_lap: int
    distance_m: list[float]
    delta_s: list[float]
    total_delta_s: float


class LinkedChartResponse(BaseModel):
    """Bundled data for synchronized linked charts."""

    session_id: str
    laps: list[int]
    distance_m: list[float]
    speed_traces: dict[str, list[float]]
    lateral_g_traces: dict[str, list[float]]
    longitudinal_g_traces: dict[str, list[float]]
    heading_traces: dict[str, list[float]]
