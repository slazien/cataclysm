"""Track database with official corner positions for known circuits.

For known tracks, corners are placed at fixed fractions of total lap distance
derived from track maps and telemetry analysis.  This bypasses heading-rate
detection entirely, giving exact official corner numbering with zero ambiguity.

For unknown tracks, heading-rate detection with sequential numbering is
used instead (see corners.py).
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from cataclysm.corners import Corner


@dataclass(frozen=True)
class OfficialCorner:
    """An official corner definition for a known track."""

    number: int  # Official corner number (e.g., 1 for T1)
    name: str  # Corner name (e.g., "Charlotte's Web")
    fraction: float  # Apex position as fraction of total lap distance (0.0–1.0)


@dataclass(frozen=True)
class TrackLayout:
    """Official layout definition for a known track."""

    name: str
    corners: list[OfficialCorner]


# ---------------------------------------------------------------------------
# Known track layouts
# ---------------------------------------------------------------------------
# Fractions are apex positions expressed as % of total lap distance, derived
# from speed-trace analysis of actual session data cross-referenced with the
# Porsche Track Experience corner-by-corner guide.
#
# Sources:
#   - Porsche Driving Experience Birmingham corner guide (T1–T16)
#   - Speed minimums from RaceChrono session data at Barber
#   - racetrackdriving.com track guide

BARBER_MOTORSPORTS_PARK = TrackLayout(
    name="Barber Motorsports Park",
    corners=[
        OfficialCorner(1, "Fast Downhill Left", 0.05),
        OfficialCorner(2, "Uphill Right", 0.10),
        OfficialCorner(3, "Uphill Crest", 0.15),
        OfficialCorner(4, "Hilltop Right", 0.20),
        OfficialCorner(5, "Charlotte's Web", 0.30),
        OfficialCorner(6, "Downhill Left Kink", 0.34),
        OfficialCorner(7, "Corkscrew Entry", 0.40),
        OfficialCorner(8, "Corkscrew Mid", 0.44),
        OfficialCorner(9, "Corkscrew Exit", 0.49),
        OfficialCorner(10, "Esses Left", 0.58),
        OfficialCorner(11, "Esses Right", 0.62),
        OfficialCorner(12, "Rollercoaster Entry", 0.73),
        OfficialCorner(13, "Rollercoaster Mid", 0.76),
        OfficialCorner(14, "Rollercoaster Exit", 0.81),
        OfficialCorner(15, "Blind Apex Right", 0.87),
        OfficialCorner(16, "Final Left", 0.90),
    ],
)

# Registry of known tracks — keys are normalized (lowercased, stripped).
_TRACK_REGISTRY: dict[str, TrackLayout] = {
    "barber motorsports park": BARBER_MOTORSPORTS_PARK,
}


def _normalize_name(name: str) -> str:
    """Normalize a track name for lookup."""
    return name.strip().lower()


def lookup_track(track_name: str) -> TrackLayout | None:
    """Look up a known track layout by name.

    Returns None if the track is not in the database.
    """
    return _TRACK_REGISTRY.get(_normalize_name(track_name))


# ---------------------------------------------------------------------------
# Default corner zone margin
# ---------------------------------------------------------------------------
_ZONE_MARGIN_M = 50.0  # entry/exit margin for first/last corners


def locate_official_corners(
    lap_df: pd.DataFrame,
    layout: TrackLayout,
) -> list[Corner]:
    """Build Corner skeletons at official positions along a lap.

    Each official corner's apex is placed at ``fraction * lap_distance``.
    Entry/exit boundaries are midpoints between adjacent corners.

    The returned Corner objects have placeholder KPI values — pass them to
    ``extract_corner_kpis_for_lap`` to fill in real KPIs.

    Parameters
    ----------
    lap_df:
        Resampled lap DataFrame with a lap_distance_m column.
    layout:
        Official track layout with corner fractions.

    Returns
    -------
    List of Corner skeletons sorted by distance, with official numbers.
    """
    max_dist = float(lap_df["lap_distance_m"].iloc[-1])

    # Compute apex distances from fractions, sorted by position on track
    apex_positions: list[tuple[int, float]] = [
        (c.number, c.fraction * max_dist)
        for c in sorted(layout.corners, key=lambda c: c.fraction)
    ]

    # Build skeleton corners with entry/exit at midpoints
    skeletons: list[Corner] = []
    for i, (number, apex_m) in enumerate(apex_positions):
        if i == 0:
            entry_m = max(0.0, apex_m - _ZONE_MARGIN_M)
        else:
            entry_m = (apex_positions[i - 1][1] + apex_m) / 2

        if i == len(apex_positions) - 1:
            exit_m = min(max_dist, apex_m + _ZONE_MARGIN_M)
        else:
            exit_m = (apex_m + apex_positions[i + 1][1]) / 2

        skeletons.append(
            Corner(
                number=number,
                entry_distance_m=round(entry_m, 1),
                exit_distance_m=round(exit_m, 1),
                apex_distance_m=round(apex_m, 1),
                min_speed_mps=0.0,
                brake_point_m=None,
                peak_brake_g=None,
                throttle_commit_m=None,
                apex_type="mid",
            )
        )

    return skeletons
