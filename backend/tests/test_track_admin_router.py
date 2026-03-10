"""Tests for the track admin REST API."""

from __future__ import annotations

import pytest
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
