"""Tests for Copernicus DEM elevation fallback."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import numpy as np
import pytest

from cataclysm.copernicus_elevation import fetch_copernicus_elevations
from cataclysm.elevation_service import ElevationResult


class TestCopernicusElevation:
    @pytest.mark.asyncio
    async def test_returns_elevation_result(self) -> None:
        lats = np.array([33.530, 33.531, 33.530])
        lons = np.array([-86.622, -86.621, -86.620])
        mock_elevations = [150.0, 152.0, 149.0]
        with patch(
            "cataclysm.copernicus_elevation._query_copernicus_batch",
            new_callable=AsyncMock,
        ) as mock_query:
            mock_query.return_value = mock_elevations
            result = await fetch_copernicus_elevations(lats, lons)
            assert isinstance(result, ElevationResult)
            assert result.source == "copernicus_dem"
            assert result.accuracy_m == pytest.approx(4.0)
            assert len(result.altitude_m) == 3

    @pytest.mark.asyncio
    async def test_fallback_on_failure(self) -> None:
        lats = np.array([33.530, 33.531])
        lons = np.array([-86.622, -86.621])
        with patch(
            "cataclysm.copernicus_elevation._query_copernicus_batch",
            new_callable=AsyncMock,
            side_effect=Exception("API down"),
        ):
            result = await fetch_copernicus_elevations(lats, lons)
            assert result.source == "gps_fallback"

    @pytest.mark.asyncio
    async def test_batches_large_requests(self) -> None:
        lats = np.linspace(33.0, 34.0, 250)
        lons = np.linspace(-87.0, -86.0, 250)
        with patch(
            "cataclysm.copernicus_elevation._query_copernicus_batch",
            new_callable=AsyncMock,
        ) as mock_query:
            # Return incrementing values for each batch
            mock_query.side_effect = lambda la, lo: list(range(len(la)))
            result = await fetch_copernicus_elevations(lats, lons)
            assert len(result.altitude_m) == 250
            assert mock_query.call_count >= 3  # 250 / 100 = 3 batches
