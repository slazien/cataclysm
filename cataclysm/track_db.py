"""Track database with official corner positions for known circuits.

For known tracks, corners are located by finding each official corner's
position along the lap using GPS proximity, then extracting KPIs at those
fixed positions. This bypasses heading-rate detection entirely, giving
exact official corner numbering with zero ambiguity.

For unknown tracks, heading-rate detection with sequential numbering is
used instead (see corners.py).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from cataclysm.corners import Corner


@dataclass(frozen=True)
class OfficialCorner:
    """An official corner definition for a known track."""

    number: int  # Official corner number (e.g., 1 for T1)
    name: str  # Corner name (e.g., "Charlotte's Web")
    lat: float  # Approximate apex latitude
    lon: float  # Approximate apex longitude


@dataclass(frozen=True)
class TrackLayout:
    """Official layout definition for a known track."""

    name: str
    corners: list[OfficialCorner]


# ---------------------------------------------------------------------------
# Known track layouts
# ---------------------------------------------------------------------------
# GPS coordinates are approximate apex positions.

BARBER_MOTORSPORTS_PARK = TrackLayout(
    name="Barber Motorsports Park",
    corners=[
        OfficialCorner(1, "Fast Downhill Left", 33.5315, -86.6165),
        OfficialCorner(2, "Uphill Right", 33.5323, -86.6152),
        OfficialCorner(3, "Uphill Crest", 33.5332, -86.6148),
        OfficialCorner(4, "Hilltop Right", 33.5340, -86.6152),
        OfficialCorner(5, "Charlotte's Web", 33.5348, -86.6163),
        OfficialCorner(6, "Downhill Left Kink", 33.5348, -86.6178),
        OfficialCorner(7, "Corkscrew Entry", 33.5343, -86.6188),
        OfficialCorner(8, "Corkscrew Mid", 33.5338, -86.6196),
        OfficialCorner(9, "Corkscrew Exit", 33.5335, -86.6203),
        OfficialCorner(10, "Downhill Right", 33.5340, -86.6213),
        OfficialCorner(11, "Back Straight S Left", 33.5346, -86.6223),
        OfficialCorner(12, "Back Straight S Right", 33.5344, -86.6233),
        OfficialCorner(13, "Rollercoaster Entry", 33.5338, -86.6243),
        OfficialCorner(14, "Rollercoaster Mid", 33.5328, -86.6250),
        OfficialCorner(15, "Blind Apex Right", 33.5318, -86.6243),
        OfficialCorner(16, "Final Left", 33.5312, -86.6228),
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
    """Locate official corners on a lap and build Corner skeletons.

    For each official corner, finds the nearest point in the lap's GPS data
    to determine its distance along the track. Entry/exit boundaries are set
    at the midpoints between adjacent corners.

    The returned Corner objects have placeholder KPI values — pass them to
    ``extract_corner_kpis_for_lap`` to fill in real KPIs.

    Parameters
    ----------
    lap_df:
        Resampled lap DataFrame with lat, lon, lap_distance_m columns.
    layout:
        Official track layout with corner GPS positions.

    Returns
    -------
    List of Corner skeletons sorted by distance, with official numbers.
    """
    dist = lap_df["lap_distance_m"].to_numpy()
    lat = lap_df["lat"].to_numpy()
    lon = lap_df["lon"].to_numpy()
    max_dist = float(dist[-1])

    # Find distance-along-track for each official corner
    apex_positions: list[tuple[int, float]] = []  # (number, apex_dist_m)
    for official in layout.corners:
        # Squared Euclidean in lat/lon — fine for finding nearest point
        gps_dists_sq = (lat - official.lat) ** 2 + (lon - official.lon) ** 2
        nearest_idx = int(np.argmin(gps_dists_sq))
        apex_positions.append((official.number, float(dist[nearest_idx])))

    apex_positions.sort(key=lambda x: x[1])

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
