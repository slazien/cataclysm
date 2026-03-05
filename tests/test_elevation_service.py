"""Tests for USGS 3DEP LIDAR elevation service."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import numpy as np
import pytest

from cataclysm.elevation_service import (
    ElevationResult,
    _cache_key,
    _save_cache,
    _subsample_indices,
    fetch_lidar_elevations,
)


class TestElevationResult:
    def test_dataclass_fields(self) -> None:
        result = ElevationResult(
            altitude_m=np.array([100.0, 101.0]),
            source="usgs_3dep",
            accuracy_m=0.1,
        )
        assert result.source == "usgs_3dep"
        assert result.accuracy_m == 0.1
        assert len(result.altitude_m) == 2

    def test_gps_fallback(self) -> None:
        result = ElevationResult(
            altitude_m=np.array([]),
            source="gps_fallback",
            accuracy_m=3.0,
        )
        assert result.source == "gps_fallback"
        assert len(result.altitude_m) == 0


class TestCacheKey:
    def test_deterministic(self) -> None:
        lats = np.array([33.0, 34.0])
        lons = np.array([-86.0, -87.0])
        assert _cache_key(lats, lons) == _cache_key(lats, lons)

    def test_different_inputs(self) -> None:
        lats1 = np.array([33.0, 34.0])
        lons1 = np.array([-86.0, -87.0])
        lats2 = np.array([33.0, 34.5])
        lons2 = np.array([-86.0, -87.0])
        assert _cache_key(lats1, lons1) != _cache_key(lats2, lons2)


class TestSubsampleIndices:
    def test_small_arrays_return_all(self) -> None:
        lats = np.array([33.0, 33.001, 33.002])
        lons = np.array([-86.0, -86.001, -86.002])
        indices = _subsample_indices(lats, lons, 2.0)
        np.testing.assert_array_equal(indices, np.arange(3))

    def test_large_array_subsamples(self) -> None:
        # ~1km trace, spacing=2m -> should get ~500 samples, not 1000
        n = 1000
        lats = np.linspace(33.0, 33.009, n)  # ~1km
        lons = np.full(n, -86.0)
        indices = _subsample_indices(lats, lons, 2.0)
        assert len(indices) < n
        assert len(indices) >= 10
        assert indices[0] == 0
        assert indices[-1] == n - 1

    def test_includes_endpoints(self) -> None:
        n = 200
        lats = np.linspace(33.0, 33.005, n)
        lons = np.linspace(-86.0, -86.005, n)
        indices = _subsample_indices(lats, lons, 5.0)
        assert indices[0] == 0
        assert indices[-1] == n - 1

    def test_unique_indices(self) -> None:
        n = 500
        lats = np.linspace(33.0, 33.002, n)
        lons = np.full(n, -86.0)
        indices = _subsample_indices(lats, lons, 2.0)
        # np.unique already guarantees uniqueness, but verify
        assert len(indices) == len(np.unique(indices))


class TestFetchLidarElevations:
    async def test_returns_cached_result(self, tmp_path: object) -> None:
        lats = np.array([33.536, 33.537, 33.538])
        lons = np.array([-86.621, -86.622, -86.623])

        # Pre-populate cache
        with patch("cataclysm.elevation_service._CACHE_DIR", tmp_path):
            key = _cache_key(lats, lons)
            _save_cache(key, np.array([195.3, 196.1, 194.8]))

            result = await fetch_lidar_elevations(lats, lons)

        assert result.source == "usgs_3dep"
        assert len(result.altitude_m) == 3
        assert result.altitude_m[0] == pytest.approx(195.3)

    async def test_fallback_on_low_success_rate(self) -> None:
        lats = np.array([33.536, 33.537, 33.538])
        lons = np.array([-86.621, -86.622, -86.623])

        with (
            patch("cataclysm.elevation_service._load_cache", return_value=None),
            patch(
                "cataclysm.elevation_service._query_single_point",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            result = await fetch_lidar_elevations(lats, lons)

        assert result.source == "gps_fallback"
        assert len(result.altitude_m) == 0

    async def test_successful_fetch_with_interpolation(self) -> None:
        """Test that valid API responses get interpolated to full resolution."""
        lats = np.array([33.536, 33.537, 33.538, 33.539, 33.540])
        lons = np.array([-86.621, -86.622, -86.623, -86.624, -86.625])

        # Mock cache miss and successful API responses
        mock_responses = [195.0, 196.0, 197.0, 198.0, 199.0]

        async def mock_query(client: object, lat: float, lon: float, sem: object) -> float | None:
            idx = int(round((lat - 33.536) / 0.001))
            if 0 <= idx < len(mock_responses):
                return mock_responses[idx]
            return None

        with (
            patch("cataclysm.elevation_service._load_cache", return_value=None),
            patch("cataclysm.elevation_service._save_cache"),
            patch(
                "cataclysm.elevation_service._query_single_point",
                side_effect=mock_query,
            ),
        ):
            result = await fetch_lidar_elevations(lats, lons)

        assert result.source == "usgs_3dep"
        assert len(result.altitude_m) == 5
        assert result.accuracy_m == 0.1

    async def test_partial_failures_interpolated(self) -> None:
        """When >80% succeed, NaN gaps should be interpolated."""
        # Use a small array (<=50) so all indices are queried
        lats = np.array([33.536, 33.537, 33.538, 33.539, 33.540])
        lons = np.array([-86.621, -86.622, -86.623, -86.624, -86.625])

        # 4/5 succeed (80%), one returns None
        responses = [195.0, None, 197.0, 198.0, 199.0]
        call_idx = 0

        async def mock_query(client: object, lat: float, lon: float, sem: object) -> float | None:
            nonlocal call_idx
            val = responses[call_idx]
            call_idx += 1
            return val

        with (
            patch("cataclysm.elevation_service._load_cache", return_value=None),
            patch("cataclysm.elevation_service._save_cache"),
            patch(
                "cataclysm.elevation_service._query_single_point",
                side_effect=mock_query,
            ),
        ):
            result = await fetch_lidar_elevations(lats, lons)

        assert result.source == "usgs_3dep"
        assert len(result.altitude_m) == 5
        # The NaN at index 1 should be interpolated between 195.0 and 197.0
        assert result.altitude_m[1] == pytest.approx(196.0)

    async def test_cache_size_mismatch_refetches(self, tmp_path: object) -> None:
        """If cache has wrong size, it should re-fetch."""
        lats = np.array([33.536, 33.537, 33.538])
        lons = np.array([-86.621, -86.622, -86.623])

        # Cache with wrong length
        with patch("cataclysm.elevation_service._CACHE_DIR", tmp_path):
            key = _cache_key(lats, lons)
            _save_cache(key, np.array([195.3, 196.1]))  # 2 points, need 3

            # Mock API to return all-None so we get fallback
            with patch(
                "cataclysm.elevation_service._query_single_point",
                new_callable=AsyncMock,
                return_value=None,
            ):
                result = await fetch_lidar_elevations(lats, lons)

        # Should fall back since cache didn't match and API "failed"
        assert result.source == "gps_fallback"
