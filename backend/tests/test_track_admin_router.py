"""Tests for the track admin REST API."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from cataclysm.osm_import import OverpassResult
from httpx import AsyncClient


class TestListTracks:
    @pytest.mark.asyncio
    async def test_list_empty(self, client: AsyncClient) -> None:
        resp = await client.get("/api/track-admin/")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestGetTrack:
    @pytest.mark.asyncio
    async def test_not_found(self, client: AsyncClient) -> None:
        resp = await client.get("/api/track-admin/nonexistent")
        assert resp.status_code == 404


class TestCreateTrack:
    @pytest.mark.asyncio
    async def test_create_minimal(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/track-admin/",
            json={
                "slug": "test-track",
                "name": "Test Track",
                "source": "manual",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["slug"] == "test-track"

    @pytest.mark.asyncio
    async def test_duplicate_slug_409(self, client: AsyncClient) -> None:
        await client.post(
            "/api/track-admin/",
            json={
                "slug": "dup-test",
                "name": "Dup",
                "source": "manual",
            },
        )
        resp = await client.post(
            "/api/track-admin/",
            json={
                "slug": "dup-test",
                "name": "Dup 2",
                "source": "manual",
            },
        )
        assert resp.status_code == 409


class TestUpdateTrack:
    @pytest.mark.asyncio
    async def test_update_quality_tier(self, client: AsyncClient) -> None:
        await client.post(
            "/api/track-admin/",
            json={
                "slug": "upd-test",
                "name": "Upd",
                "source": "manual",
            },
        )
        resp = await client.patch(
            "/api/track-admin/upd-test",
            json={
                "quality_tier": 3,
                "status": "published",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["quality_tier"] == 3

    @pytest.mark.asyncio
    async def test_update_not_found(self, client: AsyncClient) -> None:
        resp = await client.patch(
            "/api/track-admin/no-such-track",
            json={"quality_tier": 2},
        )
        assert resp.status_code == 404


class TestTrackCorners:
    @pytest.mark.asyncio
    async def test_set_and_get_corners(self, client: AsyncClient) -> None:
        await client.post(
            "/api/track-admin/",
            json={
                "slug": "corners-api",
                "name": "Corners",
                "source": "manual",
            },
        )
        corners = [
            {"number": 1, "name": "T1", "fraction": 0.05, "direction": "left"},
            {"number": 2, "name": "T2", "fraction": 0.20, "direction": "right"},
        ]
        resp = await client.put("/api/track-admin/corners-api/corners", json=corners)
        assert resp.status_code == 200
        resp = await client.get("/api/track-admin/corners-api/corners")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    @pytest.mark.asyncio
    async def test_corners_not_found(self, client: AsyncClient) -> None:
        resp = await client.get("/api/track-admin/no-such/corners")
        assert resp.status_code == 404


class TestTrackLandmarks:
    @pytest.mark.asyncio
    async def test_set_and_get_landmarks(self, client: AsyncClient) -> None:
        await client.post(
            "/api/track-admin/",
            json={
                "slug": "lm-api",
                "name": "LM",
                "source": "manual",
            },
        )
        landmarks = [
            {
                "name": "S/F gantry",
                "distance_m": 0.0,
                "landmark_type": "structure",
                "source": "manual",
            },
        ]
        resp = await client.put("/api/track-admin/lm-api/landmarks", json=landmarks)
        assert resp.status_code == 200
        resp = await client.get("/api/track-admin/lm-api/landmarks")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    @pytest.mark.asyncio
    async def test_landmarks_not_found(self, client: AsyncClient) -> None:
        resp = await client.get("/api/track-admin/no-such/landmarks")
        assert resp.status_code == 404


class TestTrackValidation:
    @pytest.mark.asyncio
    async def test_validate_good_track(self, client: AsyncClient) -> None:
        """Track with valid corners returns is_valid=True."""
        await client.post(
            "/api/track-admin/",
            json={
                "slug": "valid-track",
                "name": "Valid Track",
                "source": "manual",
                "length_m": 3200.0,
            },
        )
        corners = [
            {"number": 1, "name": "T1", "fraction": 0.10, "direction": "left"},
            {"number": 2, "name": "T2", "fraction": 0.30, "direction": "right"},
            {"number": 3, "name": "T3", "fraction": 0.55, "direction": "left"},
            {"number": 4, "name": "T4", "fraction": 0.80, "direction": "right"},
        ]
        await client.put("/api/track-admin/valid-track/corners", json=corners)

        resp = await client.post("/api/track-admin/valid-track/validate")
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_valid"] is True
        assert isinstance(data["issues"], list)
        assert data["quality_score"] > 0.0

    @pytest.mark.asyncio
    async def test_validate_track_not_found(self, client: AsyncClient) -> None:
        """Non-existent slug returns 404."""
        resp = await client.post("/api/track-admin/nonexistent/validate")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_validate_track_no_corners(self, client: AsyncClient) -> None:
        """Track with no corners returns is_valid=False with zero-corners error."""
        await client.post(
            "/api/track-admin/",
            json={
                "slug": "empty-track",
                "name": "Empty Track",
                "source": "manual",
            },
        )
        resp = await client.post("/api/track-admin/empty-track/validate")
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_valid"] is False
        assert any("zero corners" in i["message"].lower() for i in data["issues"])
        assert data["quality_score"] == 0.0


# ---------------------------------------------------------------------------
# OSM Import
# ---------------------------------------------------------------------------


def _mock_osm_result() -> OverpassResult:
    """Create a synthetic OSM result with a small circular track."""
    import numpy as np

    n = 50
    t = np.linspace(0, 2 * np.pi, n, endpoint=False)
    lats = (33.53 + 0.002 * np.sin(t)).tolist()
    lons = (-86.62 + 0.003 * np.cos(t)).tolist()
    return OverpassResult(
        osm_id=12345,
        name="Test Raceway",
        lats=lats,
        lons=lons,
        length_m=2500.0,
    )


_ENRICH_RESULT = {
    "corners_detected": 4,
    "elevation_source": "copernicus",
    "brake_markers": 4,
    "steps_logged": 4,
}


class TestOsmImport:
    @pytest.mark.asyncio
    @patch(
        "backend.api.routers.track_admin.enrich_track",
        new_callable=AsyncMock,
        return_value=_ENRICH_RESULT,
    )
    @patch(
        "backend.api.routers.track_admin.query_overpass_raceway",
        new_callable=AsyncMock,
    )
    async def test_import_osm_creates_track(
        self,
        mock_osm: AsyncMock,
        mock_enrich: AsyncMock,
        client: AsyncClient,
    ) -> None:
        """OSM import creates a track and runs enrichment."""
        mock_osm.return_value = [_mock_osm_result()]

        resp = await client.post(
            "/api/track-admin/import/osm",
            json={"lat": 33.53, "lon": -86.62},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert len(data["tracks_created"]) == 1
        assert data["tracks_created"][0] == "test-raceway"
        assert len(data["enrichment_results"]) == 1
        assert data["enrichment_results"][0]["corners_detected"] == 4

        mock_osm.assert_called_once_with(33.53, -86.62, radius_m=5000)
        mock_enrich.assert_called_once()

    @pytest.mark.asyncio
    @patch(
        "backend.api.routers.track_admin.query_overpass_raceway",
        new_callable=AsyncMock,
        return_value=[],
    )
    async def test_import_osm_no_results(
        self,
        mock_osm: AsyncMock,
        client: AsyncClient,
    ) -> None:
        """OSM import returns 404 when no raceways found."""
        resp = await client.post(
            "/api/track-admin/import/osm",
            json={"lat": 0.0, "lon": 0.0, "radius_m": 1000.0},
        )
        assert resp.status_code == 404
        assert "No raceways" in resp.json()["detail"]

    @pytest.mark.asyncio
    @patch(
        "backend.api.routers.track_admin.enrich_track",
        new_callable=AsyncMock,
        return_value=_ENRICH_RESULT,
    )
    @patch(
        "backend.api.routers.track_admin.query_overpass_raceway",
        new_callable=AsyncMock,
    )
    async def test_import_osm_skips_duplicate(
        self,
        mock_osm: AsyncMock,
        mock_enrich: AsyncMock,
        client: AsyncClient,
    ) -> None:
        """OSM import skips tracks whose slug already exists."""
        mock_osm.return_value = [_mock_osm_result()]

        # First import
        resp1 = await client.post(
            "/api/track-admin/import/osm",
            json={"lat": 33.53, "lon": -86.62},
        )
        assert resp1.status_code == 201
        assert len(resp1.json()["tracks_created"]) == 1

        # Second import — same track should be skipped
        resp2 = await client.post(
            "/api/track-admin/import/osm",
            json={"lat": 33.53, "lon": -86.62},
        )
        assert resp2.status_code == 201
        assert len(resp2.json()["tracks_created"]) == 0


# ---------------------------------------------------------------------------
# GeoJSON Import
# ---------------------------------------------------------------------------


class TestGeoJsonImport:
    @pytest.mark.asyncio
    @patch(
        "backend.api.routers.track_admin.enrich_track",
        new_callable=AsyncMock,
        return_value=_ENRICH_RESULT,
    )
    async def test_import_geojson_linestring(
        self,
        mock_enrich: AsyncMock,
        client: AsyncClient,
    ) -> None:
        """GeoJSON import with a LineString creates a track."""
        geojson = {
            "type": "LineString",
            "coordinates": [
                [-86.62, 33.53],
                [-86.619, 33.531],
                [-86.618, 33.532],
                [-86.617, 33.531],
                [-86.618, 33.53],
            ],
        }
        resp = await client.post(
            "/api/track-admin/import/geojson",
            json={"name": "GeoJSON Track", "slug": "geojson-track", "geojson": geojson},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["tracks_created"] == ["geojson-track"]
        assert len(data["enrichment_results"]) == 1
        mock_enrich.assert_called_once()

    @pytest.mark.asyncio
    @patch(
        "backend.api.routers.track_admin.enrich_track",
        new_callable=AsyncMock,
        return_value=_ENRICH_RESULT,
    )
    async def test_import_geojson_polygon(
        self,
        mock_enrich: AsyncMock,
        client: AsyncClient,
    ) -> None:
        """GeoJSON import with a Polygon extracts the exterior ring."""
        geojson = {
            "type": "Polygon",
            "coordinates": [
                [
                    [-86.62, 33.53],
                    [-86.619, 33.531],
                    [-86.618, 33.532],
                    [-86.617, 33.531],
                    [-86.62, 33.53],
                ]
            ],
        }
        resp = await client.post(
            "/api/track-admin/import/geojson",
            json={"name": "Polygon Track", "slug": "polygon-track", "geojson": geojson},
        )
        assert resp.status_code == 201
        assert resp.json()["tracks_created"] == ["polygon-track"]

    @pytest.mark.asyncio
    async def test_import_geojson_invalid_geometry(self, client: AsyncClient) -> None:
        """GeoJSON import with unsupported geometry returns 422."""
        geojson = {
            "type": "Point",
            "coordinates": [-86.62, 33.53],
        }
        resp = await client.post(
            "/api/track-admin/import/geojson",
            json={"name": "Bad", "slug": "bad-geojson", "geojson": geojson},
        )
        assert resp.status_code == 422
        assert "Unsupported" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_import_geojson_too_few_points(self, client: AsyncClient) -> None:
        """GeoJSON import with <3 points returns 422."""
        geojson = {
            "type": "LineString",
            "coordinates": [[-86.62, 33.53], [-86.619, 33.531]],
        }
        resp = await client.post(
            "/api/track-admin/import/geojson",
            json={"name": "Short", "slug": "short-line", "geojson": geojson},
        )
        assert resp.status_code == 422
        assert "at least 3" in resp.json()["detail"]

    @pytest.mark.asyncio
    @patch(
        "backend.api.routers.track_admin.enrich_track",
        new_callable=AsyncMock,
        return_value=_ENRICH_RESULT,
    )
    async def test_import_geojson_feature_wrapper(
        self,
        mock_enrich: AsyncMock,
        client: AsyncClient,
    ) -> None:
        """GeoJSON import unwraps Feature and FeatureCollection."""
        geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [
                            [-86.62, 33.53],
                            [-86.619, 33.531],
                            [-86.618, 33.532],
                        ],
                    },
                    "properties": {},
                }
            ],
        }
        resp = await client.post(
            "/api/track-admin/import/geojson",
            json={"name": "FC Track", "slug": "fc-track", "geojson": geojson},
        )
        assert resp.status_code == 201
        assert resp.json()["tracks_created"] == ["fc-track"]

    @pytest.mark.asyncio
    @patch(
        "backend.api.routers.track_admin.enrich_track",
        new_callable=AsyncMock,
        return_value=_ENRICH_RESULT,
    )
    async def test_import_geojson_duplicate_slug(
        self,
        mock_enrich: AsyncMock,
        client: AsyncClient,
    ) -> None:
        """GeoJSON import with existing slug returns 409."""
        geojson = {
            "type": "LineString",
            "coordinates": [
                [-86.62, 33.53],
                [-86.619, 33.531],
                [-86.618, 33.532],
            ],
        }
        await client.post(
            "/api/track-admin/import/geojson",
            json={"name": "First", "slug": "dup-geo", "geojson": geojson},
        )
        resp = await client.post(
            "/api/track-admin/import/geojson",
            json={"name": "Second", "slug": "dup-geo", "geojson": geojson},
        )
        assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Enrichment Trigger
# ---------------------------------------------------------------------------


class TestEnrichmentTrigger:
    @pytest.mark.asyncio
    @patch(
        "backend.api.routers.track_admin.enrich_track",
        new_callable=AsyncMock,
        return_value=_ENRICH_RESULT,
    )
    async def test_enrich_existing_track_with_corners(
        self,
        mock_enrich: AsyncMock,
        client: AsyncClient,
    ) -> None:
        """Enrichment trigger succeeds for track with corner lat/lon data."""
        await client.post(
            "/api/track-admin/",
            json={
                "slug": "enrich-test",
                "name": "Enrich Test",
                "source": "manual",
                "length_m": 3000.0,
            },
        )
        # Add corners with lat/lon
        corners = [
            {"number": 1, "fraction": 0.1, "lat": 33.53, "lon": -86.62},
            {"number": 2, "fraction": 0.3, "lat": 33.531, "lon": -86.619},
            {"number": 3, "fraction": 0.6, "lat": 33.532, "lon": -86.618},
            {"number": 4, "fraction": 0.85, "lat": 33.531, "lon": -86.62},
        ]
        await client.put("/api/track-admin/enrich-test/corners", json=corners)

        resp = await client.post("/api/track-admin/enrich-test/enrich")
        assert resp.status_code == 200
        data = resp.json()
        assert data["corners_detected"] == 4
        assert data["elevation_source"] == "copernicus"
        assert data["brake_markers"] == 4
        assert data["steps_logged"] == 4

        mock_enrich.assert_called_once()

    @pytest.mark.asyncio
    @patch(
        "backend.api.routers.track_admin.enrich_track",
        new_callable=AsyncMock,
        return_value=_ENRICH_RESULT,
    )
    async def test_enrich_track_with_geojson(
        self,
        mock_enrich: AsyncMock,
        client: AsyncClient,
    ) -> None:
        """Enrichment trigger uses stored centerline_geojson if available."""
        geojson = {
            "type": "LineString",
            "coordinates": [
                [-86.62, 33.53],
                [-86.619, 33.531],
                [-86.618, 33.532],
                [-86.617, 33.531],
            ],
        }
        await client.post(
            "/api/track-admin/",
            json={
                "slug": "enrich-geo",
                "name": "Enrich Geo",
                "source": "manual",
            },
        )
        # Store centerline_geojson via PATCH
        await client.patch(
            "/api/track-admin/enrich-geo",
            json={"centerline_geojson": geojson},
        )

        resp = await client.post("/api/track-admin/enrich-geo/enrich")
        assert resp.status_code == 200
        assert resp.json()["corners_detected"] == 4

    @pytest.mark.asyncio
    async def test_enrich_not_found(self, client: AsyncClient) -> None:
        """Enrichment on nonexistent track returns 404."""
        resp = await client.post("/api/track-admin/nonexistent/enrich")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_enrich_no_centerline(self, client: AsyncClient) -> None:
        """Enrichment with no centerline data returns 422."""
        await client.post(
            "/api/track-admin/",
            json={
                "slug": "no-center",
                "name": "No Center",
                "source": "manual",
            },
        )
        resp = await client.post("/api/track-admin/no-center/enrich")
        assert resp.status_code == 422
        assert "no centerline data" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_enrich_corners_without_latlon(self, client: AsyncClient) -> None:
        """Enrichment fails with 422 when corners exist but lack lat/lon."""
        await client.post(
            "/api/track-admin/",
            json={
                "slug": "no-latlon",
                "name": "No LatLon",
                "source": "manual",
            },
        )
        # Corners without lat/lon
        corners = [
            {"number": 1, "fraction": 0.1},
            {"number": 2, "fraction": 0.5},
        ]
        await client.put("/api/track-admin/no-latlon/corners", json=corners)

        resp = await client.post("/api/track-admin/no-latlon/enrich")
        assert resp.status_code == 422
