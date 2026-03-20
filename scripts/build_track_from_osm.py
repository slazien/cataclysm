#!/usr/bin/env python3
"""Build a canonical track reference NPZ from OpenStreetMap geometry.

Fetches the track centerline from OSM via Overpass API, computes curvature
and heading, and saves the result as a .npz file compatible with
cataclysm/track_reference.py.

Usage:
    python scripts/build_track_from_osm.py --track vir
    python scripts/build_track_from_osm.py --track laguna-seca
    python scripts/build_track_from_osm.py --track road-atlanta
    python scripts/build_track_from_osm.py --all
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime

import numpy as np
import pandas as pd
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from cataclysm.curvature import compute_curvature
from cataclysm.track_reference import TrackReference, _save_reference

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Step size for resampling the track centerline (metres).
RESAMPLE_STEP_M = 0.7


@dataclass
class OSMTrackConfig:
    """Configuration for fetching a track from OSM."""

    slug: str
    display_name: str
    overpass_query: str
    expected_length_m: float
    reverse: bool = False  # Reverse node order if OSM maps against driving direction
    way_order: list[int] | None = None  # Explicit way ordering for multi-way tracks


# --- Track configurations ---

TRACKS: dict[str, OSMTrackConfig] = {
    "vir": OSMTrackConfig(
        slug="virginia-international-raceway",
        display_name="Virginia International Raceway",
        # Full Course: explicit way order traced from OSM connectivity.
        # Chain: Hog Pen → main → Horseshoe → NASCAR → Left Hook → Snake →
        #        (unnamed) → South Bend → (unnamed) → Oak Tree → (unnamed) →
        #        Roller Coaster → (unnamed) → back to Hog Pen.
        # Spiral + S/F straight link the start/finish area but belong to
        # the North/South course split — the Full Course goes around the outside.
        overpass_query=(
            "[out:json];"
            "("
            "way(1315957516);"  # Hog Pen (start)
            "way(20293988);"  # VIR main section
            "way(1315957517);"  # VIR connector
            "way(1315957518);"  # Horseshoe
            "way(1315957519);"  # VIR connector
            "way(1315957520);"  # NASCAR Bend
            "way(1315957521);"  # VIR connector
            "way(1315957522);"  # Left Hook
            "way(1315957523);"  # VIR connector
            "way(1315957524);"  # Snake
            "way(1315957525);"  # unnamed (Snake→South Bend)
            "way(1315957526);"  # South Bend
            "way(1315957527);"  # unnamed (South Bend→Oak Tree)
            "way(1315957528);"  # Oak Tree Curve
            "way(91012202);"  # unnamed (Oak Tree→Roller Coaster)
            "way(1315957529);"  # Roller Coaster
            "way(1315957530);"  # unnamed (Roller Coaster→Hog Pen)
            ");(._;>;);out body;"
        ),
        expected_length_m=5263.0,  # 3.27 mi
        reverse=False,
    ),
    "laguna-seca": OSMTrackConfig(
        slug="laguna-seca",
        display_name="WeatherTech Raceway Laguna Seca",
        overpass_query=(
            '[out:json];way["highway"="raceway"](36.57,-121.77,36.60,-121.74);(._;>;);out body;'
        ),
        expected_length_m=3602.0,  # 2.238 mi
        reverse=False,
    ),
    "road-atlanta": OSMTrackConfig(
        slug="road-atlanta",
        display_name="Michelin Raceway Road Atlanta",
        # Full course: main way + The Esses section + connector
        overpass_query=(
            "[out:json];"
            "("
            "way(9292566);"  # Road Atlanta Racetrack (main)
            "way(1360423184);"  # Road Atlanta Racetrack (section 2)
            "way(1360423185);"  # The Esses
            ");(._;>;);out body;"
        ),
        expected_length_m=4088.0,  # 2.54 mi
        reverse=True,  # OSM way has oneway=-1
    ),
    "vir-grand-west": OSMTrackConfig(
        slug="virginia-international-raceway-grand-west",
        display_name="Virginia International Raceway — Grand West",
        # Grand West = Full Course but replaces the direct Oak Tree→Roller
        # Coaster connector (91012202, 289m) with a longer detour through
        # the Patriot Course infield section (~1674m).
        # Route: ...Oak Tree → 1315957536 → Patriot(20299611) → 989707445
        #        → Roller Coaster → ...
        overpass_query=(
            "[out:json];"
            "("
            "way(1315957516);"  # Hog Pen (start)
            "way(20293988);"  # VIR main section
            "way(1315957517);"  # VIR connector
            "way(1315957518);"  # Horseshoe
            "way(1315957519);"  # VIR connector
            "way(1315957520);"  # NASCAR Bend
            "way(1315957521);"  # VIR connector
            "way(1315957522);"  # Left Hook
            "way(1315957523);"  # VIR connector
            "way(1315957524);"  # Snake
            "way(1315957525);"  # unnamed (Snake→South Bend)
            "way(1315957526);"  # South Bend
            "way(1315957527);"  # unnamed (South Bend→Oak Tree)
            "way(1315957528);"  # Oak Tree Curve
            # Grand West divergence: infield detour instead of 91012202
            "way(1315957536);"  # unnamed (Oak Tree→Patriot connector)
            "way(20299611);"  # Patriot Course (main infield loop)
            "way(989707445);"  # unnamed (Patriot→Roller Coaster area)
            "way(1315957529);"  # Roller Coaster
            "way(1315957530);"  # unnamed (Roller Coaster→Hog Pen)
            ");(._;>;);out body;"
        ),
        expected_length_m=6598.0,  # 4.1 mi
        reverse=False,
    ),
}


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance in metres between two GPS points."""
    earth_r = 6_371_000.0
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = (
        np.sin(dlat / 2) ** 2
        + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon / 2) ** 2
    )
    return earth_r * 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))


def fetch_osm_coordinates(config: OSMTrackConfig) -> tuple[np.ndarray, np.ndarray]:
    """Fetch lat/lon arrays from OSM via Overpass API.

    Returns (lats, lons) arrays in driving order.
    """
    print(f"  Fetching OSM data for {config.display_name}...")
    resp = requests.get(OVERPASS_URL, params={"data": config.overpass_query}, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    # Separate nodes and ways
    nodes: dict[int, tuple[float, float]] = {}
    ways: list[dict] = []

    for element in data["elements"]:
        if element["type"] == "node":
            nodes[element["id"]] = (element["lat"], element["lon"])
        elif element["type"] == "way":
            tags = element.get("tags", {})
            # Skip pit lanes and service roads
            if (
                "pit" in tags.get("name", "").lower()
                or "pit" in tags.get("description", "").lower()
            ):
                continue
            ways.append(element)

    if not ways:
        raise RuntimeError(f"No ways found for {config.display_name}")

    print(f"  Found {len(ways)} way(s) and {len(nodes)} nodes")

    # Order ways by connectivity (each way's last node connects to next way's first)
    ordered_node_ids = ways[0]["nodes"] if len(ways) == 1 else _stitch_ways(ways, nodes)

    # Extract lat/lon
    lats = []
    lons = []
    for nid in ordered_node_ids:
        if nid in nodes:
            lat, lon = nodes[nid]
            lats.append(lat)
            lons.append(lon)

    lats_arr = np.array(lats, dtype=np.float64)
    lons_arr = np.array(lons, dtype=np.float64)

    if config.reverse:
        lats_arr = lats_arr[::-1]
        lons_arr = lons_arr[::-1]

    return lats_arr, lons_arr


def _stitch_ways(ways: list[dict], nodes: dict[int, tuple[float, float]]) -> list[int]:
    """Stitch multiple OSM ways into a single ordered node sequence.

    Uses a greedy algorithm: start with any way, then find the next way
    whose first or last node matches the current endpoint.
    """
    remaining = list(range(len(ways)))
    # Start with the first way
    current_idx = remaining.pop(0)
    result = list(ways[current_idx]["nodes"])

    while remaining:
        tail = result[-1]
        head = result[0]
        found = False

        for i, idx in enumerate(remaining):
            w_nodes = ways[idx]["nodes"]
            if w_nodes[0] == tail:
                # Append forward
                result.extend(w_nodes[1:])
                remaining.pop(i)
                found = True
                break
            elif w_nodes[-1] == tail:
                # Append reversed
                result.extend(reversed(w_nodes[:-1]))
                remaining.pop(i)
                found = True
                break
            elif w_nodes[-1] == head:
                # Prepend forward
                result = list(w_nodes[:-1]) + result
                remaining.pop(i)
                found = True
                break
            elif w_nodes[0] == head:
                # Prepend reversed
                result = list(reversed(w_nodes[1:])) + result
                remaining.pop(i)
                found = True
                break

        if not found:
            # Try nearest-endpoint matching (for gaps in OSM data)
            print(f"  Warning: gap in OSM ways, {len(remaining)} ways remaining")
            # Just append the next way's nodes
            idx = remaining.pop(0)
            result.extend(ways[idx]["nodes"])

    return result


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
    step_m: float,
) -> pd.DataFrame:
    """Resample lat/lon to uniform distance spacing.

    Returns a DataFrame with lat, lon, lap_distance_m columns — compatible
    with compute_curvature().
    """
    dist = _compute_cumulative_distance(lats, lons)
    total_length = dist[-1]

    # Create uniform distance grid
    n_points = int(total_length / step_m)
    uniform_dist = np.linspace(0, total_length, n_points)

    # Interpolate lat/lon onto uniform grid
    lat_interp = np.interp(uniform_dist, dist, lats)
    lon_interp = np.interp(uniform_dist, dist, lons)

    return pd.DataFrame(
        {
            "lat": lat_interp,
            "lon": lon_interp,
            "lap_distance_m": uniform_dist,
        }
    )


def build_reference_from_osm(config: OSMTrackConfig) -> TrackReference:
    """Build a TrackReference from OSM geometry."""
    print(f"\nBuilding track reference: {config.display_name}")

    # 1. Fetch raw coordinates
    raw_lats, raw_lons = fetch_osm_coordinates(config)
    raw_dist = _compute_cumulative_distance(raw_lats, raw_lons)
    raw_length = raw_dist[-1]
    print(f"  Raw OSM length: {raw_length:.0f}m (expected: {config.expected_length_m:.0f}m)")

    length_ratio = abs(raw_length - config.expected_length_m) / config.expected_length_m
    if length_ratio > 0.15:
        print(f"  WARNING: length mismatch {length_ratio:.1%} — may need way filtering")

    # 2. Resample to uniform spacing
    df = _resample_track(raw_lats, raw_lons, RESAMPLE_STEP_M)
    print(f"  Resampled to {len(df)} points at {RESAMPLE_STEP_M}m spacing")

    # 3. Compute curvature
    curvature_result = compute_curvature(df, step_m=RESAMPLE_STEP_M, savgol_window=21)
    track_length = float(curvature_result.distance_m[-1])
    print(f"  Track length after smoothing: {track_length:.0f}m")

    # 4. Build TrackReference
    ref = TrackReference(
        track_slug=config.slug,
        curvature_result=curvature_result,
        elevation_m=None,  # OSM doesn't include elevation
        reference_lats=df["lat"].to_numpy(dtype=np.float64),
        reference_lons=df["lon"].to_numpy(dtype=np.float64),
        gps_quality_score=50.0,  # Lower than real session data (centerline, not racing line)
        built_from_session_id="osm-overpass",
        n_laps_averaged=0,
        track_length_m=track_length,
        updated_at=datetime.now(UTC).isoformat(),
    )

    # 5. Save
    _save_reference(ref)
    print(f"  Saved: data/track_reference/{config.slug}.npz")

    return ref


def main() -> None:
    parser = argparse.ArgumentParser(description="Build track reference from OSM")
    parser.add_argument(
        "--track",
        choices=list(TRACKS.keys()),
        help="Track to build",
    )
    parser.add_argument("--all", action="store_true", help="Build all tracks")
    args = parser.parse_args()

    if not args.track and not args.all:
        parser.error("Specify --track <name> or --all")

    tracks_to_build = list(TRACKS.keys()) if args.all else [args.track]

    import time

    for i, track_key in enumerate(tracks_to_build):
        if i > 0:
            # Rate-limit Overpass API requests
            print("\n  Waiting 10s for Overpass API rate limit...")
            time.sleep(10)
        config = TRACKS[track_key]
        try:
            ref = build_reference_from_osm(config)
            print(f"  ✓ {config.display_name}: {ref.track_length_m:.0f}m")
        except Exception as e:
            print(f"  ✗ {config.display_name}: {e}")
            raise


if __name__ == "__main__":
    main()
