"""Pydantic schemas for session-related endpoints."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class SessionSummary(BaseModel):
    """Lightweight session summary returned in list views."""

    model_config = ConfigDict(from_attributes=True)

    session_id: str
    track_name: str
    session_date: str
    n_laps: int | None = None
    n_clean_laps: int | None = None
    best_lap_time_s: float | None = None
    top3_avg_time_s: float | None = None
    avg_lap_time_s: float | None = None
    consistency_score: float | None = None
    session_score: float | None = None
    tire_model: str | None = None
    compound_category: str | None = None
    equipment_profile_name: str | None = None
    gps_quality_score: float | None = None
    gps_quality_grade: str | None = None
    weather_temp_c: float | None = None
    weather_condition: str | None = None
    weather_humidity_pct: float | None = None
    weather_wind_kmh: float | None = None
    weather_precipitation_mm: float | None = None


class SessionList(BaseModel):
    """Paginated list of session summaries."""

    items: list[SessionSummary]
    total: int


class LapSummary(BaseModel):
    """Summary statistics for a single lap."""

    lap_number: int
    lap_time_s: float
    lap_distance_m: float
    max_speed_mps: float
    is_clean: bool = True
    tags: list[str] = []


class LapData(BaseModel):
    """Columnar resampled telemetry data for a single lap.

    Each list contains values at uniform 0.7m distance intervals.
    """

    lap_number: int
    distance_m: list[float]
    speed_mph: list[float]
    lat: list[float]
    lon: list[float]
    heading_deg: list[float]
    lateral_g: list[float]
    longitudinal_g: list[float]
    lap_time_s: list[float]
    altitude_m: list[float] | None = None


class UploadResponse(BaseModel):
    """Response after uploading one or more CSV files."""

    session_ids: list[str]
    message: str
