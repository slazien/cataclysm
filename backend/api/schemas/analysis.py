"""Pydantic schemas for analysis endpoints."""

from __future__ import annotations

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
    laps: dict[int, list[CornerSchema]]


class LapConsistencySchema(BaseModel):
    """Lap-to-lap timing consistency metrics."""

    std_dev_s: float
    spread_s: float
    mean_abs_consecutive_delta_s: float
    max_consecutive_delta_s: float
    consistency_score: float
    lap_numbers: list[int]
    lap_times_s: list[float]
    consecutive_deltas_s: list[float]


class CornerConsistencySchema(BaseModel):
    """Per-corner consistency across laps."""

    corner_number: int
    min_speed_std_mph: float
    min_speed_range_mph: float
    brake_point_std_m: float | None = None
    throttle_commit_std_m: float | None = None
    consistency_score: float


class ConsistencyResponse(BaseModel):
    """Session consistency metrics."""

    session_id: str
    lap_consistency: LapConsistencySchema
    corner_consistency: list[CornerConsistencySchema]


class GripResponse(BaseModel):
    """Grip limit estimation results."""

    session_id: str
    composite_max_g: float
    envelope_lat_g: list[float]
    envelope_lon_g: list[float]
    weights: dict[str, float]


class SegmentGainSchema(BaseModel):
    """Time gain potential for a single segment."""

    segment_name: str
    is_corner: bool
    best_time_s: float
    avg_time_s: float
    gain_s: float
    best_lap: int


class GainsResponse(BaseModel):
    """Three-tier gain estimation results."""

    session_id: str
    consistency_total_gain_s: float
    composite_gain_s: float
    theoretical_gain_s: float
    segment_gains: list[SegmentGainSchema]


class IdealLapResponse(BaseModel):
    """Composite ideal lap stitched from best segments."""

    session_id: str
    distance_m: list[float]
    speed_mph: list[float]
    segment_sources: list[tuple[str, int]]


class DeltaResponse(BaseModel):
    """Delta-T between two laps at each distance point."""

    session_id: str
    ref_lap: int
    comp_lap: int
    distance_m: list[float]
    delta_s: list[float]


class LinkedChartResponse(BaseModel):
    """Bundled data for synchronized linked charts."""

    session_id: str
    laps: list[int]
    distance_m: list[float]
    speed_traces: dict[int, list[float]]
    lateral_g_traces: dict[int, list[float]]
    longitudinal_g_traces: dict[int, list[float]]
    heading_traces: dict[int, list[float]]
