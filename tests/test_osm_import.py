"""Tests for OSM Overpass API centerline import."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from cataclysm.osm_import import (
    OverpassResult,
    extract_centerline,
    osm_to_track_seed,
    query_overpass_raceway,
)


class TestQueryOverpass:
    @pytest.mark.asyncio
    async def test_query_returns_results(self) -> None:
        mock_response = {
            "elements": [
                {
                    "type": "way",
                    "id": 12345,
                    "tags": {"name": "Barber Motorsports Park", "highway": "raceway"},
                    "geometry": [
                        {"lat": 33.530, "lon": -86.622},
                        {"lat": 33.531, "lon": -86.621},
                        {"lat": 33.530, "lon": -86.620},
                    ],
                }
            ]
        }
        with patch("cataclysm.osm_import._fetch_overpass", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_response
            results = await query_overpass_raceway(33.53, -86.62, radius_m=5000)
            assert len(results) == 1
            assert results[0].name == "Barber Motorsports Park"

    @pytest.mark.asyncio
    async def test_query_no_results(self) -> None:
        with patch("cataclysm.osm_import._fetch_overpass", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = {"elements": []}
            results = await query_overpass_raceway(0.0, 0.0, radius_m=1000)
            assert len(results) == 0

    @pytest.mark.asyncio
    async def test_handles_missing_name(self) -> None:
        mock_response = {
            "elements": [
                {
                    "type": "way",
                    "id": 99,
                    "tags": {"highway": "raceway"},
                    "geometry": [
                        {"lat": 33.530, "lon": -86.622},
                        {"lat": 33.531, "lon": -86.621},
                    ],
                }
            ]
        }
        with patch("cataclysm.osm_import._fetch_overpass", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_response
            results = await query_overpass_raceway(33.53, -86.62)
            assert len(results) == 1
            assert "99" in results[0].name


class TestExtractCenterline:
    def test_extracts_lat_lon_arrays(self) -> None:
        geom = [
            {"lat": 33.530, "lon": -86.622},
            {"lat": 33.531, "lon": -86.621},
            {"lat": 33.530, "lon": -86.620},
        ]
        result = extract_centerline(geom)
        assert len(result.lats) == 3
        assert result.lats[0] == pytest.approx(33.530)

    def test_computes_length(self) -> None:
        geom = [
            {"lat": 33.530, "lon": -86.622},
            {"lat": 33.531, "lon": -86.621},
            {"lat": 33.530, "lon": -86.620},
        ]
        result = extract_centerline(geom)
        assert result.length_m > 0


class TestOsmToTrackSeed:
    def test_creates_seed_dict(self) -> None:
        result = OverpassResult(
            osm_id=12345,
            name="Test Raceway",
            lats=[33.53, 33.531, 33.53],
            lons=[-86.622, -86.621, -86.620],
            length_m=3500.0,
        )
        seed = osm_to_track_seed(result)
        assert seed["slug"] == "test-raceway"
        assert seed["name"] == "Test Raceway"
        assert seed["source"] == "osm"
        assert seed["center_lat"] == pytest.approx(33.5303, abs=0.01)
