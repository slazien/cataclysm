"""Tests for the line-analysis endpoint."""

from __future__ import annotations

import numpy as np
import pytest
from cataclysm.corner_line import CornerLineProfile
from cataclysm.gps_line import GPSTrace, ReferenceCenterline
from httpx import AsyncClient
from scipy.spatial import cKDTree

from backend.api.services import session_store
from backend.tests.conftest import build_synthetic_csv


async def _upload_session(
    client: AsyncClient,
    csv_bytes: bytes | None = None,
    filename: str = "test.csv",
) -> str:
    """Upload a CSV and return the session_id."""
    if csv_bytes is None:
        csv_bytes = build_synthetic_csv(n_laps=5)
    resp = await client.post(
        "/api/sessions/upload",
        files=[("files", (filename, csv_bytes, "text/csv"))],
    )
    assert resp.status_code == 200
    session_id: str = resp.json()["session_ids"][0]
    return session_id


def _inject_line_analysis(session_id: str) -> None:
    """Inject synthetic line analysis data into a stored session.

    This ensures the endpoint test exercises the serialization path
    regardless of whether the pipeline's GPS quality check passed.
    """
    sd = session_store.get_session(session_id)
    assert sd is not None

    # Build simple synthetic traces (3 laps)
    n_points = 100
    distance = np.arange(n_points) * 0.7
    base_e = np.cos(np.linspace(0, 2 * np.pi, n_points)) * 50
    base_n = np.sin(np.linspace(0, 2 * np.pi, n_points)) * 50

    traces = []
    for lap_num in [2, 3, 4]:
        offset = (lap_num - 2) * 0.3  # slight offset per lap
        traces.append(
            GPSTrace(
                e=base_e + offset,
                n=base_n + offset * 0.5,
                distance_m=distance,
                lap_number=lap_num,
            )
        )

    # Build reference centerline from median
    e_med = np.median([t.e for t in traces], axis=0)
    n_med = np.median([t.n for t in traces], axis=0)
    points = np.column_stack([e_med, n_med])
    kdtree = cKDTree(points)

    ref = ReferenceCenterline(
        e=e_med,
        n=n_med,
        kdtree=kdtree,
        n_laps_used=3,
        left_edge=np.full(n_points, -2.0),
        right_edge=np.full(n_points, 2.0),
    )

    # Inject corner line profiles
    profiles = [
        CornerLineProfile(
            corner_number=1,
            n_laps=3,
            d_entry_median=0.5,
            d_apex_median=-0.2,
            d_exit_median=0.8,
            apex_fraction_median=0.55,
            d_apex_sd=0.3,
            line_error_type="good_line",
            severity="minor",
            consistency_tier="consistent",
            allen_berg_type="A",
        ),
        CornerLineProfile(
            corner_number=2,
            n_laps=3,
            d_entry_median=1.2,
            d_apex_median=0.1,
            d_exit_median=-0.5,
            apex_fraction_median=0.35,
            d_apex_sd=0.8,
            line_error_type="early_apex",
            severity="moderate",
            consistency_tier="developing",
            allen_berg_type="B",
        ),
    ]

    sd.gps_traces = traces
    sd.reference_centerline = ref
    sd.corner_line_profiles = profiles


@pytest.mark.asyncio
async def test_line_analysis_available(client: AsyncClient) -> None:
    """GET /line-analysis with injected data returns full response."""
    session_id = await _upload_session(client)
    _inject_line_analysis(session_id)

    resp = await client.get(f"/api/sessions/{session_id}/line-analysis")
    assert resp.status_code == 200
    data = resp.json()

    assert data["session_id"] == session_id
    assert data["available"] is True
    assert data["n_laps_used"] == 3

    # Corner profiles
    assert len(data["corner_profiles"]) == 2
    p1 = data["corner_profiles"][0]
    assert p1["corner_number"] == 1
    assert p1["line_error_type"] == "good_line"
    assert p1["consistency_tier"] == "consistent"
    assert p1["allen_berg_type"] == "A"

    p2 = data["corner_profiles"][1]
    assert p2["line_error_type"] == "early_apex"
    assert p2["severity"] == "moderate"

    # Lateral offset traces
    assert len(data["traces"]) == 3  # all 3 laps
    for trace in data["traces"]:
        assert "lap_number" in trace
        assert "offsets_m" in trace
        assert len(trace["offsets_m"]) > 0

    # Distance grid + reference coords
    assert len(data["distance_m"]) > 0
    assert len(data["reference_e"]) > 0
    assert len(data["reference_n"]) > 0
    assert len(data["reference_e"]) == len(data["reference_n"])


@pytest.mark.asyncio
async def test_line_analysis_with_lap_filter(client: AsyncClient) -> None:
    """GET /line-analysis?laps=2&laps=3 returns only requested laps."""
    session_id = await _upload_session(client)
    _inject_line_analysis(session_id)

    resp = await client.get(
        f"/api/sessions/{session_id}/line-analysis",
        params={"laps": [2, 3]},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["available"] is True
    assert len(data["traces"]) == 2
    lap_nums = {t["lap_number"] for t in data["traces"]}
    assert lap_nums == {2, 3}


@pytest.mark.asyncio
async def test_line_analysis_not_available(client: AsyncClient) -> None:
    """GET /line-analysis returns available=False when no line data."""
    session_id = await _upload_session(client)
    # Don't inject line data — pipeline may not produce it for synthetic data

    # Ensure the session has no line data
    sd = session_store.get_session(session_id)
    assert sd is not None
    sd.gps_traces = []
    sd.reference_centerline = None
    sd.corner_line_profiles = []

    resp = await client.get(f"/api/sessions/{session_id}/line-analysis")
    assert resp.status_code == 200
    data = resp.json()

    assert data["available"] is False
    assert data["corner_profiles"] == []
    assert data["traces"] == []
    assert data["distance_m"] == []
    assert data["n_laps_used"] == 0


@pytest.mark.asyncio
async def test_line_analysis_not_found(client: AsyncClient) -> None:
    """GET /line-analysis with bad session ID returns 404."""
    resp = await client.get("/api/sessions/nonexistent/line-analysis")
    assert resp.status_code == 404
