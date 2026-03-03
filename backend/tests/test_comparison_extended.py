"""Tests for extended comparison fields: speed_traces, skill_dimensions, ai_verdict."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from httpx import AsyncClient

from backend.api.schemas.coaching import CoachingReportResponse, CornerGradeSchema
from backend.api.services.comparison import GRADE_SCORES, _compute_skill_dims
from backend.tests.conftest import build_synthetic_csv

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _upload_session(
    client: AsyncClient,
    csv_bytes: bytes | None = None,
    filename: str = "test.csv",
) -> str:
    """Helper: upload a CSV and return the session_id."""
    if csv_bytes is None:
        csv_bytes = build_synthetic_csv(n_laps=5)
    resp = await client.post(
        "/api/sessions/upload",
        files=[("files", (filename, csv_bytes, "text/csv"))],
    )
    assert resp.status_code == 200
    session_id: str = resp.json()["session_ids"][0]
    return session_id


def _make_coaching_report(session_id: str, n_corners: int = 5) -> CoachingReportResponse:
    """Build a mock coaching report with corner grades."""
    grades = [
        CornerGradeSchema(
            corner=i + 1,
            braking="A" if i % 2 == 0 else "B",
            trail_braking="B",
            min_speed="A" if i % 3 == 0 else "C",
            throttle="B",
            notes=f"Corner {i + 1} notes",
        )
        for i in range(n_corners)
    ]
    return CoachingReportResponse(
        session_id=session_id,
        status="ready",
        skill_level="intermediate",
        summary="Good session overall.",
        corner_grades=grades,
        priority_corners=[],
        patterns=["Consistent braking"],
        drills=["Trail braking drill"],
    )


# ---------------------------------------------------------------------------
# Unit tests for _compute_skill_dims
# ---------------------------------------------------------------------------


class TestComputeSkillDims:
    """Unit tests for the skill dimension aggregation helper."""

    def test_all_a_grades(self) -> None:
        """All A grades should produce 100.0 for all dims."""
        grades = [
            CornerGradeSchema(
                corner=1, braking="A", trail_braking="A", min_speed="A", throttle="A", notes=""
            )
        ]
        result = _compute_skill_dims(grades)
        assert result == {
            "braking": 100.0,
            "trail_braking": 100.0,
            "throttle": 100.0,
            "line": 100.0,
        }

    def test_all_f_grades(self) -> None:
        """All F grades should produce 20.0 for all dims."""
        grades = [
            CornerGradeSchema(
                corner=1, braking="F", trail_braking="F", min_speed="F", throttle="F", notes=""
            )
        ]
        result = _compute_skill_dims(grades)
        assert result == {"braking": 20.0, "trail_braking": 20.0, "throttle": 20.0, "line": 20.0}

    def test_mixed_grades_average(self) -> None:
        """Mixed grades should average correctly."""
        grades = [
            CornerGradeSchema(
                corner=1, braking="A", trail_braking="B", min_speed="C", throttle="D", notes=""
            ),
            CornerGradeSchema(
                corner=2, braking="B", trail_braking="C", min_speed="A", throttle="B", notes=""
            ),
        ]
        result = _compute_skill_dims(grades)
        # braking: (100+80)/2=90, trail_braking: (80+60)/2=70,
        # throttle: (40+80)/2=60, line (min_speed): (60+100)/2=80
        assert result == {"braking": 90.0, "trail_braking": 70.0, "throttle": 60.0, "line": 80.0}

    def test_empty_grades_list(self) -> None:
        """Empty grades list should produce default 60.0 for all dims."""
        result = _compute_skill_dims([])
        assert result == {"braking": 60.0, "trail_braking": 60.0, "throttle": 60.0, "line": 60.0}


class TestGradeScores:
    """Verify the grade-to-score mapping is complete."""

    def test_all_standard_grades_present(self) -> None:
        for grade in ("A", "B", "C", "D", "F"):
            assert grade in GRADE_SCORES

    def test_scores_descending(self) -> None:
        assert GRADE_SCORES["A"] > GRADE_SCORES["B"] > GRADE_SCORES["C"]
        assert GRADE_SCORES["C"] > GRADE_SCORES["D"] > GRADE_SCORES["F"]


# ---------------------------------------------------------------------------
# Integration tests via the comparison endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_comparison_includes_speed_traces(client: AsyncClient) -> None:
    """Comparison response should include speed_traces with distance and speed arrays."""
    sid_a = await _upload_session(client, filename="a.csv")
    sid_b = await _upload_session(client, filename="b.csv")

    resp = await client.get(f"/api/sessions/{sid_a}/compare/{sid_b}")
    assert resp.status_code == 200

    data = resp.json()
    assert "speed_traces" in data
    traces = data["speed_traces"]
    assert traces is not None
    assert "a" in traces and "b" in traces
    for key in ("a", "b"):
        assert "distance_m" in traces[key]
        assert "speed_mph" in traces[key]
        assert isinstance(traces[key]["distance_m"], list)
        assert isinstance(traces[key]["speed_mph"], list)
        assert len(traces[key]["distance_m"]) == len(traces[key]["speed_mph"])
        assert len(traces[key]["distance_m"]) > 0
        # All speed values should be non-negative
        assert all(v >= 0 for v in traces[key]["speed_mph"])


@pytest.mark.asyncio
async def test_comparison_speed_traces_match_distance_array(client: AsyncClient) -> None:
    """Speed trace distance arrays should span the lap distance."""
    sid = await _upload_session(client, filename="session.csv")

    resp = await client.get(f"/api/sessions/{sid}/compare/{sid}")
    assert resp.status_code == 200

    data = resp.json()
    traces = data["speed_traces"]
    # When comparing same session, both traces should be identical
    assert traces["a"]["distance_m"] == traces["b"]["distance_m"]
    assert traces["a"]["speed_mph"] == traces["b"]["speed_mph"]


@pytest.mark.asyncio
async def test_comparison_skill_dimensions_none_without_coaching(
    client: AsyncClient,
) -> None:
    """Skill dimensions should be None when no coaching reports exist."""
    sid_a = await _upload_session(client, filename="a.csv")
    sid_b = await _upload_session(client, filename="b.csv")

    resp = await client.get(f"/api/sessions/{sid_a}/compare/{sid_b}")
    assert resp.status_code == 200

    data = resp.json()
    assert data["skill_dimensions"] is None


@pytest.mark.asyncio
async def test_comparison_skill_dimensions_with_coaching(client: AsyncClient) -> None:
    """Skill dimensions should be populated when coaching reports exist."""
    sid_a = await _upload_session(client, filename="a.csv")
    sid_b = await _upload_session(client, filename="b.csv")

    report_a = _make_coaching_report(sid_a)
    report_b = _make_coaching_report(sid_b)

    async def mock_get_report(session_id: str) -> CoachingReportResponse | None:
        if session_id == sid_a:
            return report_a
        if session_id == sid_b:
            return report_b
        return None

    with patch(
        "backend.api.services.comparison.get_coaching_report",
        side_effect=mock_get_report,
    ):
        resp = await client.get(f"/api/sessions/{sid_a}/compare/{sid_b}")

    assert resp.status_code == 200
    data = resp.json()
    dims = data["skill_dimensions"]
    assert dims is not None
    assert "a" in dims and "b" in dims
    for key in ("a", "b"):
        assert "braking" in dims[key]
        assert "trail_braking" in dims[key]
        assert "throttle" in dims[key]
        assert "line" in dims[key]
        for dim_value in dims[key].values():
            assert 0 <= dim_value <= 100


@pytest.mark.asyncio
async def test_comparison_skill_dimensions_partial_coaching(
    client: AsyncClient,
) -> None:
    """Skill dimensions should be None when only one driver has coaching data.

    The radar chart requires both datasets — partial data would crash the frontend.
    """
    sid_a = await _upload_session(client, filename="a.csv")
    sid_b = await _upload_session(client, filename="b.csv")

    report_a = _make_coaching_report(sid_a)

    async def mock_get_report(session_id: str) -> CoachingReportResponse | None:
        if session_id == sid_a:
            return report_a
        return None

    with patch(
        "backend.api.services.comparison.get_coaching_report",
        side_effect=mock_get_report,
    ):
        resp = await client.get(f"/api/sessions/{sid_a}/compare/{sid_b}")

    assert resp.status_code == 200
    data = resp.json()
    assert data["skill_dimensions"] is None


@pytest.mark.asyncio
async def test_comparison_ai_verdict_is_none(client: AsyncClient) -> None:
    """AI verdict should be None (populated later by the narrative endpoint)."""
    sid_a = await _upload_session(client, filename="a.csv")
    sid_b = await _upload_session(client, filename="b.csv")

    resp = await client.get(f"/api/sessions/{sid_a}/compare/{sid_b}")
    assert resp.status_code == 200

    data = resp.json()
    assert data["ai_verdict"] is None
