"""Visual landmark system for converting abstract distances to cockpit references.

Maps track distances to curated visual landmarks (brake boards, structures,
barriers, etc.) so the AI coaching output references things drivers can
actually see from the cockpit instead of raw meter distances.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np
import pandas as pd

from cataclysm.corners import Corner


class LandmarkType(Enum):
    """Categories of visual landmarks around a circuit."""

    brake_board = "brake_board"
    structure = "structure"
    barrier = "barrier"
    road = "road"
    curbing = "curbing"
    natural = "natural"
    marshal = "marshal"
    sign = "sign"


@dataclass(frozen=True)
class Landmark:
    """A curated visual reference point on the track."""

    name: str
    distance_m: float
    landmark_type: LandmarkType
    lat: float | None = None
    lon: float | None = None
    description: str | None = None


@dataclass(frozen=True)
class LandmarkReference:
    """A resolved reference: the nearest landmark to a query point."""

    landmark: Landmark
    offset_m: float  # signed: positive = landmark is ahead of query point

    def format_reference(self) -> str:
        """Return a human-readable spatial reference string.

        Examples:
            "at the 200m board"
            "15m before the access road"
            "10m past the tire wall end"
        """
        abs_offset = abs(self.offset_m)
        if abs_offset < 5.0:
            return f"at the {self.landmark.name}"
        if self.offset_m > 0:
            return f"{abs_offset:.0f}m before the {self.landmark.name}"
        return f"{abs_offset:.0f}m past the {self.landmark.name}"


# Maximum distance from a query point to consider a landmark relevant
MAX_LANDMARK_DISTANCE_M = 150.0

# Preferred landmark types for brake point lookups (higher priority)
_BRAKE_PREFERRED_TYPES = {LandmarkType.brake_board, LandmarkType.sign, LandmarkType.structure}


def find_nearest_landmark(
    query_distance_m: float,
    landmarks: list[Landmark],
    *,
    max_distance_m: float = MAX_LANDMARK_DISTANCE_M,
    preferred_types: set[LandmarkType] | None = None,
) -> LandmarkReference | None:
    """Find the nearest landmark to a query distance.

    Parameters
    ----------
    query_distance_m:
        The track distance to find a landmark near.
    landmarks:
        Available landmarks to search.
    max_distance_m:
        Maximum distance from query to consider a landmark.
    preferred_types:
        If provided, landmarks of these types get priority when within
        range.  A preferred landmark within ``max_distance_m`` beats a
        closer non-preferred landmark.

    Returns
    -------
    LandmarkReference or None if no landmark is within range.
    """
    if not landmarks:
        return None

    best: LandmarkReference | None = None
    best_preferred: LandmarkReference | None = None

    for lm in landmarks:
        offset = lm.distance_m - query_distance_m  # positive = landmark ahead
        abs_offset = abs(offset)
        if abs_offset > max_distance_m:
            continue

        ref = LandmarkReference(landmark=lm, offset_m=round(offset, 1))

        if (
            preferred_types
            and lm.landmark_type in preferred_types
            and (best_preferred is None or abs_offset < abs(best_preferred.offset_m))
        ):
            best_preferred = ref

        if best is None or abs_offset < abs(best.offset_m):
            best = ref

    # Prefer a preferred-type landmark if one exists in range
    if best_preferred is not None:
        return best_preferred
    return best


def find_landmarks_in_range(
    start_m: float,
    end_m: float,
    landmarks: list[Landmark],
) -> list[Landmark]:
    """Return all landmarks within a distance range, sorted by distance."""
    return sorted(
        [lm for lm in landmarks if start_m <= lm.distance_m <= end_m],
        key=lambda lm: lm.distance_m,
    )


def resolve_gps_at_distance(
    lap_df: pd.DataFrame,
    distance_m: float,
) -> tuple[float, float] | None:
    """Look up (lat, lon) at a track distance from a resampled DataFrame.

    Returns None if the DataFrame lacks lat/lon columns or the distance
    is out of range.
    """
    if "lat" not in lap_df.columns or "lon" not in lap_df.columns:
        return None

    dist = lap_df["lap_distance_m"].to_numpy()
    if distance_m < dist[0] or distance_m > dist[-1]:
        return None

    idx = int(np.searchsorted(dist, distance_m))
    idx = min(idx, len(dist) - 1)
    return float(lap_df["lat"].iloc[idx]), float(lap_df["lon"].iloc[idx])


def format_corner_landmarks(
    corner: Corner,
    landmarks: list[Landmark],
) -> str:
    """Format landmark references for a corner's key points.

    Returns a multi-line string with brake, apex, and throttle references
    suitable for injection into the coaching prompt.
    """
    lines: list[str] = []

    if corner.brake_point_m is not None:
        ref = find_nearest_landmark(
            corner.brake_point_m,
            landmarks,
            preferred_types=_BRAKE_PREFERRED_TYPES,
        )
        if ref is not None:
            lines.append(f"  Brake: {ref.format_reference()}")

    apex_ref = find_nearest_landmark(corner.apex_distance_m, landmarks)
    if apex_ref is not None:
        lines.append(f"  Apex: {apex_ref.format_reference()}")

    if corner.throttle_commit_m is not None:
        throttle_ref = find_nearest_landmark(corner.throttle_commit_m, landmarks)
        if throttle_ref is not None:
            lines.append(f"  Throttle: {throttle_ref.format_reference()}")

    return "\n".join(lines)
