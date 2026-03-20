#!/usr/bin/env python3
"""Build a canonical track reference NPZ from a GPX file.

Parses GPX trackpoints (lat/lon/ele), computes curvature and heading,
and saves the result as a .npz file compatible with cataclysm/track_reference.py.

Usage:
    python scripts/build_track_from_gpx.py \
        --gpx /tmp/vir-full.gpx \
        --slug virginia-international-raceway \
        --name "Virginia International Raceway" \
        --expected-length 5263

    python scripts/build_track_from_gpx.py \
        --gpx /tmp/vir-grand/.map.gpx \
        --slug virginia-international-raceway-grand-west \
        --name "VIR Grand West" \
        --expected-length 6598 \
        --gpx-ns "http://www.topografix.com/GPX/1/0"
"""

from __future__ import annotations

import argparse
import os
import sys
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from math import atan2, cos, radians, sin, sqrt
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from cataclysm.curvature import compute_curvature
from cataclysm.track_reference import TrackReference, _save_reference

RESAMPLE_STEP_M = 0.7


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance between two GPS points in metres."""
    R = 6_371_000.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))


def parse_gpx(
    gpx_path: str | Path,
    namespace: str = "http://www.topografix.com/GPX/1/1",
) -> tuple[np.ndarray, np.ndarray, np.ndarray | None]:
    """Parse a GPX file and return (lats, lons, elevations_or_None)."""
    tree = ET.parse(gpx_path)
    ns = {"gpx": namespace}

    points = tree.findall(".//gpx:trkpt", ns)
    if not points:
        raise ValueError(f"No trackpoints found in {gpx_path} with namespace {namespace}")

    lats: list[float] = []
    lons: list[float] = []
    eles: list[float] = []

    for pt in points:
        lats.append(float(pt.get("lat")))  # type: ignore[arg-type]
        lons.append(float(pt.get("lon")))  # type: ignore[arg-type]
        ele = pt.find("gpx:ele", ns)
        if ele is not None and ele.text:
            eles.append(float(ele.text))

    lats_arr = np.array(lats, dtype=np.float64)
    lons_arr = np.array(lons, dtype=np.float64)
    eles_arr = np.array(eles, dtype=np.float64) if len(eles) == len(lats) else None

    return lats_arr, lons_arr, eles_arr


def _compute_cumulative_distance(lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
    """Compute cumulative distance along lat/lon arrays."""
    distances = [0.0]
    for i in range(1, len(lats)):
        d = _haversine_m(lats[i - 1], lons[i - 1], lats[i], lons[i])
        distances.append(distances[-1] + d)
    return np.array(distances, dtype=np.float64)


def _resample_track(
    lats: np.ndarray,
    lons: np.ndarray,
    eles: np.ndarray | None,
    step_m: float,
) -> tuple[pd.DataFrame, np.ndarray | None]:
    """Resample lat/lon/ele to uniform distance spacing."""
    dist = _compute_cumulative_distance(lats, lons)
    total_length = dist[-1]

    n_points = int(total_length / step_m)
    uniform_dist = np.linspace(0, total_length, n_points)

    lat_interp = np.interp(uniform_dist, dist, lats)
    lon_interp = np.interp(uniform_dist, dist, lons)

    df = pd.DataFrame(
        {
            "lat": lat_interp,
            "lon": lon_interp,
            "lap_distance_m": uniform_dist,
        }
    )

    ele_interp = None
    if eles is not None:
        ele_interp = np.interp(uniform_dist, dist, eles)

    return df, ele_interp


def build_reference_from_gpx(
    gpx_path: str | Path,
    slug: str,
    display_name: str,
    expected_length_m: float,
    gpx_namespace: str = "http://www.topografix.com/GPX/1/1",
    quality_score: float = 70.0,
) -> TrackReference:
    """Build a TrackReference from a GPX file."""
    print(f"\nBuilding track reference: {display_name}")

    # 1. Parse GPX
    raw_lats, raw_lons, raw_eles = parse_gpx(gpx_path, namespace=gpx_namespace)
    raw_dist = _compute_cumulative_distance(raw_lats, raw_lons)
    raw_length = raw_dist[-1]
    print(f"  GPX raw length: {raw_length:.0f}m (expected: {expected_length_m:.0f}m)")
    print(f"  GPX points: {len(raw_lats)}")
    if raw_eles is not None:
        print(f"  Elevation: {raw_eles.min():.1f}m – {raw_eles.max():.1f}m (delta={raw_eles.max() - raw_eles.min():.1f}m)")
    else:
        print("  Elevation: not available in GPX")

    length_ratio = abs(raw_length - expected_length_m) / expected_length_m
    if length_ratio > 0.10:
        print(f"  WARNING: length mismatch {length_ratio:.1%}")

    # Close the loop if gap < 50m
    gap = _haversine_m(raw_lats[0], raw_lons[0], raw_lats[-1], raw_lons[-1])
    print(f"  Start-end gap: {gap:.1f}m")
    if gap < 50:
        # Append first point to close loop
        raw_lats = np.append(raw_lats, raw_lats[0])
        raw_lons = np.append(raw_lons, raw_lons[0])
        if raw_eles is not None:
            raw_eles = np.append(raw_eles, raw_eles[0])

    # 2. Resample to uniform spacing
    df, ele_interp = _resample_track(raw_lats, raw_lons, raw_eles, RESAMPLE_STEP_M)
    print(f"  Resampled to {len(df)} points at {RESAMPLE_STEP_M}m spacing")

    # 3. Compute curvature
    curvature_result = compute_curvature(df, step_m=RESAMPLE_STEP_M, savgol_window=21)
    track_length = float(curvature_result.distance_m[-1])
    print(f"  Track length after smoothing: {track_length:.0f}m ({track_length / 1609.34:.2f} mi)")

    # 4. Build TrackReference
    source_label = f"gpx-{Path(gpx_path).stem}"
    ref = TrackReference(
        track_slug=slug,
        curvature_result=curvature_result,
        elevation_m=ele_interp,
        banking_deg=None,
        reference_lats=df["lat"].to_numpy(dtype=np.float64),
        reference_lons=df["lon"].to_numpy(dtype=np.float64),
        gps_quality_score=quality_score,
        built_from_session_id=source_label,
        n_laps_averaged=1,
        track_length_m=track_length,
        updated_at=datetime.now(UTC).isoformat(),
    )

    # 5. Save
    _save_reference(ref)
    print(f"  Saved: data/track_reference/{slug}.npz")

    return ref


def main() -> None:
    parser = argparse.ArgumentParser(description="Build track reference from GPX file")
    parser.add_argument("--gpx", required=True, help="Path to GPX file")
    parser.add_argument("--slug", required=True, help="Track slug (NPZ filename stem)")
    parser.add_argument("--name", required=True, help="Display name")
    parser.add_argument("--expected-length", type=float, required=True, help="Expected track length in meters")
    parser.add_argument("--gpx-ns", default="http://www.topografix.com/GPX/1/1", help="GPX XML namespace")
    parser.add_argument("--quality", type=float, default=70.0, help="GPS quality score (0-100)")
    args = parser.parse_args()

    build_reference_from_gpx(
        gpx_path=args.gpx,
        slug=args.slug,
        display_name=args.name,
        expected_length_m=args.expected_length,
        gpx_namespace=args.gpx_ns,
        quality_score=args.quality,
    )


if __name__ == "__main__":
    main()
