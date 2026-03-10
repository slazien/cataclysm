"""Elevation fallback chain: USGS 3DEP -> Copernicus -> GPS."""

from __future__ import annotations

import logging

import numpy as np

from cataclysm.copernicus_elevation import fetch_copernicus_elevations
from cataclysm.elevation_service import ElevationResult, fetch_lidar_elevations

logger = logging.getLogger(__name__)


async def fetch_best_elevation(
    lats: np.ndarray,
    lons: np.ndarray,
    *,
    gps_altitudes: np.ndarray | None = None,
) -> ElevationResult:
    """Try each elevation source in priority order, return first success.

    Chain order:
      1. USGS 3DEP  (US only, ~0.1 m accuracy)
      2. Copernicus DEM  (global, ~4 m accuracy)
      3. GPS altitude  (device-reported, ~3 m accuracy)

    A source is considered *failed* if it raises an exception **or** returns
    ``source == "gps_fallback"`` (which both upstream functions use to signal
    an internal failure / insufficient data).
    """
    # 1. USGS 3DEP
    try:
        result = await fetch_lidar_elevations(lats, lons)
        if result.source != "gps_fallback" and len(result.altitude_m) > 0:
            logger.info("Elevation from USGS 3DEP (%d points)", len(result.altitude_m))
            return result
    except Exception:
        logger.warning("USGS 3DEP failed", exc_info=True)

    # 2. Copernicus DEM
    try:
        result = await fetch_copernicus_elevations(lats, lons)
        if result.source != "gps_fallback" and len(result.altitude_m) > 0:
            logger.info("Elevation from Copernicus DEM (%d points)", len(result.altitude_m))
            return result
    except Exception:
        logger.warning("Copernicus DEM failed", exc_info=True)

    # 3. GPS altitude fallback
    if gps_altitudes is not None and len(gps_altitudes) > 0:
        logger.info("Using GPS altitude fallback (%d points)", len(gps_altitudes))
        return ElevationResult(
            altitude_m=gps_altitudes,
            source="gps_fallback",
            accuracy_m=3.0,
        )

    # Nothing worked — return empty result
    return ElevationResult(
        altitude_m=np.array([], dtype=np.float64),
        source="gps_fallback",
        accuracy_m=3.0,
    )
