"""Extended tests for leaderboards router — covers uncovered lines [38, 53].

Line 38: corner_leaderboard — get_corner_leaderboard call → LeaderboardResponse
Line 53: corner_kings — get_kings call → KingsResponse
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


class TestCornerLeaderboard:
    """Tests for GET /api/leaderboards/{track}/corners."""

    @pytest.mark.asyncio
    async def test_corner_leaderboard_returns_response(self, client: AsyncClient) -> None:
        """GET /api/leaderboards/{track}/corners returns LeaderboardResponse (line 38)."""
        with patch(
            "backend.api.routers.leaderboards.get_corner_leaderboard",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_lb:
            resp = await client.get("/api/leaderboards/barber/corners?corner=1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["track_name"] == "barber"
        assert data["corner_number"] == 1
        assert "entries" in data
        mock_lb.assert_called_once()

    @pytest.mark.asyncio
    async def test_corner_leaderboard_with_category(self, client: AsyncClient) -> None:
        """GET with category=min_speed calls service with correct params."""
        with patch(
            "backend.api.routers.leaderboards.get_corner_leaderboard",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_lb:
            resp = await client.get(
                "/api/leaderboards/barber/corners?corner=5&category=min_speed&limit=5"
            )
        assert resp.status_code == 200
        # Verify the service was called with the right params
        call_args = mock_lb.call_args
        assert call_args[1]["category"] == "min_speed"
        assert call_args[1]["limit"] == 5

    @pytest.mark.asyncio
    async def test_corner_leaderboard_with_entries(self, client: AsyncClient) -> None:
        """GET /api/leaderboards/{track}/corners returns entries when data exists."""
        # CornerRecordEntry uses min_speed_mps (domain units), not min_speed_mph
        fake_entry = {
            "rank": 1,
            "user_name": "Alex Racer",
            "session_date": "2026-03-01",
            "sector_time_s": 12.345,
            "min_speed_mps": 20.1168,  # ~45 mph in m/s
            "brake_point_m": None,
            "consistency_cv": None,
            "is_king": True,
        }
        with patch(
            "backend.api.routers.leaderboards.get_corner_leaderboard",
            new_callable=AsyncMock,
            return_value=[fake_entry],
        ):
            resp = await client.get("/api/leaderboards/barber/corners?corner=1")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["entries"]) == 1
        assert data["entries"][0]["rank"] == 1
        assert data["entries"][0]["user_name"] == "Alex Racer"


class TestCornerKings:
    """Tests for GET /api/leaderboards/{track}/kings."""

    @pytest.mark.asyncio
    async def test_corner_kings_returns_response(self, client: AsyncClient) -> None:
        """GET /api/leaderboards/{track}/kings returns KingsResponse (line 53)."""
        with patch(
            "backend.api.routers.leaderboards.get_kings",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_kings:
            resp = await client.get("/api/leaderboards/barber/kings")
        assert resp.status_code == 200
        data = resp.json()
        assert data["track_name"] == "barber"
        assert "kings" in data
        mock_kings.assert_called_once()

    @pytest.mark.asyncio
    async def test_corner_kings_with_data(self, client: AsyncClient) -> None:
        """GET /api/leaderboards/{track}/kings returns kings data."""
        fake_king = {
            "corner_number": 1,
            "user_name": "Speed Demon",
            "best_time_s": 11.5,
        }
        with patch(
            "backend.api.routers.leaderboards.get_kings",
            new_callable=AsyncMock,
            return_value=[fake_king],
        ):
            resp = await client.get("/api/leaderboards/barber/kings")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["kings"]) == 1
        assert data["kings"][0]["corner_number"] == 1
        assert data["kings"][0]["user_name"] == "Speed Demon"
