"""Tests for the elevation fallback chain."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import numpy as np
import pytest

from cataclysm.elevation_chain import fetch_best_elevation
from cataclysm.elevation_service import ElevationResult


def _usgs_result(n: int = 5) -> ElevationResult:
    return ElevationResult(
        altitude_m=np.linspace(100.0, 110.0, n),
        source="usgs_3dep",
        accuracy_m=0.1,
    )


def _copernicus_result(n: int = 5) -> ElevationResult:
    return ElevationResult(
        altitude_m=np.linspace(200.0, 210.0, n),
        source="copernicus_dem",
        accuracy_m=4.0,
    )


def _gps_fallback_result() -> ElevationResult:
    """Simulates an upstream function returning its own GPS fallback."""
    return ElevationResult(
        altitude_m=np.array([], dtype=np.float64),
        source="gps_fallback",
        accuracy_m=3.0,
    )


@pytest.fixture()
def _coords() -> tuple[np.ndarray, np.ndarray]:
    lats = np.array([33.45, 33.46, 33.47, 33.48, 33.49])
    lons = np.array([-86.10, -86.11, -86.12, -86.13, -86.14])
    return lats, lons


# ------------------------------------------------------------------
# 1. USGS succeeds -> uses USGS
# ------------------------------------------------------------------
@pytest.mark.asyncio()
async def test_usgs_success(_coords: tuple[np.ndarray, np.ndarray]) -> None:
    lats, lons = _coords
    with (
        patch(
            "cataclysm.elevation_chain.fetch_lidar_elevations",
            new_callable=AsyncMock,
            return_value=_usgs_result(),
        ) as mock_usgs,
        patch(
            "cataclysm.elevation_chain.fetch_copernicus_elevations",
            new_callable=AsyncMock,
        ) as mock_cop,
    ):
        result = await fetch_best_elevation(lats, lons)

    assert result.source == "usgs_3dep"
    assert result.accuracy_m == 0.1
    assert len(result.altitude_m) == 5
    mock_usgs.assert_awaited_once()
    mock_cop.assert_not_awaited()


# ------------------------------------------------------------------
# 2. USGS fails (exception) -> Copernicus succeeds
# ------------------------------------------------------------------
@pytest.mark.asyncio()
async def test_usgs_exception_copernicus_success(
    _coords: tuple[np.ndarray, np.ndarray],
) -> None:
    lats, lons = _coords
    with (
        patch(
            "cataclysm.elevation_chain.fetch_lidar_elevations",
            new_callable=AsyncMock,
            side_effect=RuntimeError("USGS down"),
        ),
        patch(
            "cataclysm.elevation_chain.fetch_copernicus_elevations",
            new_callable=AsyncMock,
            return_value=_copernicus_result(),
        ),
    ):
        result = await fetch_best_elevation(lats, lons)

    assert result.source == "copernicus_dem"
    assert result.accuracy_m == 4.0
    assert len(result.altitude_m) == 5


# ------------------------------------------------------------------
# 3. Both fail, GPS altitudes provided -> GPS fallback
# ------------------------------------------------------------------
@pytest.mark.asyncio()
async def test_both_fail_gps_fallback(_coords: tuple[np.ndarray, np.ndarray]) -> None:
    lats, lons = _coords
    gps_alt = np.array([300.0, 301.0, 302.0, 303.0, 304.0])
    with (
        patch(
            "cataclysm.elevation_chain.fetch_lidar_elevations",
            new_callable=AsyncMock,
            side_effect=RuntimeError("USGS down"),
        ),
        patch(
            "cataclysm.elevation_chain.fetch_copernicus_elevations",
            new_callable=AsyncMock,
            side_effect=TimeoutError("Copernicus timeout"),
        ),
    ):
        result = await fetch_best_elevation(lats, lons, gps_altitudes=gps_alt)

    assert result.source == "gps_fallback"
    assert result.accuracy_m == 3.0
    np.testing.assert_array_equal(result.altitude_m, gps_alt)


# ------------------------------------------------------------------
# 4. All fail, no GPS altitudes -> empty result
# ------------------------------------------------------------------
@pytest.mark.asyncio()
async def test_all_fail_empty_result(_coords: tuple[np.ndarray, np.ndarray]) -> None:
    lats, lons = _coords
    with (
        patch(
            "cataclysm.elevation_chain.fetch_lidar_elevations",
            new_callable=AsyncMock,
            side_effect=RuntimeError("USGS down"),
        ),
        patch(
            "cataclysm.elevation_chain.fetch_copernicus_elevations",
            new_callable=AsyncMock,
            side_effect=TimeoutError("Copernicus timeout"),
        ),
    ):
        result = await fetch_best_elevation(lats, lons)

    assert result.source == "gps_fallback"
    assert result.accuracy_m == 3.0
    assert len(result.altitude_m) == 0


# ------------------------------------------------------------------
# 5. USGS returns gps_fallback source (soft fail) -> falls through to Copernicus
# ------------------------------------------------------------------
@pytest.mark.asyncio()
async def test_usgs_soft_fail_falls_through(
    _coords: tuple[np.ndarray, np.ndarray],
) -> None:
    lats, lons = _coords
    with (
        patch(
            "cataclysm.elevation_chain.fetch_lidar_elevations",
            new_callable=AsyncMock,
            return_value=_gps_fallback_result(),
        ),
        patch(
            "cataclysm.elevation_chain.fetch_copernicus_elevations",
            new_callable=AsyncMock,
            return_value=_copernicus_result(),
        ),
    ):
        result = await fetch_best_elevation(lats, lons)

    assert result.source == "copernicus_dem"
    assert result.accuracy_m == 4.0


# ------------------------------------------------------------------
# 6. Both return gps_fallback, GPS altitudes provided -> uses gps_altitudes kwarg
# ------------------------------------------------------------------
@pytest.mark.asyncio()
async def test_both_soft_fail_uses_gps_kwarg(
    _coords: tuple[np.ndarray, np.ndarray],
) -> None:
    lats, lons = _coords
    gps_alt = np.array([400.0, 401.0, 402.0, 403.0, 404.0])
    with (
        patch(
            "cataclysm.elevation_chain.fetch_lidar_elevations",
            new_callable=AsyncMock,
            return_value=_gps_fallback_result(),
        ),
        patch(
            "cataclysm.elevation_chain.fetch_copernicus_elevations",
            new_callable=AsyncMock,
            return_value=_gps_fallback_result(),
        ),
    ):
        result = await fetch_best_elevation(lats, lons, gps_altitudes=gps_alt)

    assert result.source == "gps_fallback"
    assert result.accuracy_m == 3.0
    np.testing.assert_array_equal(result.altitude_m, gps_alt)


# ------------------------------------------------------------------
# 7. Copernicus returns gps_fallback (soft fail), USGS also fails -> GPS kwarg
# ------------------------------------------------------------------
@pytest.mark.asyncio()
async def test_copernicus_soft_fail_gps_fallback(
    _coords: tuple[np.ndarray, np.ndarray],
) -> None:
    lats, lons = _coords
    gps_alt = np.array([500.0, 501.0, 502.0])
    with (
        patch(
            "cataclysm.elevation_chain.fetch_lidar_elevations",
            new_callable=AsyncMock,
            side_effect=RuntimeError("USGS down"),
        ),
        patch(
            "cataclysm.elevation_chain.fetch_copernicus_elevations",
            new_callable=AsyncMock,
            return_value=_gps_fallback_result(),
        ),
    ):
        result = await fetch_best_elevation(lats, lons, gps_altitudes=gps_alt)

    assert result.source == "gps_fallback"
    np.testing.assert_array_equal(result.altitude_m, gps_alt)


# ------------------------------------------------------------------
# 8. Empty gps_altitudes array treated as no GPS data
# ------------------------------------------------------------------
@pytest.mark.asyncio()
async def test_empty_gps_altitudes_treated_as_none(
    _coords: tuple[np.ndarray, np.ndarray],
) -> None:
    lats, lons = _coords
    with (
        patch(
            "cataclysm.elevation_chain.fetch_lidar_elevations",
            new_callable=AsyncMock,
            side_effect=RuntimeError("USGS down"),
        ),
        patch(
            "cataclysm.elevation_chain.fetch_copernicus_elevations",
            new_callable=AsyncMock,
            side_effect=RuntimeError("Copernicus down"),
        ),
    ):
        result = await fetch_best_elevation(
            lats, lons, gps_altitudes=np.array([], dtype=np.float64)
        )

    assert result.source == "gps_fallback"
    assert len(result.altitude_m) == 0
