"""USGS 3DEP LIDAR elevation service for high-accuracy track altitude.

Queries the USGS 3DEP Elevation Point Query Service to get LIDAR-grade
altitude (5-15cm accuracy) instead of relying on GPS altitude (~3m).
Results are cached per-track to avoid repeated API calls.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass
from pathlib import Path

import httpx
import numpy as np

logger = logging.getLogger(__name__)

_USGS_3DEP_URL = "https://epqs.nationalmap.gov/v1/json"
_CACHE_DIR = Path("data/elevation_cache")
_MAX_CONCURRENT = 20
_SUBSAMPLE_SPACING_M = 2.0


@dataclass
class ElevationResult:
    """Result of elevation lookup."""

    altitude_m: np.ndarray
    source: str  # "usgs_3dep" | "gps_fallback"
    accuracy_m: float


def _cache_key(lats: np.ndarray, lons: np.ndarray) -> str:
    """Generate cache key from the trace geometry itself.

    Bounding-box keys collide for different laps that share the same overall
    footprint and point count. Hash the rounded trace so cached altitude stays
    aligned to the specific driving line that produced it.
    """
    lat_trace = np.round(np.asarray(lats, dtype=np.float64), 6)
    lon_trace = np.round(np.asarray(lons, dtype=np.float64), 6)

    h = hashlib.blake2b(digest_size=16)
    h.update(np.asarray([len(lat_trace)], dtype=np.int32).tobytes())
    h.update(lat_trace.tobytes())
    h.update(lon_trace.tobytes())
    return h.hexdigest()


def _load_cache(key: str) -> np.ndarray | None:
    """Load cached elevation data if available."""
    path = _CACHE_DIR / f"{key}.json"
    if path.exists():
        data = json.loads(path.read_text())
        return np.array(data["elevations"], dtype=np.float64)
    return None


def _save_cache(key: str, elevations: np.ndarray) -> None:
    """Save elevation data to cache."""
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _CACHE_DIR / f"{key}.json"
    path.write_text(json.dumps({"elevations": elevations.tolist()}))


async def _query_single_point(
    client: httpx.AsyncClient,
    lat: float,
    lon: float,
    semaphore: asyncio.Semaphore,
) -> float | None:
    """Query USGS 3DEP for a single point."""
    async with semaphore:
        try:
            resp = await client.get(
                _USGS_3DEP_URL,
                params={
                    "x": f"{lon:.6f}",
                    "y": f"{lat:.6f}",
                    "wkid": 4326,
                    "units": "Meters",
                },
                timeout=10.0,
            )
            resp.raise_for_status()
            value = resp.json().get("value")
            if value is not None and value != -1_000_000:
                return float(value)
            return None
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            logger.debug("3DEP query failed for (%.6f, %.6f): %s", lat, lon, exc)
            return None


def _subsample_indices(
    lats: np.ndarray,
    lons: np.ndarray,
    spacing_m: float,
) -> np.ndarray:
    """Pick evenly-spaced indices along the GPS trace."""
    n = len(lats)
    if n <= 50:
        return np.arange(n)

    dlat = np.diff(lats)
    dlon = np.diff(lons)
    cos_lat = np.cos(np.radians(lats[:-1]))
    step_m = np.sqrt((dlat * 111_320) ** 2 + (dlon * 111_320 * cos_lat) ** 2)
    cum_dist = np.concatenate([[0], np.cumsum(step_m)])
    total_dist = cum_dist[-1]

    n_samples = max(10, int(total_dist / spacing_m))
    sample_dists = np.linspace(0, total_dist, n_samples)
    indices = np.searchsorted(cum_dist, sample_dists).clip(0, n - 1)
    return np.unique(indices)


async def fetch_lidar_elevations(
    lats: np.ndarray,
    lons: np.ndarray,
    *,
    subsample_spacing_m: float = _SUBSAMPLE_SPACING_M,
) -> ElevationResult:
    """Fetch LIDAR elevations for a GPS trace from USGS 3DEP.

    Subsamples the trace, queries the USGS API in parallel, interpolates
    back to full resolution, and caches the result.

    Returns ElevationResult with source="usgs_3dep" on success, or
    source="gps_fallback" with empty altitude_m if <80% of points resolve.
    """
    n = len(lats)
    cache_key = _cache_key(lats, lons)
    cached = _load_cache(cache_key)
    if cached is not None and len(cached) == n:
        return ElevationResult(altitude_m=cached, source="usgs_3dep", accuracy_m=0.1)

    sample_indices = _subsample_indices(lats, lons, subsample_spacing_m)
    sample_lats = lats[sample_indices]
    sample_lons = lons[sample_indices]

    semaphore = asyncio.Semaphore(_MAX_CONCURRENT)
    async with httpx.AsyncClient() as client:
        tasks = [
            _query_single_point(client, float(lat), float(lon), semaphore)
            for lat, lon in zip(sample_lats, sample_lons, strict=True)
        ]
        results = await asyncio.gather(*tasks)

    valid_count = sum(1 for r in results if r is not None)
    if valid_count < len(results) * 0.8:
        logger.warning(
            "LIDAR elevation: only %d/%d points valid, falling back to GPS",
            valid_count,
            len(results),
        )
        return ElevationResult(altitude_m=np.array([]), source="gps_fallback", accuracy_m=3.0)

    sample_elevations = np.array(
        [r if r is not None else np.nan for r in results], dtype=np.float64
    )
    # Fill NaN gaps via linear interpolation
    mask = np.isnan(sample_elevations)
    if mask.any() and not mask.all():
        xp = np.where(~mask)[0]
        fp = sample_elevations[~mask]
        sample_elevations = np.interp(np.arange(len(sample_elevations)), xp, fp)

    # Interpolate back to full resolution
    if len(sample_indices) < n:
        full_elevations = np.interp(
            np.arange(n),
            sample_indices.astype(np.float64),
            sample_elevations,
        )
    else:
        full_elevations = sample_elevations

    _save_cache(cache_key, full_elevations)
    return ElevationResult(altitude_m=full_elevations, source="usgs_3dep", accuracy_m=0.1)
