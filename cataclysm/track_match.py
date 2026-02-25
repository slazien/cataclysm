"""GPS-based track auto-detection.

Matches a session's GPS centroid against the known track database to
automatically identify which circuit was driven — no reliance on the
RaceChrono metadata track name.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd

from cataclysm.track_db import TrackLayout, get_all_tracks, lookup_track

# Minimum GPS points required to compute a reliable centroid.
_MIN_GPS_POINTS = 50

# Earth radius in meters (mean, WGS-84).
_EARTH_RADIUS_M = 6_371_000.0


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in meters between two GPS coordinates."""
    rlat1, rlon1 = math.radians(lat1), math.radians(lon1)
    rlat2, rlon2 = math.radians(lat2), math.radians(lon2)
    dlat = rlat2 - rlat1
    dlon = rlon2 - rlon1
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    return _EARTH_RADIUS_M * 2 * math.asin(math.sqrt(a))


def compute_session_centroid(df: pd.DataFrame) -> tuple[float, float]:
    """Compute the mean lat/lon from a session DataFrame.

    Parameters
    ----------
    df:
        Must contain ``lat`` and ``lon`` columns with at least
        :data:`_MIN_GPS_POINTS` valid rows.

    Returns
    -------
    (mean_lat, mean_lon) tuple.

    Raises
    ------
    ValueError
        If fewer than :data:`_MIN_GPS_POINTS` valid GPS points exist.
    """
    lats = df["lat"].dropna()
    lons = df["lon"].dropna()
    n = min(len(lats), len(lons))
    if n < _MIN_GPS_POINTS:
        msg = f"Need at least {_MIN_GPS_POINTS} GPS points, got {n}"
        raise ValueError(msg)
    return float(lats.mean()), float(lons.mean())


@dataclass
class TrackMatch:
    """Result of GPS-based track matching."""

    layout: TrackLayout
    distance_m: float
    confidence: float  # 0.0–1.0, decreases with distance


def detect_track(
    df: pd.DataFrame,
    threshold_m: float = 5000.0,
) -> TrackMatch | None:
    """Match a session's GPS centroid against all known tracks.

    Returns the best match within *threshold_m*, or ``None`` if no track
    is close enough.
    """
    try:
        clat, clon = compute_session_centroid(df)
    except ValueError:
        return None

    best: TrackMatch | None = None
    for layout in get_all_tracks():
        if layout.center_lat is None or layout.center_lon is None:
            continue
        dist = haversine(clat, clon, layout.center_lat, layout.center_lon)
        if dist > threshold_m:
            continue
        # Confidence: 1.0 at 0m, decaying linearly to 0.0 at threshold_m
        confidence = max(0.0, 1.0 - dist / threshold_m)
        if best is None or dist < best.distance_m:
            best = TrackMatch(layout=layout, distance_m=dist, confidence=confidence)
    return best


def detect_track_or_lookup(
    df: pd.DataFrame,
    track_name: str,
    threshold_m: float = 5000.0,
) -> TrackLayout | None:
    """Primary integration function: GPS detection first, name fallback.

    Tries GPS-based detection via :func:`detect_track`.  If that fails
    (not enough GPS data, or no match within *threshold_m*), falls back
    to :func:`lookup_track` using the metadata track name.
    """
    match = detect_track(df, threshold_m)
    if match is not None:
        return match.layout
    return lookup_track(track_name)
