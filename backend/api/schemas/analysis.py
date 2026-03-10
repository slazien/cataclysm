"""Pydantic schemas for analysis endpoints."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


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
    direction: str | None = None
    character: str | None = None
    corner_type_hint: str | None = None
    elevation_trend: str | None = None
    camber: str | None = None
    blind: bool = False
    coaching_notes: str | None = None
    banking_deg: float | None = None
    name: str | None = None
    nominal_distance_m: float | None = None
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
    lateral_g_traces: dict[str, list[float]] | None = None
    longitudinal_g_traces: dict[str, list[float]] | None = None
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
    calibrated: bool = False


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
    linked_group_id: int | None = None  # non-null if part of a chicane/esses group


class OptimalComparisonResponse(BaseModel):
    """Per-corner speed gap comparison against the physics-optimal profile."""

    session_id: str
    corner_opportunities: list[CornerOpportunitySchema]
    actual_lap_time_s: float
    optimal_lap_time_s: float
    total_gap_s: float  # actual - optimal (positive = driver is slower)
    is_valid: bool = True
    invalid_reasons: list[str] = Field(default_factory=list)


class CornerLineProfileSchema(BaseModel):
    """Line analysis for a single corner across all laps."""

    corner_number: int
    n_laps: int
    d_entry_median: float  # meters from reference at entry
    d_apex_median: float  # meters from reference at apex
    d_exit_median: float  # meters from reference at exit
    apex_fraction_median: float  # 0.0=entry, 1.0=exit
    d_apex_sd: float  # lateral SD at apex (consistency)
    line_error_type: str  # early_apex, late_apex, wide_entry, etc.
    severity: str  # minor, moderate, major
    consistency_tier: str  # expert, consistent, developing, novice
    allen_berg_type: str  # A, B, C
    straight_after_m: float = 0.0
    priority_rank: int = 0
    best_lap_number: int | None = None
    best_exit_speed_mps: float | None = None
    best_segment_time_s: float | None = None
    best_ranking_method: str | None = None
    best_d_entry: float | None = None
    best_d_apex: float | None = None
    best_d_exit: float | None = None
    median_segment_time_s: float | None = None
    median_exit_speed_mps: float | None = None


class LateralOffsetTraceSchema(BaseModel):
    """Lateral offset trace for a single lap."""

    lap_number: int
    offsets_m: list[float]  # signed offset at each distance point


class LapSpatialTraceSchema(BaseModel):
    """Per-lap ENU coordinates + speed for bird's-eye corner map."""

    lap_number: int
    e: list[float]  # East coords (meters from session origin)
    n: list[float]  # North coords (meters from session origin)
    speed_mps: list[float]  # speed at each point


class LineAnalysisResponse(BaseModel):
    """Full line analysis: corner profiles + per-lap lateral offsets."""

    session_id: str
    available: bool  # False if GPS quality too low or too few laps
    corner_profiles: list[CornerLineProfileSchema]
    distance_m: list[float]  # shared distance grid
    traces: list[LateralOffsetTraceSchema]  # per-lap lateral offsets
    reference_e: list[float]  # reference centerline East coords
    reference_n: list[float]  # reference centerline North coords
    n_laps_used: int  # laps used to build reference
    lap_traces: list[LapSpatialTraceSchema] = Field(
        default_factory=list, description="Per-lap ENU + speed for corner map"
    )
