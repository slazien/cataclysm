"""Automated track data validation gates.

Separates correctness (hard gates) from completeness (quality score).
Any correctness issue → is_valid=False. Quality score measures how much
optional coaching metadata is filled in.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from cataclysm.track_db import OfficialCorner

# Minimum fraction gap between consecutive corners.
_MIN_FRACTION_SPACING = 0.01
_SPACING_EPS = 1e-9  # Floating-point tolerance for spacing comparison

# Maximum grade (rise/run) between consecutive elevation points.
_MAX_GRADE = 0.40  # 40%

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


@dataclass(frozen=True)
class ValidationIssue:
    """A single validation issue found during track validation."""

    severity: str  # "error" | "warning"
    message: str


@dataclass
class ValidationResult:
    """Result of running validation gates on track data."""

    fraction_monotonic: bool
    fraction_spacing: bool  # No two corners within 0.01
    all_directions_set: bool
    all_coaching_notes: bool
    quality_score: float  # 0.0-1.0 (completeness metric)
    issues: list[ValidationIssue] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)  # Legacy, kept for compat

    @property
    def is_valid(self) -> bool:
        """False if ANY issue has severity 'error'."""
        return not any(i.severity == "error" for i in self.issues)


def validate_track(
    corners: list[OfficialCorner],
    *,
    length_m: float | None = None,
    elevation_distances: list[float] | None = None,
    elevation_values: list[float] | None = None,
) -> ValidationResult:
    """Run all validation checks on track data.

    Correctness gates (severity='error') cause is_valid=False.
    Completeness issues (severity='warning') only affect quality_score.
    """
    issues: list[ValidationIssue] = []
    errors: list[str] = []  # Legacy list

    # --- corner count gate ---
    if len(corners) == 0:
        issues.append(ValidationIssue("error", "Track has zero corners"))

    # --- fraction domain: every fraction must be in [0.0, 1.0) ---
    for c in corners:
        if c.fraction < 0.0 or c.fraction >= 1.0:
            issues.append(
                ValidationIssue(
                    "error",
                    f"Corner {c.number} fraction {c.fraction} outside [0.0, 1.0)",
                )
            )

    # --- fraction monotonicity ---
    fraction_monotonic = True
    for i in range(1, len(corners)):
        if corners[i].fraction <= corners[i - 1].fraction:
            fraction_monotonic = False
            msg = (
                f"Corner {corners[i].number} fraction {corners[i].fraction} "
                f"<= previous {corners[i - 1].fraction}"
            )
            issues.append(ValidationIssue("error", msg))
            errors.append(msg)

    # --- fraction spacing (consecutive) ---
    fraction_spacing = True
    for i in range(1, len(corners)):
        gap = abs(corners[i].fraction - corners[i - 1].fraction)
        if gap < _MIN_FRACTION_SPACING - _SPACING_EPS:
            fraction_spacing = False
            msg = f"Corners {corners[i - 1].number}-{corners[i].number} too close: gap={gap:.4f}"
            issues.append(ValidationIssue("error", msg))
            errors.append(msg)

    # --- wrap-around spacing (last corner → first corner across lap boundary) ---
    if len(corners) >= 2:
        wrap_gap = (1.0 - corners[-1].fraction) + corners[0].fraction
        if wrap_gap < _MIN_FRACTION_SPACING - _SPACING_EPS:
            fraction_spacing = False
            msg = (
                f"Corners {corners[-1].number}-{corners[0].number} "
                f"wrap-around too close: gap={wrap_gap:.4f}"
            )
            issues.append(ValidationIssue("error", msg))
            errors.append(msg)

    # --- track length sanity ---
    if length_m is not None and length_m <= 0:
        issues.append(ValidationIssue("error", f"Track length must be positive, got {length_m}"))

    # --- elevation profile checks ---
    if elevation_distances is not None or elevation_values is not None:
        _validate_elevation(elevation_distances, elevation_values, issues)

    # --- all directions set ---
    all_directions_set = all(c.direction is not None for c in corners) if corners else False

    # --- all coaching notes set ---
    all_coaching_notes = all(c.coaching_notes is not None for c in corners) if corners else False

    # --- quality score (completeness only, not correctness) ---
    quality_score = _compute_quality_score(corners, length_m=length_m)

    return ValidationResult(
        fraction_monotonic=fraction_monotonic,
        fraction_spacing=fraction_spacing,
        all_directions_set=all_directions_set,
        all_coaching_notes=all_coaching_notes,
        quality_score=quality_score,
        issues=issues,
        errors=errors,
    )


def _validate_elevation(
    distances: list[float] | None,
    values: list[float] | None,
    issues: list[ValidationIssue],
) -> None:
    """Validate elevation profile data, appending issues in-place."""
    if distances is None or values is None:
        issues.append(
            ValidationIssue(
                "error",
                "Elevation data incomplete: both distances_m and elevations_m required",
            )
        )
        return

    if len(distances) != len(values):
        issues.append(
            ValidationIssue(
                "error",
                f"Elevation length mismatch: {len(distances)} distances vs {len(values)} values",
            )
        )
        return  # Can't do further checks with mismatched lengths

    # NaN / infinity check
    for i, (d, v) in enumerate(zip(distances, values, strict=True)):
        if math.isnan(d) or math.isinf(d):
            issues.append(ValidationIssue("error", f"Elevation distance[{i}] is NaN or Inf"))
            return
        if math.isnan(v) or math.isinf(v):
            issues.append(ValidationIssue("error", f"Elevation value[{i}] is NaN or Inf"))
            return

    # Strictly increasing distances
    for i in range(1, len(distances)):
        if distances[i] <= distances[i - 1]:
            issues.append(
                ValidationIssue(
                    "error",
                    f"Elevation distances not strictly increasing at index {i}: "
                    f"{distances[i]} <= {distances[i - 1]}",
                )
            )
            return  # One error is enough

    # Grade spike check
    for i in range(1, len(distances)):
        d_dist = distances[i] - distances[i - 1]
        if d_dist <= 0:
            continue  # Already caught above
        grade = abs(values[i] - values[i - 1]) / d_dist
        if grade > _MAX_GRADE:
            issues.append(
                ValidationIssue(
                    "error",
                    f"Elevation grade spike at index {i}: "
                    f"{grade:.1%} exceeds {_MAX_GRADE:.0%} limit",
                )
            )
            return  # One error is enough


def _compute_quality_score(
    corners: list[OfficialCorner],
    *,
    length_m: float | None = None,
) -> float:
    """Compute a 0.0-1.0 quality score based on field completeness."""
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
        if length_m is not None:
            earned += _WEIGHTS["length_m"]
        per_corner_scores.append(earned / total_weight)

    score = sum(per_corner_scores) / len(per_corner_scores)
    return round(score, 10)  # Avoid floating-point dust like 0.9999999999999999
