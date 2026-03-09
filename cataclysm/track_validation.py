"""Automated track data validation gates."""

from __future__ import annotations

from dataclasses import dataclass, field

from cataclysm.track_db import TrackLayout

# Minimum fraction gap between consecutive corners.
_MIN_FRACTION_SPACING = 0.01
_SPACING_EPS = 1e-9  # Floating-point tolerance for spacing comparison

# Quality score weights per field.
_WEIGHTS: dict[str, float] = {
    "direction": 0.20,
    "corner_type": 0.15,
    "elevation_trend": 0.15,
    "coaching_notes": 0.20,
    "camber": 0.10,
    "lat_lon": 0.10,
    "length_m": 0.10,
}


@dataclass
class ValidationResult:
    """Result of running validation gates on a TrackLayout."""

    fraction_monotonic: bool
    fraction_spacing: bool  # No two corners within 0.01
    all_directions_set: bool
    all_coaching_notes: bool
    quality_score: float  # 0.0–1.0
    errors: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return self.fraction_monotonic and self.fraction_spacing


def validate_track(layout: TrackLayout) -> ValidationResult:
    """Run all validation checks on a TrackLayout."""
    errors: list[str] = []
    corners = layout.corners

    # --- fraction monotonicity ---
    fraction_monotonic = True
    for i in range(1, len(corners)):
        if corners[i].fraction <= corners[i - 1].fraction:
            fraction_monotonic = False
            errors.append(
                f"Corner {corners[i].number} fraction {corners[i].fraction} "
                f"<= previous {corners[i - 1].fraction}"
            )

    # --- fraction spacing ---
    fraction_spacing = True
    for i in range(1, len(corners)):
        gap = abs(corners[i].fraction - corners[i - 1].fraction)
        if gap < _MIN_FRACTION_SPACING - _SPACING_EPS:
            fraction_spacing = False
            errors.append(
                f"Corners {corners[i - 1].number}–{corners[i].number} too close: gap={gap:.4f}"
            )

    # --- all directions set ---
    all_directions_set = all(c.direction is not None for c in corners) if corners else False

    # --- all coaching notes set ---
    all_coaching_notes = all(c.coaching_notes is not None for c in corners) if corners else False

    # --- quality score ---
    quality_score = _compute_quality_score(layout)

    return ValidationResult(
        fraction_monotonic=fraction_monotonic,
        fraction_spacing=fraction_spacing,
        all_directions_set=all_directions_set,
        all_coaching_notes=all_coaching_notes,
        quality_score=quality_score,
        errors=errors,
    )


def _compute_quality_score(layout: TrackLayout) -> float:
    """Compute a 0.0–1.0 quality score based on field completeness."""
    corners = layout.corners
    if not corners:
        return 0.0

    total_weight = sum(_WEIGHTS.values())
    per_corner_scores: list[float] = []

    for c in corners:
        earned = 0.0
        if c.direction is not None:
            earned += _WEIGHTS["direction"]
        if c.corner_type is not None:
            earned += _WEIGHTS["corner_type"]
        if c.elevation_trend is not None:
            earned += _WEIGHTS["elevation_trend"]
        if c.coaching_notes is not None:
            earned += _WEIGHTS["coaching_notes"]
        if c.camber is not None:
            earned += _WEIGHTS["camber"]
        if c.lat is not None and c.lon is not None:
            earned += _WEIGHTS["lat_lon"]
        # length_m is layout-level, same contribution for every corner
        if layout.length_m is not None:
            earned += _WEIGHTS["length_m"]
        per_corner_scores.append(earned / total_weight)

    score = sum(per_corner_scores) / len(per_corner_scores)
    return round(score, 10)  # Avoid floating-point dust like 0.9999999999999999
