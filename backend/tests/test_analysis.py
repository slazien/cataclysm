"""Tests for analysis endpoints."""

from __future__ import annotations

import pytest
from cataclysm.equipment import (
    EquipmentProfile,
    MuSource,
    SessionEquipment,
    TireCompoundCategory,
    TireSpec,
)
from httpx import AsyncClient

from backend.api.services import equipment_store
from backend.tests.conftest import build_synthetic_csv


async def _upload_session(
    client: AsyncClient,
    csv_bytes: bytes | None = None,
    filename: str = "test.csv",
) -> str:
    """Helper: upload a CSV and return the session_id.

    Uses 5 laps by default so that after removing in/out laps (1st + last),
    we still have 3 coaching laps -- enough for consistency and gains.
    """
    if csv_bytes is None:
        csv_bytes = build_synthetic_csv(n_laps=5)
    resp = await client.post(
        "/api/sessions/upload",
        files=[("files", (filename, csv_bytes, "text/csv"))],
    )
    assert resp.status_code == 200
    session_id: str = resp.json()["session_ids"][0]
    return session_id


@pytest.mark.asyncio
async def test_get_corners(client: AsyncClient) -> None:
    """GET /api/sessions/{id}/corners returns best-lap corners."""
    session_id = await _upload_session(client)

    response = await client.get(f"/api/sessions/{session_id}/corners")
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == session_id
    assert "lap_number" in data
    assert "corners" in data
    assert isinstance(data["corners"], list)
    if data["corners"]:
        corner = data["corners"][0]
        assert "number" in corner
        assert "entry_distance_m" in corner
        assert "exit_distance_m" in corner
        assert "min_speed_mph" in corner
        assert "apex_type" in corner


@pytest.mark.asyncio
async def test_get_corners_not_found(client: AsyncClient) -> None:
    """GET /api/sessions/{id}/corners with bad ID returns 404."""
    response = await client.get("/api/sessions/nonexistent/corners")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_all_laps_corners(client: AsyncClient) -> None:
    """GET /api/sessions/{id}/corners/all-laps returns per-lap corners."""
    session_id = await _upload_session(client)

    response = await client.get(f"/api/sessions/{session_id}/corners/all-laps")
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == session_id
    assert "laps" in data
    assert isinstance(data["laps"], dict)


@pytest.mark.asyncio
async def test_get_consistency(client: AsyncClient) -> None:
    """GET /api/sessions/{id}/consistency returns consistency metrics."""
    session_id = await _upload_session(client)

    response = await client.get(f"/api/sessions/{session_id}/consistency")
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == session_id
    assert "data" in data
    assert "lap_consistency" in data["data"]


@pytest.mark.asyncio
async def test_get_gains(client: AsyncClient) -> None:
    """GET /api/sessions/{id}/gains returns gain estimation data."""
    session_id = await _upload_session(client)

    response = await client.get(f"/api/sessions/{session_id}/gains")
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == session_id
    assert "data" in data


@pytest.mark.asyncio
async def test_get_grip(client: AsyncClient) -> None:
    """GET /api/sessions/{id}/grip returns grip estimation data."""
    session_id = await _upload_session(client)

    response = await client.get(f"/api/sessions/{session_id}/grip")
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == session_id
    assert "data" in data
    assert "composite_max_g" in data["data"]


@pytest.mark.asyncio
async def test_get_delta(client: AsyncClient) -> None:
    """GET /api/sessions/{id}/delta?ref=N&comp=M returns delta between two laps."""
    session_id = await _upload_session(client)

    # Get available laps
    laps_resp = await client.get(f"/api/sessions/{session_id}/laps")
    laps = laps_resp.json()
    if len(laps) < 2:
        pytest.skip("Need at least 2 laps for delta test")

    ref_lap = laps[0]["lap_number"]
    comp_lap = laps[1]["lap_number"]

    response = await client.get(
        f"/api/sessions/{session_id}/delta",
        params={"ref": ref_lap, "comp": comp_lap},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == session_id
    assert data["ref_lap"] == ref_lap
    assert data["comp_lap"] == comp_lap
    assert "distance_m" in data
    assert "delta_s" in data
    assert "total_delta_s" in data
    assert isinstance(data["distance_m"], list)
    assert isinstance(data["delta_s"], list)


@pytest.mark.asyncio
async def test_get_delta_invalid_lap(client: AsyncClient) -> None:
    """GET /api/sessions/{id}/delta with nonexistent lap returns 404."""
    session_id = await _upload_session(client)

    response = await client.get(
        f"/api/sessions/{session_id}/delta",
        params={"ref": 999, "comp": 998},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_linked_chart_data(client: AsyncClient) -> None:
    """GET /api/sessions/{id}/charts/linked?laps=N,M returns bundled traces."""
    session_id = await _upload_session(client)

    # Get available laps
    laps_resp = await client.get(f"/api/sessions/{session_id}/laps")
    laps = laps_resp.json()
    if len(laps) < 2:
        pytest.skip("Need at least 2 laps for linked chart test")

    lap_nums = [laps[0]["lap_number"], laps[1]["lap_number"]]

    response = await client.get(
        f"/api/sessions/{session_id}/charts/linked",
        params={"laps": lap_nums},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == session_id
    assert data["laps"] == lap_nums
    assert "distance_m" in data
    assert "speed_traces" in data
    assert "lateral_g_traces" in data
    assert "longitudinal_g_traces" in data
    assert "heading_traces" in data


@pytest.mark.asyncio
async def test_get_linked_chart_invalid_lap(client: AsyncClient) -> None:
    """GET /api/sessions/{id}/charts/linked with bad lap returns 404."""
    session_id = await _upload_session(client)

    response = await client.get(
        f"/api/sessions/{session_id}/charts/linked",
        params={"laps": [999]},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_ideal_lap(client: AsyncClient) -> None:
    """GET /api/sessions/{id}/ideal-lap returns ideal lap trace."""
    session_id = await _upload_session(client)

    response = await client.get(f"/api/sessions/{session_id}/ideal-lap")
    # May return 422 if fewer than 2 clean laps, or 200 with data
    if response.status_code == 200:
        data = response.json()
        assert data["session_id"] == session_id
        assert "distance_m" in data
        assert "speed_mph" in data
        assert "segment_sources" in data
    else:
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# Optimal profile tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_optimal_profile_default_params(client: AsyncClient) -> None:
    """GET /{id}/optimal-profile returns profile with default vehicle params."""
    session_id = await _upload_session(client)

    response = await client.get(f"/api/sessions/{session_id}/optimal-profile")
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == session_id
    assert isinstance(data["distance_m"], list)
    assert isinstance(data["optimal_speed_mph"], list)
    assert isinstance(data["max_cornering_speed_mph"], list)
    assert isinstance(data["brake_points"], list)
    assert isinstance(data["throttle_points"], list)
    assert isinstance(data["lap_time_s"], float)
    assert data["equipment_profile_id"] is None

    # Default vehicle params (from default_vehicle_params)
    vp = data["vehicle_params"]
    assert vp["mu"] == 1.0
    assert vp["max_accel_g"] == 0.5
    assert vp["max_decel_g"] == 1.0
    assert vp["max_lateral_g"] == 1.0
    assert vp["top_speed_mps"] == 80.0


@pytest.mark.asyncio
async def test_get_optimal_profile_not_found(client: AsyncClient) -> None:
    """GET /{id}/optimal-profile with bad session ID returns 404."""
    response = await client.get("/api/sessions/nonexistent/optimal-profile")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_optimal_profile_with_equipment(client: AsyncClient) -> None:
    """Assigning low-grip equipment should change optimal profile params."""
    session_id = await _upload_session(client)

    # Get baseline optimal profile (default params)
    resp_default = await client.get(f"/api/sessions/{session_id}/optimal-profile")
    assert resp_default.status_code == 200
    default_data = resp_default.json()
    default_lap_time = default_data["lap_time_s"]

    # Create a low-grip street tire profile and assign to session
    tire = TireSpec(
        model="Budget Street",
        compound_category=TireCompoundCategory.STREET,
        size="225/45R17",
        treadwear_rating=400,
        estimated_mu=0.85,
        mu_source=MuSource.FORMULA_ESTIMATE,
        mu_confidence="medium",
    )
    profile = EquipmentProfile(id="low-grip", name="Budget Street", tires=tire)
    equipment_store.store_profile(profile)
    equipment_store.store_session_equipment(
        SessionEquipment(session_id=session_id, profile_id="low-grip")
    )

    # Get optimal profile with equipment
    resp_equip = await client.get(f"/api/sessions/{session_id}/optimal-profile")
    assert resp_equip.status_code == 200
    equip_data = resp_equip.json()

    # Vehicle params should reflect the low-grip tire
    vp = equip_data["vehicle_params"]
    assert vp["mu"] == 0.85
    assert vp["max_lateral_g"] == 0.85
    assert vp["max_accel_g"] == 0.40  # STREET category
    assert abs(vp["max_decel_g"] - 0.85 * 0.95) < 1e-6
    assert equip_data["equipment_profile_id"] == "low-grip"

    # Lower grip should produce a slower optimal lap time
    equip_lap_time = equip_data["lap_time_s"]
    assert equip_lap_time > default_lap_time, (
        f"Low-grip tire should produce slower lap time: {equip_lap_time} vs {default_lap_time}"
    )

    # Clean up
    equipment_store.delete_session_equipment(session_id)
    equipment_store.delete_profile("low-grip")
