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
    brake_point_lat: float | None = None
    brake_point_lon: float | None = None
    apex_lat: float | None = None
    apex_lon: float | None = None
    landmark_ref: str | None = None


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


class SectorSplitSchema(BaseModel):
    """One sector's time for a single lap."""

    sector_name: str
    time_s: float
    is_personal_best: bool = False


class LapSectorSplitsSchema(BaseModel):
    """All sector splits for a single lap."""

    lap_number: int
    total_time_s: float
    splits: list[SectorSplitSchema]


class SectorResponse(BaseModel):
    """Per-lap sector splits with composite time."""

    session_id: str
    segments: list[dict[str, Any]]
    lap_splits: list[LapSectorSplitsSchema]
    best_sector_times: dict[str, float]
    best_sector_laps: dict[str, int]
    composite_time_s: float


class VehicleParamsSchema(BaseModel):
    """Vehicle parameters used by the velocity solver."""

    mu: float
    max_accel_g: float
    max_decel_g: float
    max_lateral_g: float
    top_speed_mps: float


class GPSQualityResponse(BaseModel):
    """GPS quality assessment results."""

    session_id: str
    data: dict[str, Any]


class OptimalProfileResponse(BaseModel):
    """Physics-optimal velocity profile for a track."""

    session_id: str
    distance_m: list[float]
    optimal_speed_mph: list[float]
    max_cornering_speed_mph: list[float]
    brake_points: list[float]
    throttle_points: list[float]
    lap_time_s: float
    vehicle_params: VehicleParamsSchema
    equipment_profile_id: str | None = None


class DegradationEventSchema(BaseModel):
    """A detected degradation event for a specific corner."""

    corner_number: int
    metric: str
    start_lap: int
    end_lap: int
    slope: float
    r_squared: float
    severity: str
    description: str
    values: list[float]
    lap_numbers: list[int]


class DegradationResponse(BaseModel):
    """Brake fade and tire degradation analysis results."""

    session_id: str
    events: list[DegradationEventSchema]
    has_brake_fade: bool
    has_tire_degradation: bool


class CornerSensitivitySchema(BaseModel):
    """Speed sensitivity for a single corner."""

    corner_number: int
    sensitivity_s: float  # seconds saved per +1 mph min speed
    min_speed_mph: float
    arc_length_m: float


class SpeedSensitivityResponse(BaseModel):
    """Per-corner speed sensitivity for a session."""

    session_id: str
    corners: list[CornerSensitivitySchema]
    vehicle_params: VehicleParamsSchema


class GGPointSchema(BaseModel):
    """A single point in the G-G diagram."""

    lat_g: float
    lon_g: float
    distance_m: float
    corner_number: int | None = None


class CornerGGSummarySchema(BaseModel):
    """G-G utilization summary for a single corner."""

    corner_number: int
    utilization_pct: float
    max_lat_g: float
    max_lon_g: float
    point_count: int


class GGDiagramResponse(BaseModel):
    """G-G diagram data with traction circle utilization."""

    session_id: str
    lap_number: int
    points: list[GGPointSchema]
    overall_utilization_pct: float
    observed_max_g: float
    per_corner: list[CornerGGSummarySchema]


class CornerOpportunitySchema(BaseModel):
    """Speed gap for a single corner vs the physics-optimal profile."""

    corner_number: int
    actual_min_speed_mph: float
    optimal_min_speed_mph: float
    speed_gap_mph: float  # optimal - actual (positive = driver is slower)
    brake_gap_m: float | None = None  # positive = driver brakes later than optimal
    time_cost_s: float  # time lost vs optimal in this corner zone


class OptimalComparisonResponse(BaseModel):
    """Per-corner speed gap comparison against the physics-optimal profile."""

    session_id: str
    corner_opportunities: list[CornerOpportunitySchema]
    actual_lap_time_s: float
    optimal_lap_time_s: float
    total_gap_s: float  # actual - optimal (positive = driver is slower)
