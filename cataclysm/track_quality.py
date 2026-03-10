"""Track data quality confidence scoring."""

from __future__ import annotations

from dataclasses import dataclass

from cataclysm.track_db import OfficialCorner

# Elevation source accuracy rankings
_ELEVATION_SCORES: dict[str, float] = {
    "usgs_3dep": 1.0,
    "copernicus_dem": 0.6,
    "gps_fallback": 0.3,
}

# Corner verification source rankings
_CORNER_SOURCE_SCORES: dict[str, float] = {
    "manual": 1.0,
    "admin": 0.8,
    "auto": 0.3,
}

# Component weights (must sum to 1.0)
_W_FIELD_COMPLETENESS = 0.40
_W_ELEVATION = 0.20
_W_CORNER_VERIFICATION = 0.25
_W_SOURCE_COUNT = 0.15


@dataclass
class QualityScore:
    """Quality confidence score for track data completeness."""

    overall: float  # 0.0 - 1.0
    field_completeness: float  # What fraction of fields are filled
    elevation_quality: float  # 1.0=LIDAR, 0.6=Copernicus, 0.3=GPS, 0.0=none
    corner_verification: float  # 1.0=manual/seed, 0.8=admin-reviewed, 0.3=auto-detected
    source_count: float  # Normalized: how many data sources contributed
    suggested_tier: int  # 1, 2, or 3


def _compute_field_completeness(corners: list[OfficialCorner]) -> float:
    """Compute average field fill rate across all corners.

    Checked fields per corner:
    - direction (set if not None)
    - corner_type (set if not None)
    - elevation_trend (set if not None)
    - camber (set if not None)
    - coaching_notes (set if not None)
    - character (set if not None)
    - lat/lon (both must be set to count as 1 point)
    """
    if not corners:
        return 0.0

    total_fields = 7  # 6 individual + 1 for lat/lon pair
    total_score = 0.0

    for c in corners:
        filled = 0
        if c.direction is not None:
            filled += 1
        if c.corner_type is not None:
            filled += 1
        if c.elevation_trend is not None:
            filled += 1
        if c.camber is not None:
            filled += 1
        if c.coaching_notes is not None:
            filled += 1
        if c.character is not None:
            filled += 1
        if c.lat is not None and c.lon is not None:
            filled += 1
        total_score += filled / total_fields

    return total_score / len(corners)


def _compute_elevation_quality(elevation_source: str | None) -> float:
    """Map elevation source string to quality score."""
    if elevation_source is None:
        return 0.0
    return _ELEVATION_SCORES.get(elevation_source, 0.0)


def _compute_corner_verification(corner_source: str) -> float:
    """Map corner source string to verification quality score."""
    return _CORNER_SOURCE_SCORES.get(corner_source, 0.0)


def _compute_source_count(
    *,
    has_centerline: bool,
    has_elevation_profile: bool,
    has_landmarks: bool,
    has_corners: bool,
    has_track_length: bool,
) -> float:
    """Count how many data sources contributed, normalized to 0.0-1.0."""
    count = sum(
        [
            has_centerline,
            has_elevation_profile,
            has_landmarks,
            has_corners,
            has_track_length,
        ]
    )
    return count / 5.0


def _assign_tier(score: float) -> int:
    """Assign quality tier based on overall score.

    - score < 0.3  -> Tier 1 (auto-detected, draft)
    - 0.3 <= score < 0.7 -> Tier 2 (enriched, needs review)
    - score >= 0.7 -> Tier 3 (verified, production-ready)
    """
    if score >= 0.7:
        return 3
    if score >= 0.3:
        return 2
    return 1


def compute_quality_score(
    corners: list[OfficialCorner],
    *,
    elevation_source: str | None = None,
    corner_source: str = "auto",
    has_centerline: bool = False,
    has_elevation_profile: bool = False,
    has_landmarks: bool = False,
    track_length_m: float | None = None,
) -> QualityScore:
    """Compute a quality confidence score for track data completeness.

    Weighted average:
    - Field completeness (40%): per-corner field fill rate
    - Elevation quality (20%): source accuracy
    - Corner verification (25%): how corners were created
    - Source count (15%): number of data sources used

    Tier assignment:
    - score < 0.3  -> Tier 1 (auto-detected, draft)
    - 0.3 <= score < 0.7 -> Tier 2 (enriched, needs review)
    - score >= 0.7 -> Tier 3 (verified, production-ready)
    """
    field_comp = _compute_field_completeness(corners)
    elev_qual = _compute_elevation_quality(elevation_source)
    corner_ver = _compute_corner_verification(corner_source)
    src_count = _compute_source_count(
        has_centerline=has_centerline,
        has_elevation_profile=has_elevation_profile,
        has_landmarks=has_landmarks,
        has_corners=len(corners) > 0,
        has_track_length=track_length_m is not None,
    )

    overall = (
        _W_FIELD_COMPLETENESS * field_comp
        + _W_ELEVATION * elev_qual
        + _W_CORNER_VERIFICATION * corner_ver
        + _W_SOURCE_COUNT * src_count
    )

    return QualityScore(
        overall=overall,
        field_completeness=field_comp,
        elevation_quality=elev_qual,
        corner_verification=corner_ver,
        source_count=src_count,
        suggested_tier=_assign_tier(overall),
    )
