"""Track database with official corner positions for known circuits.

Maps detected corners to official track corner numbers using GPS proximity
matching. For unknown tracks, corners keep their sequential numbering.
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
    name: str  # Optional corner name (e.g., "Charlotte's Web")
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
# GPS coordinates are approximate apex positions. The matching algorithm uses
# a generous radius so exact precision is not required.

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
# GPS distance helper
# ---------------------------------------------------------------------------
_EARTH_RADIUS_M = 6_371_000


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Approximate distance in meters between two GPS points."""
    lat1_r, lon1_r = np.radians(lat1), np.radians(lon1)
    lat2_r, lon2_r = np.radians(lat2), np.radians(lon2)
    dlat = lat2_r - lat1_r
    dlon = lon2_r - lon1_r
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1_r) * np.cos(lat2_r) * np.sin(dlon / 2) ** 2
    return float(2 * _EARTH_RADIUS_M * np.arcsin(np.sqrt(a)))


# ---------------------------------------------------------------------------
# Corner matching
# ---------------------------------------------------------------------------
MAX_MATCH_DISTANCE_M = 200  # Maximum distance to match a detected corner to an official one


def assign_official_numbers(
    corners: list[Corner],
    track_name: str,
    lap_df: pd.DataFrame,
) -> list[Corner]:
    """Re-number detected corners using official track corner numbers.

    For each detected corner, finds the nearest official corner by GPS
    proximity and assigns its official number. Detected corners that don't
    match any official corner keep a high number (100+) to sort last.

    For unknown tracks, returns the original corners unchanged.

    Parameters
    ----------
    corners:
        Detected corners with sequential numbering.
    track_name:
        Track name from session metadata.
    lap_df:
        Resampled lap DataFrame with lat, lon, lap_distance_m columns
        (used to look up GPS position of each corner apex).

    Returns
    -------
    New list of Corner objects with official numbers, sorted by number.
    """
    layout = lookup_track(track_name)
    if layout is None or not corners:
        return corners

    dist = lap_df["lap_distance_m"].to_numpy()
    lat = lap_df["lat"].to_numpy()
    lon = lap_df["lon"].to_numpy()

    # Build a list of (detected_corner_index, official_corner, distance)
    # for all possible pairings within MAX_MATCH_DISTANCE_M.
    candidates: list[tuple[int, OfficialCorner, float]] = []
    for ci, corner in enumerate(corners):
        apex_idx = int(np.searchsorted(dist, corner.apex_distance_m))
        apex_idx = min(apex_idx, len(lat) - 1)
        apex_lat = float(lat[apex_idx])
        apex_lon = float(lon[apex_idx])

        for official in layout.corners:
            d = _haversine_m(apex_lat, apex_lon, official.lat, official.lon)
            if d <= MAX_MATCH_DISTANCE_M:
                candidates.append((ci, official, d))

    # Greedy matching: assign closest pairs first, no double-assignment.
    candidates.sort(key=lambda c: c[2])
    used_detected: set[int] = set()
    used_official: set[int] = set()
    assignments: dict[int, int] = {}  # detected_index -> official_number

    for ci, official, _ in candidates:
        if ci in used_detected or official.number in used_official:
            continue
        assignments[ci] = official.number
        used_detected.add(ci)
        used_official.add(official.number)

    # Build new corner list with official numbers
    result: list[Corner] = []
    for ci, corner in enumerate(corners):
        official_num = assignments.get(ci, 100 + corner.number)
        result.append(
            Corner(
                number=official_num,
                entry_distance_m=corner.entry_distance_m,
                exit_distance_m=corner.exit_distance_m,
                apex_distance_m=corner.apex_distance_m,
                min_speed_mps=corner.min_speed_mps,
                brake_point_m=corner.brake_point_m,
                peak_brake_g=corner.peak_brake_g,
                throttle_commit_m=corner.throttle_commit_m,
                apex_type=corner.apex_type,
            )
        )

    result.sort(key=lambda c: c.entry_distance_m)
    return result
