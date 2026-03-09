"""Copernicus DEM elevation fallback for international tracks.

Queries the Open-Elevation API (backed by Copernicus/SRTM data) to get
~4m-accuracy altitude for tracks outside the US where USGS 3DEP is unavailable.
"""

from __future__ import annotations

import logging

import httpx
import numpy as np

from cataclysm.elevation_service import ElevationResult

logger = logging.getLogger(__name__)

_OPEN_ELEVATION_URL = "https://api.open-elevation.com/api/v1/lookup"
_BATCH_SIZE = 100


async def _query_copernicus_batch(lats: list[float], lons: list[float]) -> list[float]:
    """Query the Open-Elevation API for a batch of coordinates.

    Max 100 points per request.
    """
    locations = [{"latitude": lat, "longitude": lon} for lat, lon in zip(lats, lons, strict=True)]
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            _OPEN_ELEVATION_URL,
            json={"locations": locations},
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
        return [r["elevation"] for r in data["results"]]


async def fetch_copernicus_elevations(lats: np.ndarray, lons: np.ndarray) -> ElevationResult:
    """Fetch elevations from the Open-Elevation (Copernicus/SRTM) API.

    Splits the input into batches of up to 100 points and concatenates results.
    On any failure, returns a GPS-fallback result.
    """
    n = len(lats)
    try:
        all_elevations: list[float] = []
        for start in range(0, n, _BATCH_SIZE):
            end = min(start + _BATCH_SIZE, n)
            batch_lats = lats[start:end].tolist()
            batch_lons = lons[start:end].tolist()
            batch_result = await _query_copernicus_batch(batch_lats, batch_lons)
            all_elevations.extend(batch_result)

        return ElevationResult(
            altitude_m=np.array(all_elevations, dtype=np.float64),
            source="copernicus_dem",
            accuracy_m=4.0,
        )
    except Exception:
        logger.warning(
            "Copernicus DEM elevation lookup failed, falling back to GPS",
            exc_info=True,
        )
        return ElevationResult(
            altitude_m=np.array([], dtype=np.float64),
            source="gps_fallback",
            accuracy_m=3.0,
        )
