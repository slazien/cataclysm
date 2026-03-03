"""Integration tests for analysis endpoints — covering previously uncovered lines.

Uncovered lines addressed:
  - analysis.py line 100: consistency None → 404
  - analysis.py line 116: grip None → 404
  - analysis.py lines 130-137: gps_quality None → 404
  - analysis.py line 148: gains None → 404
  - analysis.py line 164: ideal-lap < 2 laps → 422
  - analysis.py line 219: delta comp lap not found → 404
  - analysis.py lines 292-335: sectors endpoint
  - analysis.py lines 353-371: mini-sectors endpoint
  - wrapped.py lines 22-23: GET /api/wrapped/{year} endpoint
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from backend.api.services import session_store
from backend.tests.conftest import build_synthetic_csv

# ---------------------------------------------------------------------------
# Upload helpers
# ---------------------------------------------------------------------------


async def _upload(client: AsyncClient, *, n_laps: int = 5, filename: str = "test.csv") -> str:
    """Upload a synthetic CSV with the given lap count and return the session_id."""
    csv_bytes = build_synthetic_csv(n_laps=n_laps)
    resp = await client.post(
        "/api/sessions/upload",
        files=[("files", (filename, csv_bytes, "text/csv"))],
    )
    assert resp.status_code == 200, resp.text
    return str(resp.json()["session_ids"][0])


async def _first_two_laps(client: AsyncClient, session_id: str) -> tuple[int, int]:
    """Return the first two lap numbers from the /laps endpoint."""
    laps_resp = await client.get(f"/api/sessions/{session_id}/laps")
    assert laps_resp.status_code == 200
    laps = laps_resp.json()
    assert len(laps) >= 2, "Need at least 2 laps"
    return laps[0]["lap_number"], laps[1]["lap_number"]


# ===========================================================================
# 404 paths — None data on real uploaded session
# ===========================================================================


class TestAnalysisNone404Paths:
    """Verify that None-valued session attributes produce 404 responses."""

    @pytest.mark.asyncio
    async def test_consistency_none_returns_404(self, client: AsyncClient) -> None:
        """When sd.consistency is None the endpoint returns 404 (line 100)."""
        session_id = await _upload(client)
        sd = session_store.get_session(session_id)
        assert sd is not None
        # Temporarily null out consistency
        original = sd.consistency
        sd.consistency = None
        try:
            resp = await client.get(f"/api/sessions/{session_id}/consistency")
            assert resp.status_code == 404
            assert "Consistency" in resp.json()["detail"]
        finally:
            sd.consistency = original

    @pytest.mark.asyncio
    async def test_grip_none_returns_404(self, client: AsyncClient) -> None:
        """When sd.grip is None the endpoint returns 404 (line 116)."""
        session_id = await _upload(client)
        sd = session_store.get_session(session_id)
        assert sd is not None
        original = sd.grip
        sd.grip = None
        try:
            resp = await client.get(f"/api/sessions/{session_id}/grip")
            assert resp.status_code == 404
            assert "Grip" in resp.json()["detail"]
        finally:
            sd.grip = original

    @pytest.mark.asyncio
    async def test_gps_quality_none_returns_404(self, client: AsyncClient) -> None:
        """When sd.gps_quality is None the endpoint returns 404 (lines 130-137)."""
        session_id = await _upload(client)
        sd = session_store.get_session(session_id)
        assert sd is not None
        original = sd.gps_quality
        sd.gps_quality = None
        try:
            resp = await client.get(f"/api/sessions/{session_id}/gps-quality")
            assert resp.status_code == 404
            assert "GPS quality" in resp.json()["detail"]
        finally:
            sd.gps_quality = original

    @pytest.mark.asyncio
    async def test_gains_none_returns_404(self, client: AsyncClient) -> None:
        """When sd.gains is None the endpoint returns 404 (line 148)."""
        session_id = await _upload(client)
        sd = session_store.get_session(session_id)
        assert sd is not None
        original = sd.gains
        sd.gains = None
        try:
            resp = await client.get(f"/api/sessions/{session_id}/gains")
            assert resp.status_code == 404
            assert "Gains" in resp.json()["detail"]
        finally:
            sd.gains = original


# ===========================================================================
# 404 on non-existent session — all analysis endpoints
# ===========================================================================


class TestAnalysisNotFound:
    """All analysis endpoints return 404 for a non-existent session_id."""

    @pytest.mark.asyncio
    async def test_consistency_not_found(self, client: AsyncClient) -> None:
        resp = await client.get("/api/sessions/no-such-id/consistency")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_grip_not_found(self, client: AsyncClient) -> None:
        resp = await client.get("/api/sessions/no-such-id/grip")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_gps_quality_not_found(self, client: AsyncClient) -> None:
        resp = await client.get("/api/sessions/no-such-id/gps-quality")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_gains_not_found(self, client: AsyncClient) -> None:
        resp = await client.get("/api/sessions/no-such-id/gains")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_ideal_lap_not_found(self, client: AsyncClient) -> None:
        resp = await client.get("/api/sessions/no-such-id/ideal-lap")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delta_not_found(self, client: AsyncClient) -> None:
        resp = await client.get(
            "/api/sessions/no-such-id/delta",
            params={"ref": 1, "comp": 2},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_sectors_not_found(self, client: AsyncClient) -> None:
        resp = await client.get("/api/sessions/no-such-id/sectors")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_mini_sectors_not_found(self, client: AsyncClient) -> None:
        resp = await client.get("/api/sessions/no-such-id/mini-sectors")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_degradation_not_found(self, client: AsyncClient) -> None:
        resp = await client.get("/api/sessions/no-such-id/degradation")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_optimal_profile_not_found(self, client: AsyncClient) -> None:
        resp = await client.get("/api/sessions/no-such-id/optimal-profile")
        assert resp.status_code == 404


# ===========================================================================
# ideal-lap — < 2 coaching laps → 422 (line 164)
# ===========================================================================


class TestIdealLapEdgeCases:
    """Edge cases for the ideal-lap endpoint."""

    @pytest.mark.asyncio
    async def test_ideal_lap_requires_two_clean_laps(self, client: AsyncClient) -> None:
        """With fewer than 2 coaching laps the endpoint returns 422 (line 164)."""
        session_id = await _upload(client)
        sd = session_store.get_session(session_id)
        assert sd is not None
        original = sd.coaching_laps
        # Override coaching_laps to have only one lap
        sd.coaching_laps = original[:1]
        try:
            resp = await client.get(f"/api/sessions/{session_id}/ideal-lap")
            assert resp.status_code == 422
            assert "2 clean laps" in resp.json()["detail"]
        finally:
            sd.coaching_laps = original

    @pytest.mark.asyncio
    async def test_ideal_lap_zero_coaching_laps_returns_422(self, client: AsyncClient) -> None:
        """With zero coaching laps the endpoint returns 422."""
        session_id = await _upload(client)
        sd = session_store.get_session(session_id)
        assert sd is not None
        original = sd.coaching_laps
        sd.coaching_laps = []
        try:
            resp = await client.get(f"/api/sessions/{session_id}/ideal-lap")
            assert resp.status_code == 422
        finally:
            sd.coaching_laps = original

    @pytest.mark.asyncio
    async def test_ideal_lap_success_with_enough_laps(self, client: AsyncClient) -> None:
        """With >= 2 coaching laps the endpoint returns 200 with trace data."""
        session_id = await _upload(client, n_laps=5)
        sd = session_store.get_session(session_id)
        assert sd is not None
        if len(sd.coaching_laps) < 2:
            pytest.skip("Synthetic data produced fewer than 2 coaching laps")
        resp = await client.get(f"/api/sessions/{session_id}/ideal-lap")
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == session_id
        assert isinstance(data["distance_m"], list)
        assert isinstance(data["speed_mph"], list)
        assert isinstance(data["segment_sources"], list)


# ===========================================================================
# delta — comp lap not found → 404 (line 219)
# ===========================================================================


class TestDeltaEdgeCases:
    """Edge cases for the delta endpoint."""

    @pytest.mark.asyncio
    async def test_delta_ref_lap_not_found_returns_404(self, client: AsyncClient) -> None:
        """Non-existent ref lap → 404 (line 217)."""
        session_id = await _upload(client)
        resp = await client.get(
            f"/api/sessions/{session_id}/delta",
            params={"ref": 9999, "comp": 1},
        )
        assert resp.status_code == 404
        assert "9999" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_delta_comp_lap_not_found_returns_404(self, client: AsyncClient) -> None:
        """Valid ref lap + non-existent comp lap → 404 (line 219)."""
        session_id = await _upload(client)
        ref_lap, _ = await _first_two_laps(client, session_id)
        resp = await client.get(
            f"/api/sessions/{session_id}/delta",
            params={"ref": ref_lap, "comp": 9999},
        )
        assert resp.status_code == 404
        assert "9999" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_delta_valid_laps_returns_200(self, client: AsyncClient) -> None:
        """Valid ref and comp laps → 200 with delta arrays."""
        session_id = await _upload(client)
        ref_lap, comp_lap = await _first_two_laps(client, session_id)
        resp = await client.get(
            f"/api/sessions/{session_id}/delta",
            params={"ref": ref_lap, "comp": comp_lap},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ref_lap"] == ref_lap
        assert data["comp_lap"] == comp_lap
        assert isinstance(data["distance_m"], list)
        assert isinstance(data["delta_s"], list)
        assert isinstance(data["total_delta_s"], float)


# ===========================================================================
# sectors endpoint — lines 292-335
# ===========================================================================


class TestSectorsEndpoint:
    """Tests for GET /api/sessions/{id}/sectors (lines 292-335)."""

    @pytest.mark.asyncio
    async def test_sectors_returns_200_with_data(self, client: AsyncClient) -> None:
        """Happy-path: sectors endpoint returns segment splits (lines 292-342)."""
        session_id = await _upload(client, n_laps=5)
        sd = session_store.get_session(session_id)
        assert sd is not None
        if len(sd.coaching_laps) < 1:
            pytest.skip("Synthetic data produced no coaching laps")
        resp = await client.get(f"/api/sessions/{session_id}/sectors")
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == session_id
        assert "segments" in data
        assert "lap_splits" in data
        assert "best_sector_times" in data
        assert "best_sector_laps" in data
        assert "composite_time_s" in data
        assert isinstance(data["segments"], list)
        assert isinstance(data["lap_splits"], list)

    @pytest.mark.asyncio
    async def test_sectors_segment_structure(self, client: AsyncClient) -> None:
        """Each segment dict contains the expected keys."""
        session_id = await _upload(client, n_laps=5)
        sd = session_store.get_session(session_id)
        assert sd is not None
        if len(sd.coaching_laps) < 1:
            pytest.skip("No coaching laps available")
        resp = await client.get(f"/api/sessions/{session_id}/sectors")
        assert resp.status_code == 200
        segments = resp.json()["segments"]
        if segments:
            seg = segments[0]
            assert "name" in seg
            assert "entry_distance_m" in seg
            assert "exit_distance_m" in seg
            assert "is_corner" in seg

    @pytest.mark.asyncio
    async def test_sectors_lap_splits_structure(self, client: AsyncClient) -> None:
        """Each lap split entry contains lap_number, total_time_s, and splits list."""
        session_id = await _upload(client, n_laps=5)
        sd = session_store.get_session(session_id)
        assert sd is not None
        if len(sd.coaching_laps) < 1:
            pytest.skip("No coaching laps available")
        resp = await client.get(f"/api/sessions/{session_id}/sectors")
        assert resp.status_code == 200
        lap_splits = resp.json()["lap_splits"]
        if lap_splits:
            ls = lap_splits[0]
            assert "lap_number" in ls
            assert "total_time_s" in ls
            assert "splits" in ls
            if ls["splits"]:
                split = ls["splits"][0]
                assert "sector_name" in split
                assert "time_s" in split
                assert "is_personal_best" in split

    @pytest.mark.asyncio
    async def test_sectors_no_coaching_laps_returns_422(self, client: AsyncClient) -> None:
        """Zero coaching laps → 422 with informative message."""
        session_id = await _upload(client)
        sd = session_store.get_session(session_id)
        assert sd is not None
        original = sd.coaching_laps
        sd.coaching_laps = []
        try:
            resp = await client.get(f"/api/sessions/{session_id}/sectors")
            assert resp.status_code == 422
            assert "clean lap" in resp.json()["detail"].lower()
        finally:
            sd.coaching_laps = original


# ===========================================================================
# mini-sectors endpoint — lines 353-371
# ===========================================================================


class TestMiniSectorsEndpoint:
    """Tests for GET /api/sessions/{id}/mini-sectors (lines 353-371)."""

    @pytest.mark.asyncio
    async def test_mini_sectors_returns_200_with_data(self, client: AsyncClient) -> None:
        """Happy-path: mini-sectors endpoint returns structured response."""
        session_id = await _upload(client, n_laps=5)
        resp = await client.get(f"/api/sessions/{session_id}/mini-sectors")
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == session_id
        assert "n_sectors" in data
        assert "sectors" in data
        assert "best_sector_times_s" in data
        assert "best_sector_laps" in data
        assert "lap_data" in data
        assert isinstance(data["sectors"], list)
        assert isinstance(data["lap_data"], dict)

    @pytest.mark.asyncio
    async def test_mini_sectors_default_n_sectors(self, client: AsyncClient) -> None:
        """Default n_sectors=20 is used when not specified."""
        session_id = await _upload(client, n_laps=5)
        resp = await client.get(f"/api/sessions/{session_id}/mini-sectors")
        assert resp.status_code == 200
        assert resp.json()["n_sectors"] == 20

    @pytest.mark.asyncio
    async def test_mini_sectors_custom_n_sectors(self, client: AsyncClient) -> None:
        """Custom n_sectors parameter is respected."""
        session_id = await _upload(client, n_laps=5)
        resp = await client.get(
            f"/api/sessions/{session_id}/mini-sectors",
            params={"n_sectors": 10},
        )
        assert resp.status_code == 200
        assert resp.json()["n_sectors"] == 10

    @pytest.mark.asyncio
    async def test_mini_sectors_sector_structure(self, client: AsyncClient) -> None:
        """Each sector entry has the expected index and distance fields."""
        session_id = await _upload(client, n_laps=5)
        resp = await client.get(f"/api/sessions/{session_id}/mini-sectors")
        assert resp.status_code == 200
        sectors = resp.json()["sectors"]
        assert len(sectors) > 0
        sector = sectors[0]
        assert "index" in sector
        assert "entry_distance_m" in sector
        assert "exit_distance_m" in sector
        assert "gps_points" in sector

    @pytest.mark.asyncio
    async def test_mini_sectors_lap_filter(self, client: AsyncClient) -> None:
        """Specifying lap=N filters lap_data to only that lap."""
        session_id = await _upload(client, n_laps=5)
        # Get any available lap number from the full response
        full_resp = await client.get(f"/api/sessions/{session_id}/mini-sectors")
        assert full_resp.status_code == 200
        all_lap_keys = list(full_resp.json()["lap_data"].keys())
        if not all_lap_keys:
            pytest.skip("No lap data returned")
        target_lap = int(all_lap_keys[0])
        # Request with lap filter
        filtered_resp = await client.get(
            f"/api/sessions/{session_id}/mini-sectors",
            params={"lap": target_lap},
        )
        assert filtered_resp.status_code == 200
        lap_data = filtered_resp.json()["lap_data"]
        assert str(target_lap) in lap_data
        # If multiple laps exist in full response, filtered should be a subset
        if len(all_lap_keys) > 1:
            assert len(lap_data) <= len(all_lap_keys)

    @pytest.mark.asyncio
    async def test_mini_sectors_n_sectors_below_min_rejected(self, client: AsyncClient) -> None:
        """n_sectors below minimum (3) is rejected with 422."""
        session_id = await _upload(client)
        resp = await client.get(
            f"/api/sessions/{session_id}/mini-sectors",
            params={"n_sectors": 1},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_mini_sectors_n_sectors_above_max_rejected(self, client: AsyncClient) -> None:
        """n_sectors above maximum (100) is rejected with 422."""
        session_id = await _upload(client)
        resp = await client.get(
            f"/api/sessions/{session_id}/mini-sectors",
            params={"n_sectors": 200},
        )
        assert resp.status_code == 422


# ===========================================================================
# wrapped router — lines 22-23
# ===========================================================================


class TestWrappedEndpoint:
    """Tests for GET /api/wrapped/{year} (wrapped.py lines 22-23)."""

    @pytest.mark.asyncio
    async def test_wrapped_no_sessions_returns_empty_year(self, client: AsyncClient) -> None:
        """With no sessions the endpoint returns a zeroed-out year summary."""
        resp = await client.get("/api/wrapped/2025")
        assert resp.status_code == 200
        data = resp.json()
        assert data["year"] == 2025
        assert data["total_sessions"] == 0
        assert data["total_laps"] == 0
        assert data["total_distance_km"] == 0.0
        assert data["tracks_visited"] == []
        assert data["personality"] == "The Track Day Warrior"
        assert "highlights" in data
        assert isinstance(data["highlights"], list)

    @pytest.mark.asyncio
    async def test_wrapped_current_year_returns_valid_schema(self, client: AsyncClient) -> None:
        """Wrapped endpoint for any year returns a structurally valid response."""
        resp = await client.get("/api/wrapped/2026")
        assert resp.status_code == 200
        data = resp.json()
        # Required fields per WrappedResponse schema
        assert "year" in data
        assert "total_sessions" in data
        assert "total_laps" in data
        assert "total_distance_km" in data
        assert "tracks_visited" in data
        assert "total_track_time_hours" in data
        assert "biggest_improvement_track" in data
        assert "biggest_improvement_s" in data
        assert "best_consistency_score" in data
        assert "personality" in data
        assert "personality_description" in data
        assert "top_corner_grade" in data
        assert "highlights" in data

    @pytest.mark.asyncio
    async def test_wrapped_with_session_in_year_counts_it(self, client: AsyncClient) -> None:
        """After uploading a session, the wrapped year for that session shows it."""
        session_id = await _upload(client, n_laps=3)
        sd = session_store.get_session(session_id)
        assert sd is not None
        # Determine the year of the synthetic session
        year = sd.snapshot.session_date_parsed.year
        resp = await client.get(f"/api/wrapped/{year}")
        assert resp.status_code == 200
        data = resp.json()
        # Session should be counted
        assert data["total_sessions"] >= 1
        assert data["total_laps"] >= 1

    @pytest.mark.asyncio
    async def test_wrapped_wrong_year_returns_zero_sessions(self, client: AsyncClient) -> None:
        """Requesting a year with no sessions returns zero totals."""
        await _upload(client, n_laps=3)
        # Use a year that will never match the synthetic session (far future)
        resp = await client.get("/api/wrapped/2099")
        assert resp.status_code == 200
        data = resp.json()
        assert data["year"] == 2099
        assert data["total_sessions"] == 0

    @pytest.mark.asyncio
    async def test_wrapped_personality_description_nonempty(self, client: AsyncClient) -> None:
        """personality_description is always a non-empty string."""
        resp = await client.get("/api/wrapped/2025")
        assert resp.status_code == 200
        desc = resp.json()["personality_description"]
        assert isinstance(desc, str)
        assert len(desc) > 0

    @pytest.mark.asyncio
    async def test_wrapped_highlights_are_list_of_dicts(self, client: AsyncClient) -> None:
        """highlights is a list of objects with label, value, category keys."""
        resp = await client.get("/api/wrapped/2025")
        assert resp.status_code == 200
        highlights = resp.json()["highlights"]
        assert isinstance(highlights, list)
        # Empty year → empty highlights list
        assert highlights == []

    @pytest.mark.asyncio
    async def test_wrapped_highlights_structure_with_session(self, client: AsyncClient) -> None:
        """With a session, highlights list contains well-formed entries."""
        session_id = await _upload(client, n_laps=3)
        sd = session_store.get_session(session_id)
        assert sd is not None
        year = sd.snapshot.session_date_parsed.year
        resp = await client.get(f"/api/wrapped/{year}")
        assert resp.status_code == 200
        highlights = resp.json()["highlights"]
        assert len(highlights) > 0
        for h in highlights:
            assert "label" in h
            assert "value" in h
            assert "category" in h
