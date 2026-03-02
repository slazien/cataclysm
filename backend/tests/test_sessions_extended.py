"""Extended tests for session management endpoints — covering uncovered lines.

Targets: lines 55, 68-69, 86-87, 90-91, 113, 125-128, 133, 146-161,
         174, 191-201, 204, 221-231, 234-239, 252-253, 260-281, 303,
         306-315, 342-346, 413-422, 432, 435-436, 438, 449-453,
         468-513, 527-633, 649, 673, 703-712, 723-734
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from backend.api.routers.sessions import (
    _auto_fetch_weather,
    _compute_ideal_lap_time,
    _compute_session_score,
    _equipment_fields,
    _normalize_score,
    _weather_fields,
)
from backend.api.services import equipment_store, session_store
from backend.tests.conftest import _TEST_USER, build_synthetic_csv

# ---------------------------------------------------------------------------
# Helper: build a minimal SessionData stub
# ---------------------------------------------------------------------------


def _make_session_data(
    session_id: str = "test-session",
    coaching_laps: list[int] | None = None,
    best_lap_time_s: float = 90.0,
    optimal_lap_time_s: float = 88.0,
    consistency_score: float | None = None,
    user_id: str | None = None,
) -> session_store.SessionData:
    """Return a minimal SessionData with mocked sub-objects."""
    snap = MagicMock()
    snap.best_lap_time_s = best_lap_time_s
    snap.optimal_lap_time_s = optimal_lap_time_s
    snap.n_laps = 3
    snap.n_clean_laps = 2
    snap.top3_avg_time_s = 91.0
    snap.avg_lap_time_s = 92.0
    snap.consistency_score = consistency_score
    snap.metadata.track_name = "Test Circuit"
    snap.metadata.session_date = "22/02/2026 10:00"

    parsed = MagicMock()
    import pandas as pd

    parsed.data = pd.DataFrame(
        {
            "lat": [33.53, 33.54, 33.55],
            "lon": [-86.62, -86.61, -86.60],
            "timestamp": [1700000000.0, 1700000060.0, 1700000120.0],
        }
    )
    parsed.metadata.session_date = "22/02/2026 10:00"

    processed = MagicMock()
    processed.lap_summaries = []
    processed.resampled_laps = {}
    processed.best_lap = 1

    sd = session_store.SessionData(
        session_id=session_id,
        snapshot=snap,
        parsed=parsed,
        processed=processed,
        corners=[],
        all_lap_corners={},
        coaching_laps=coaching_laps if coaching_laps is not None else [],
        user_id=user_id or _TEST_USER.user_id,
    )
    return sd


# ===========================================================================
# _auto_fetch_weather — lines 55, 68-69, 86-87, 90-91
# ===========================================================================


@pytest.mark.asyncio
async def test_auto_fetch_weather_empty_df() -> None:
    """_auto_fetch_weather returns early when DataFrame has no GPS columns (line 55)."""
    import pandas as pd

    sd = _make_session_data()
    sd.parsed.data = pd.DataFrame()  # empty — triggers early return at line 55

    # Should complete without error and leave weather as None
    await _auto_fetch_weather(sd)
    assert sd.weather is None


@pytest.mark.asyncio
async def test_auto_fetch_weather_no_lat_lon_columns() -> None:
    """_auto_fetch_weather returns early when DataFrame lacks lat/lon (line 55)."""
    import pandas as pd

    sd = _make_session_data()
    sd.parsed.data = pd.DataFrame({"speed": [10.0, 20.0]})

    await _auto_fetch_weather(sd)
    assert sd.weather is None


@pytest.mark.asyncio
async def test_auto_fetch_weather_bad_timestamp_falls_back_to_noon() -> None:
    """_auto_fetch_weather handles invalid timestamp gracefully (lines 68-69)."""
    import pandas as pd

    sd = _make_session_data()
    sd.parsed.data = pd.DataFrame(
        {
            "lat": [33.53, 33.54],
            "lon": [-86.62, -86.61],
            "timestamp": ["not-a-number", "also-bad"],  # invalid — triggers except at line 68-69
        }
    )
    sd.parsed.metadata.session_date = "22/02/2026 10:00"

    mock_weather = MagicMock()
    mock_weather.track_condition.value = "dry"
    mock_weather.ambient_temp_c = 20.0

    with patch(
        "cataclysm.weather_client.lookup_weather",
        new_callable=AsyncMock,
        return_value=mock_weather,
    ):
        await _auto_fetch_weather(sd)

    # Weather should be set (timestamp error was handled, continued to date parse)
    assert sd.weather is mock_weather


@pytest.mark.asyncio
async def test_auto_fetch_weather_unparseable_date_returns_early() -> None:
    """_auto_fetch_weather logs warning and returns early on bad date (lines 86-87, 90-91)."""
    import pandas as pd

    sd = _make_session_data()
    sd.parsed.data = pd.DataFrame({"lat": [33.53], "lon": [-86.62], "timestamp": [1700000000.0]})
    sd.parsed.metadata.session_date = "NOT A DATE AT ALL !@#"

    await _auto_fetch_weather(sd)
    assert sd.weather is None  # should return without setting weather


@pytest.mark.asyncio
async def test_auto_fetch_weather_success_stores_weather() -> None:
    """_auto_fetch_weather sets sd.weather when lookup succeeds."""
    import pandas as pd

    sd = _make_session_data()
    sd.parsed.data = pd.DataFrame(
        {"lat": [33.53, 33.54], "lon": [-86.62, -86.61], "timestamp": [1700000000.0, 1700000060.0]}
    )
    sd.parsed.metadata.session_date = "22/02/2026 10:00"

    mock_weather = MagicMock()
    mock_weather.track_condition.value = "dry"
    mock_weather.ambient_temp_c = 22.5

    with patch(
        "cataclysm.weather_client.lookup_weather",
        new_callable=AsyncMock,
        return_value=mock_weather,
    ):
        await _auto_fetch_weather(sd)

    assert sd.weather is mock_weather


@pytest.mark.asyncio
async def test_auto_fetch_weather_lookup_returns_none() -> None:
    """_auto_fetch_weather handles lookup returning None without setting weather."""
    import pandas as pd

    sd = _make_session_data()
    sd.parsed.data = pd.DataFrame({"lat": [33.53], "lon": [-86.62], "timestamp": [1700000000.0]})
    sd.parsed.metadata.session_date = "22/02/2026 10:00"

    with patch(
        "cataclysm.weather_client.lookup_weather",
        new_callable=AsyncMock,
        return_value=None,
    ):
        await _auto_fetch_weather(sd)

    assert sd.weather is None


# ===========================================================================
# _weather_fields — line 113
# ===========================================================================


def test_weather_fields_no_weather() -> None:
    """_weather_fields returns all-None tuple when sd.weather is None (line 113)."""
    sd = _make_session_data()
    sd.weather = None

    result = _weather_fields(sd)
    assert result == (None, None, None, None, None)


def test_weather_fields_with_weather() -> None:
    """_weather_fields extracts fields from a populated weather object."""
    from cataclysm.equipment import SessionConditions, TrackCondition

    sd = _make_session_data()
    sd.weather = SessionConditions(
        track_condition=TrackCondition.DRY,
        ambient_temp_c=20.0,
        humidity_pct=55.0,
        wind_speed_kmh=10.0,
        precipitation_mm=0.0,
    )

    temp, cond, hum, wind, precip = _weather_fields(sd)
    assert temp == 20.0
    assert cond == "dry"
    assert hum == 55.0
    assert wind == 10.0
    assert precip == 0.0


# ===========================================================================
# _equipment_fields — lines 125-128
# ===========================================================================


def test_equipment_fields_no_session_equipment() -> None:
    """_equipment_fields returns all-None when session has no equipment assigned."""
    result = _equipment_fields("no-equipment-session")
    assert result == (None, None, None)


def test_equipment_fields_profile_missing() -> None:
    """_equipment_fields returns all-None when profile_id lookup fails (line 125-127)."""
    from cataclysm.equipment import SessionEquipment

    se = SessionEquipment(session_id="test-sess", profile_id="nonexistent-profile")
    equipment_store._session_equipment["test-sess"] = se

    try:
        result = _equipment_fields("test-sess")
        assert result == (None, None, None)
    finally:
        equipment_store._session_equipment.pop("test-sess", None)


def test_equipment_fields_with_valid_profile() -> None:
    """_equipment_fields returns tire/compound/profile_name when fully assigned (line 128)."""
    from cataclysm.equipment import (
        EquipmentProfile,
        MuSource,
        SessionEquipment,
        TireCompoundCategory,
        TireSpec,
    )

    profile = EquipmentProfile(
        id="prof-1",
        name="Street Setup",
        tires=TireSpec(
            model="RE71R",
            compound_category=TireCompoundCategory.SUPER_200TW,
            size="245/40R18",
            treadwear_rating=200,
            estimated_mu=1.15,
            mu_source=MuSource.CURATED_TABLE,
            mu_confidence="high",
        ),
    )
    equipment_store._profiles["prof-1"] = profile

    se = SessionEquipment(session_id="equipped-sess", profile_id="prof-1")
    equipment_store._session_equipment["equipped-sess"] = se

    try:
        model, category, name = _equipment_fields("equipped-sess")
        assert model == "RE71R"
        assert category == "super_200tw"
        assert name == "Street Setup"
    finally:
        equipment_store._profiles.pop("prof-1", None)
        equipment_store._session_equipment.pop("equipped-sess", None)


# ===========================================================================
# _normalize_score — line 133
# ===========================================================================


def test_normalize_score_already_0_to_100() -> None:
    """_normalize_score leaves values > 1 unchanged."""
    assert _normalize_score(85.0) == 85.0


def test_normalize_score_0_to_1_range() -> None:
    """_normalize_score multiplies values <= 1 by 100."""
    assert _normalize_score(0.75) == pytest.approx(75.0)


def test_normalize_score_boundary_exactly_1() -> None:
    """_normalize_score multiplies exactly 1.0 by 100."""
    assert _normalize_score(1.0) == pytest.approx(100.0)


# ===========================================================================
# _compute_ideal_lap_time — lines 146-161
# ===========================================================================


@pytest.mark.asyncio
async def test_compute_ideal_lap_time_fewer_than_2_coaching_laps() -> None:
    """_compute_ideal_lap_time returns None when coaching_laps < 2 (line 145)."""
    sd = _make_session_data(coaching_laps=[1])  # only 1 lap
    result = await _compute_ideal_lap_time(sd)
    assert result is None


@pytest.mark.asyncio
async def test_compute_ideal_lap_time_zero_coaching_laps() -> None:
    """_compute_ideal_lap_time returns None for zero coaching laps."""
    sd = _make_session_data(coaching_laps=[])
    result = await _compute_ideal_lap_time(sd)
    assert result is None


@pytest.mark.asyncio
async def test_compute_ideal_lap_time_success() -> None:
    """_compute_ideal_lap_time integrates speed/distance to compute lap time (lines 148-158)."""
    sd = _make_session_data(coaching_laps=[1, 2])

    ideal_data = {
        "distance_m": [0.0, 100.0, 200.0, 300.0],
        "speed_mph": [60.0, 60.0, 60.0, 60.0],  # constant 60mph ≈ 26.82 m/s
    }
    with patch(
        "backend.api.services.pipeline.get_ideal_lap_data",
        new_callable=AsyncMock,
        return_value=ideal_data,
    ):
        result = await _compute_ideal_lap_time(sd)

    # 300m at 60mph ≈ 300 / 26.82 ≈ 11.19s
    assert result is not None
    assert result > 0


@pytest.mark.asyncio
async def test_compute_ideal_lap_time_single_distance_point() -> None:
    """_compute_ideal_lap_time returns None when distance_m has < 2 points (line 151)."""
    sd = _make_session_data(coaching_laps=[1, 2])

    ideal_data = {"distance_m": [0.0], "speed_mph": [60.0]}
    with patch(
        "backend.api.services.pipeline.get_ideal_lap_data",
        new_callable=AsyncMock,
        return_value=ideal_data,
    ):
        result = await _compute_ideal_lap_time(sd)

    assert result is None


@pytest.mark.asyncio
async def test_compute_ideal_lap_time_raises_key_error() -> None:
    """_compute_ideal_lap_time handles KeyError from get_ideal_lap_data (lines 159-161)."""
    sd = _make_session_data(coaching_laps=[1, 2])

    with patch(
        "backend.api.services.pipeline.get_ideal_lap_data",
        new_callable=AsyncMock,
        side_effect=KeyError("distance_m"),
    ):
        result = await _compute_ideal_lap_time(sd)

    assert result is None


@pytest.mark.asyncio
async def test_compute_ideal_lap_time_all_zero_speeds() -> None:
    """_compute_ideal_lap_time returns None when total integration yields 0 (line 158)."""
    sd = _make_session_data(coaching_laps=[1, 2])

    # All speeds are 0 — avg_mps == 0 so we skip all segments → total stays 0.0
    ideal_data = {"distance_m": [0.0, 100.0, 200.0], "speed_mph": [0.0, 0.0, 0.0]}
    with patch(
        "backend.api.services.pipeline.get_ideal_lap_data",
        new_callable=AsyncMock,
        return_value=ideal_data,
    ):
        result = await _compute_ideal_lap_time(sd)

    assert result is None


# ===========================================================================
# _compute_session_score — lines 174, 191-201, 204
# ===========================================================================


@pytest.mark.asyncio
async def test_compute_session_score_no_components_returns_none() -> None:
    """_compute_session_score returns None when no data is available (line 204)."""
    sd = _make_session_data(best_lap_time_s=0.0)  # best_lap_time_s=0 skips pace component
    sd.consistency = None

    with patch(
        "backend.api.routers.sessions.get_coaching_report",
        new_callable=AsyncMock,
        return_value=None,
    ):
        result = await _compute_session_score(sd)

    assert result is None


@pytest.mark.asyncio
async def test_compute_session_score_with_corner_grades(client: AsyncClient) -> None:
    """_compute_session_score includes corner grades from coaching report (lines 191-201)."""
    sd = _make_session_data(best_lap_time_s=90.0, optimal_lap_time_s=88.0, coaching_laps=[1, 2])

    mock_corner_grade = MagicMock()
    mock_corner_grade.braking = "A"
    mock_corner_grade.trail_braking = "B"
    mock_corner_grade.min_speed = "C"
    mock_corner_grade.throttle = "A"

    mock_report = MagicMock()
    mock_report.corner_grades = [mock_corner_grade]

    with (
        patch(
            "backend.api.routers.sessions.get_coaching_report",
            new_callable=AsyncMock,
            return_value=mock_report,
        ),
        patch(
            "backend.api.services.pipeline.get_ideal_lap_data",
            new_callable=AsyncMock,
            return_value={"distance_m": [0.0, 100.0], "speed_mph": [60.0, 60.0]},
        ),
    ):
        result = await _compute_session_score(sd)

    assert result is not None
    assert 0.0 <= result <= 100.0


@pytest.mark.asyncio
async def test_compute_session_score_consistency_only() -> None:
    """_compute_session_score with only consistency uses 100% consistency weight."""
    sd = _make_session_data(best_lap_time_s=0.0)  # pace skipped

    consistency = MagicMock()
    consistency.lap_consistency.consistency_score = 0.80  # 0-1 scale → normalized to 80
    sd.consistency = consistency

    with patch(
        "backend.api.routers.sessions.get_coaching_report",
        new_callable=AsyncMock,
        return_value=None,
    ):
        result = await _compute_session_score(sd)

    assert result is not None
    assert result == pytest.approx(80.0)


@pytest.mark.asyncio
async def test_compute_session_score_corner_grades_with_empty_grade() -> None:
    """_compute_session_score skips invalid grade letters (lines 196-199)."""
    sd = _make_session_data(best_lap_time_s=0.0)
    sd.consistency = None

    mock_corner_grade = MagicMock()
    mock_corner_grade.braking = ""  # empty — [:1] = "" not in grade_map, skipped
    mock_corner_grade.trail_braking = "Z"  # not in grade_map, skipped
    mock_corner_grade.min_speed = "B"  # valid → 80
    mock_corner_grade.throttle = ""

    mock_report = MagicMock()
    mock_report.corner_grades = [mock_corner_grade]

    with patch(
        "backend.api.routers.sessions.get_coaching_report",
        new_callable=AsyncMock,
        return_value=mock_report,
    ):
        result = await _compute_session_score(sd)

    # Only one valid grade "B"=80, so result should be 80
    assert result == pytest.approx(80.0)


# ===========================================================================
# upload_sessions — lines 221-231, 234-239, 252-253, 260-281
# ===========================================================================


@pytest.mark.asyncio
async def test_upload_file_with_no_name(client: AsyncClient) -> None:
    """POST /api/sessions/upload skips files whose filename is falsy (lines 234-235).

    FastAPI UploadFile.filename can be None or empty string; the router guards
    against both with ``if not f.filename``.  We test this by invoking the
    endpoint function directly with a mocked UploadFile that has filename=None.
    """
    from fastapi import UploadFile as _UploadFile

    nameless_file = MagicMock(spec=_UploadFile)
    nameless_file.filename = None  # triggers "if not f.filename" guard
    nameless_file.read = AsyncMock(return_value=b"some bytes")

    # Build a fully async-capable mock DB session
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=MagicMock()))
    )
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()

    with patch(
        "backend.api.routers.sessions.process_upload",
        new_callable=AsyncMock,
    ) as mock_process:
        from backend.api.config import Settings
        from backend.api.routers.sessions import upload_sessions

        result = await upload_sessions(
            files=[nameless_file],
            settings=MagicMock(spec=Settings),
            current_user=_TEST_USER,  # type: ignore[arg-type]
            db=mock_db,
        )

    assert result.session_ids == []
    assert "error" in result.message.lower()
    mock_process.assert_not_called()


@pytest.mark.asyncio
async def test_upload_auto_weather_called_on_upload(
    client: AsyncClient, synthetic_csv_bytes: bytes
) -> None:
    """POST /api/sessions/upload calls _auto_fetch_weather for new sessions (lines 249-253)."""
    with patch(
        "backend.api.routers.sessions._auto_fetch_weather",
        new_callable=AsyncMock,
        return_value=None,
    ) as mock_weather:
        response = await client.post(
            "/api/sessions/upload",
            files=[("files", ("test.csv", synthetic_csv_bytes, "text/csv"))],
        )

    assert response.status_code == 200
    assert len(response.json()["session_ids"]) == 1
    mock_weather.assert_called_once()


@pytest.mark.asyncio
async def test_upload_weather_fetch_exception_does_not_fail_upload(
    client: AsyncClient, synthetic_csv_bytes: bytes
) -> None:
    """POST /api/sessions/upload continues if _auto_fetch_weather raises (lines 252-253)."""
    with patch(
        "backend.api.routers.sessions._auto_fetch_weather",
        new_callable=AsyncMock,
        side_effect=ValueError("network down"),
    ):
        response = await client.post(
            "/api/sessions/upload",
            files=[("files", ("test.csv", synthetic_csv_bytes, "text/csv"))],
        )

    assert response.status_code == 200
    assert len(response.json()["session_ids"]) == 1  # upload succeeded despite weather error


@pytest.mark.asyncio
async def test_upload_csv_bytes_sqlalchemy_error_is_tolerated(
    client: AsyncClient, synthetic_csv_bytes: bytes
) -> None:
    """POST /api/sessions/upload continues when CSV bytes persist fails (lines 273-275)."""
    from sqlalchemy.exc import SQLAlchemyError

    with patch(
        "backend.api.routers.sessions.SessionFileModel",
        side_effect=SQLAlchemyError("disk full"),
    ):
        response = await client.post(
            "/api/sessions/upload",
            files=[("files", ("test.csv", synthetic_csv_bytes, "text/csv"))],
        )

    # Session metadata was already committed — should still succeed
    assert response.status_code == 200
    assert len(response.json()["session_ids"]) == 1


@pytest.mark.asyncio
async def test_upload_auto_coaching_exception_does_not_fail_upload(
    client: AsyncClient, synthetic_csv_bytes: bytes
) -> None:
    """POST /api/sessions/upload continues if auto-coaching raises (lines 279-281)."""
    with patch(
        "backend.api.routers.sessions.trigger_auto_coaching",
        new_callable=AsyncMock,
        side_effect=ValueError("model unavailable"),
    ):
        response = await client.post(
            "/api/sessions/upload",
            files=[("files", ("test.csv", synthetic_csv_bytes, "text/csv"))],
        )

    assert response.status_code == 200
    assert len(response.json()["session_ids"]) == 1


# ===========================================================================
# list_sessions — lines 303, 306-315, 342-346
# ===========================================================================


@pytest.mark.asyncio
async def test_list_sessions_db_only_fallback(
    client: AsyncClient, synthetic_csv_bytes: bytes
) -> None:
    """GET /api/sessions falls back to DB metadata when session not in memory (lines 342-346)."""
    # Upload to get a DB row, then evict from memory
    upload_resp = await client.post(
        "/api/sessions/upload",
        files=[("files", ("test.csv", synthetic_csv_bytes, "text/csv"))],
    )
    session_id = upload_resp.json()["session_ids"][0]

    # Remove from in-memory store to force DB fallback path
    session_store.delete_session(session_id)

    response = await client.get("/api/sessions")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    ids = [item["session_id"] for item in data["items"]]
    assert session_id in ids

    # Verify the DB-only item has expected fields
    item = next(i for i in data["items"] if i["session_id"] == session_id)
    assert item["track_name"] is not None


@pytest.mark.asyncio
async def test_list_sessions_db_fallback_with_weather_snapshot(
    client: AsyncClient, synthetic_csv_bytes: bytes
) -> None:
    """GET /api/sessions returns weather data from snapshot_json in DB-only mode (lines 342-346)."""
    from backend.api.db.models import Session as SessionModel
    from backend.tests.conftest import _test_session_factory

    # Upload a session, then manually inject weather into snapshot_json
    upload_resp = await client.post(
        "/api/sessions/upload",
        files=[("files", ("test.csv", synthetic_csv_bytes, "text/csv"))],
    )
    session_id = upload_resp.json()["session_ids"][0]

    # Inject weather and GPS quality into the DB snapshot_json
    from sqlalchemy import select as sa_select

    async with _test_session_factory() as db:
        result = await db.execute(
            sa_select(SessionModel).where(SessionModel.session_id == session_id)
        )
        row = result.scalar_one_or_none()
        assert row is not None
        snap = dict(row.snapshot_json or {})
        snap["weather"] = {
            "ambient_temp_c": 18.5,
            "track_condition": "dry",
            "humidity_pct": 60.0,
            "wind_speed_kmh": 5.0,
            "precipitation_mm": 0.0,
        }
        snap["gps_quality"] = {"overall_score": 0.95, "grade": "A", "is_usable": True}
        row.snapshot_json = snap
        await db.commit()

    # Remove from memory to force DB-only fallback
    session_store.delete_session(session_id)

    response = await client.get("/api/sessions")
    assert response.status_code == 200
    data = response.json()
    item = next(i for i in data["items"] if i["session_id"] == session_id)
    assert item["weather_temp_c"] == pytest.approx(18.5)
    assert item["weather_condition"] == "dry"
    assert item["gps_quality_score"] == pytest.approx(0.95)
    assert item["gps_quality_grade"] == "A"


@pytest.mark.asyncio
async def test_list_sessions_weather_backfilled_from_snapshot(
    client: AsyncClient, synthetic_csv_bytes: bytes
) -> None:
    """GET /api/sessions backfills weather from DB snapshot when sd.weather is None."""
    from backend.api.db.models import Session as SessionModel
    from backend.tests.conftest import _test_session_factory

    upload_resp = await client.post(
        "/api/sessions/upload",
        files=[("files", ("test.csv", synthetic_csv_bytes, "text/csv"))],
    )
    session_id = upload_resp.json()["session_ids"][0]

    # Inject weather into DB snapshot but ensure sd.weather is None in memory
    from sqlalchemy import select as sa_select

    async with _test_session_factory() as db:
        result = await db.execute(
            sa_select(SessionModel).where(SessionModel.session_id == session_id)
        )
        row = result.scalar_one_or_none()
        assert row is not None
        snap = dict(row.snapshot_json or {})
        snap["weather"] = {
            "ambient_temp_c": 25.0,
            "track_condition": "dry",
            "humidity_pct": 40.0,
            "wind_speed_kmh": 8.0,
            "precipitation_mm": 0.0,
        }
        row.snapshot_json = snap
        await db.commit()

    # Clear weather from in-memory session
    sd = session_store.get_session(session_id)
    assert sd is not None
    sd.weather = None

    response = await client.get("/api/sessions")
    assert response.status_code == 200
    data = response.json()
    item = next((i for i in data["items"] if i["session_id"] == session_id), None)
    assert item is not None
    # Weather should be restored from snapshot
    assert item["weather_temp_c"] == pytest.approx(25.0)


# ===========================================================================
# compare_sessions — lines 413-422
# ===========================================================================


@pytest.mark.asyncio
async def test_compare_sessions_first_not_found(client: AsyncClient) -> None:
    """GET /sessions/{id}/compare/{other} returns 404 when first session missing (line 414-415)."""
    response = await client.get("/api/sessions/nonexistent-a/compare/nonexistent-b")
    assert response.status_code == 404
    assert "nonexistent-a" in response.json()["detail"]


@pytest.mark.asyncio
async def test_compare_sessions_second_not_found(
    client: AsyncClient, synthetic_csv_bytes: bytes
) -> None:
    """GET /sessions/{id}/compare/{other} returns 404 when second session missing."""
    upload_resp = await client.post(
        "/api/sessions/upload",
        files=[("files", ("test.csv", synthetic_csv_bytes, "text/csv"))],
    )
    session_id = upload_resp.json()["session_ids"][0]

    response = await client.get(f"/api/sessions/{session_id}/compare/nonexistent-b")
    assert response.status_code == 404
    assert "nonexistent-b" in response.json()["detail"]


@pytest.mark.asyncio
async def test_compare_sessions_success(client: AsyncClient, synthetic_csv_bytes: bytes) -> None:
    """GET /sessions/{id}/compare/{other} returns ComparisonResult for two valid sessions."""
    # Upload two sessions (same CSV, different filenames → same session_id)
    resp_a = await client.post(
        "/api/sessions/upload",
        files=[("files", ("session_a.csv", synthetic_csv_bytes, "text/csv"))],
    )
    resp_b = await client.post(
        "/api/sessions/upload",
        files=[("files", ("session_b.csv", build_synthetic_csv(n_laps=3), "text/csv"))],
    )
    sid_a = resp_a.json()["session_ids"][0]
    sid_b = resp_b.json()["session_ids"][0]

    response = await client.get(f"/api/sessions/{sid_a}/compare/{sid_b}")
    assert response.status_code == 200
    data = response.json()
    assert "session_a_id" in data
    assert "session_b_id" in data
    assert "delta_s" in data
    assert isinstance(data["distance_m"], list)
    assert isinstance(data["corner_deltas"], list)


# ===========================================================================
# delete_all_sessions — lines 432, 435-436, 438
# ===========================================================================


@pytest.mark.asyncio
async def test_delete_all_sessions_returns_count(
    client: AsyncClient, synthetic_csv_bytes: bytes
) -> None:
    """DELETE /api/sessions/all/clear returns deletion count message (lines 432-438)."""
    await client.post(
        "/api/sessions/upload",
        files=[("files", ("a.csv", synthetic_csv_bytes, "text/csv"))],
    )
    await client.post(
        "/api/sessions/upload",
        files=[("files", ("b.csv", synthetic_csv_bytes, "text/csv"))],
    )

    response = await client.delete("/api/sessions/all/clear")
    assert response.status_code == 200
    msg = response.json()["message"]
    assert "Deleted" in msg

    # Confirm sessions are gone from memory and list
    list_resp = await client.get("/api/sessions")
    assert list_resp.json()["total"] == 0


@pytest.mark.asyncio
async def test_delete_all_sessions_empty_store(client: AsyncClient) -> None:
    """DELETE /api/sessions/all/clear succeeds on empty store (lines 432-438)."""
    response = await client.delete("/api/sessions/all/clear")
    assert response.status_code == 200
    assert response.json()["message"] == "Deleted 0 session(s)"


# ===========================================================================
# delete_session — lines 449-453
# ===========================================================================


@pytest.mark.asyncio
async def test_delete_session_success_message(
    client: AsyncClient, synthetic_csv_bytes: bytes
) -> None:
    """DELETE /api/sessions/{id} returns confirmation message (lines 449-453)."""
    upload_resp = await client.post(
        "/api/sessions/upload",
        files=[("files", ("test.csv", synthetic_csv_bytes, "text/csv"))],
    )
    session_id = upload_resp.json()["session_ids"][0]

    response = await client.delete(f"/api/sessions/{session_id}")
    assert response.status_code == 200
    assert session_id in response.json()["message"]


# ===========================================================================
# get_session_weather — lines 468-513
# ===========================================================================


@pytest.mark.asyncio
async def test_get_weather_session_not_found(client: AsyncClient) -> None:
    """GET /api/sessions/{id}/weather returns 404 for unknown session (line 469-470)."""
    response = await client.get("/api/sessions/unknown-sess/weather")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_weather_returns_cached_weather(
    client: AsyncClient, synthetic_csv_bytes: bytes
) -> None:
    """GET /api/sessions/{id}/weather returns cached weather immediately (lines 473-488)."""
    from cataclysm.equipment import SessionConditions, TrackCondition

    upload_resp = await client.post(
        "/api/sessions/upload",
        files=[("files", ("test.csv", synthetic_csv_bytes, "text/csv"))],
    )
    session_id = upload_resp.json()["session_ids"][0]

    # Manually set weather on the in-memory session
    sd = session_store.get_session(session_id)
    assert sd is not None
    sd.weather = SessionConditions(
        track_condition=TrackCondition.DRY,
        ambient_temp_c=21.0,
        humidity_pct=55.0,
        wind_speed_kmh=12.0,
        wind_direction_deg=180.0,
        precipitation_mm=0.0,
        weather_source="open-meteo",
    )

    response = await client.get(f"/api/sessions/{session_id}/weather")
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == session_id
    assert data["weather"]["track_condition"] == "dry"
    assert data["weather"]["ambient_temp_c"] == pytest.approx(21.0)
    assert data["weather"]["humidity_pct"] == pytest.approx(55.0)
    assert data["weather"]["wind_speed_kmh"] == pytest.approx(12.0)
    assert data["weather"]["weather_source"] == "open-meteo"


@pytest.mark.asyncio
async def test_get_weather_live_fetch_on_miss(
    client: AsyncClient, synthetic_csv_bytes: bytes
) -> None:
    """GET /api/sessions/{id}/weather triggers live fetch when weather is None (lines 490-511)."""
    from cataclysm.equipment import SessionConditions, TrackCondition

    upload_resp = await client.post(
        "/api/sessions/upload",
        files=[("files", ("test.csv", synthetic_csv_bytes, "text/csv"))],
    )
    session_id = upload_resp.json()["session_ids"][0]

    # Ensure no cached weather
    sd = session_store.get_session(session_id)
    assert sd is not None
    sd.weather = None

    fetched_weather = SessionConditions(
        track_condition=TrackCondition.DRY,
        ambient_temp_c=19.0,
        humidity_pct=50.0,
        wind_speed_kmh=7.0,
        wind_direction_deg=270.0,
        precipitation_mm=0.0,
        weather_source="open-meteo",
    )

    async def _set_weather(sd_arg: object) -> None:
        sd_arg.weather = fetched_weather  # type: ignore[attr-defined]

    with patch(
        "backend.api.routers.sessions._auto_fetch_weather",
        new_callable=AsyncMock,
        side_effect=_set_weather,
    ):
        response = await client.get(f"/api/sessions/{session_id}/weather")

    assert response.status_code == 200
    data = response.json()
    assert data["weather"]["ambient_temp_c"] == pytest.approx(19.0)


@pytest.mark.asyncio
async def test_get_weather_returns_null_when_fetch_fails(
    client: AsyncClient, synthetic_csv_bytes: bytes
) -> None:
    """GET /api/sessions/{id}/weather returns {weather: null} when fetch fails (line 513)."""
    upload_resp = await client.post(
        "/api/sessions/upload",
        files=[("files", ("test.csv", synthetic_csv_bytes, "text/csv"))],
    )
    session_id = upload_resp.json()["session_ids"][0]

    sd = session_store.get_session(session_id)
    assert sd is not None
    sd.weather = None

    with patch(
        "backend.api.routers.sessions._auto_fetch_weather",
        new_callable=AsyncMock,
        return_value=None,  # does not set sd.weather
    ):
        response = await client.get(f"/api/sessions/{session_id}/weather")

    assert response.status_code == 200
    data = response.json()
    assert data["weather"] is None


@pytest.mark.asyncio
async def test_get_weather_fetch_exception_returns_null(
    client: AsyncClient, synthetic_csv_bytes: bytes
) -> None:
    """GET /api/sessions/{id}/weather handles OSError in live fetch gracefully (lines 493-494)."""
    upload_resp = await client.post(
        "/api/sessions/upload",
        files=[("files", ("test.csv", synthetic_csv_bytes, "text/csv"))],
    )
    session_id = upload_resp.json()["session_ids"][0]

    sd = session_store.get_session(session_id)
    assert sd is not None
    sd.weather = None

    with patch(
        "backend.api.routers.sessions._auto_fetch_weather",
        new_callable=AsyncMock,
        side_effect=OSError("network timeout"),
    ):
        response = await client.get(f"/api/sessions/{session_id}/weather")

    assert response.status_code == 200
    assert response.json()["weather"] is None


@pytest.mark.asyncio
async def test_get_weather_track_condition_string_fallback(
    client: AsyncClient, synthetic_csv_bytes: bytes
) -> None:
    """GET /api/sessions/{id}/weather uses str() when track_condition has no .value attr."""
    upload_resp = await client.post(
        "/api/sessions/upload",
        files=[("files", ("test.csv", synthetic_csv_bytes, "text/csv"))],
    )
    session_id = upload_resp.json()["session_ids"][0]

    sd = session_store.get_session(session_id)
    assert sd is not None

    # Create a mock weather object where track_condition has no .value (plain string)
    mock_weather = MagicMock(spec=[])  # no attributes by default
    mock_weather.track_condition = "wet"  # plain string, not enum
    mock_weather.ambient_temp_c = 10.0
    mock_weather.humidity_pct = 90.0
    mock_weather.wind_speed_kmh = 20.0
    mock_weather.wind_direction_deg = 45.0
    mock_weather.precipitation_mm = 5.0
    mock_weather.weather_source = "manual"
    sd.weather = mock_weather

    response = await client.get(f"/api/sessions/{session_id}/weather")
    assert response.status_code == 200
    data = response.json()
    assert data["weather"]["track_condition"] == "wet"


# ===========================================================================
# backfill_weather — lines 527-633
# ===========================================================================


@pytest.mark.asyncio
async def test_backfill_weather_skips_sessions_with_existing_weather(
    client: AsyncClient, synthetic_csv_bytes: bytes
) -> None:
    """POST /api/sessions/backfill-weather skips sessions that already have weather."""
    from sqlalchemy import select as sa_select

    from backend.api.db.models import Session as SessionModel
    from backend.tests.conftest import _test_session_factory

    upload_resp = await client.post(
        "/api/sessions/upload",
        files=[("files", ("test.csv", synthetic_csv_bytes, "text/csv"))],
    )
    session_id = upload_resp.json()["session_ids"][0]

    # Inject existing weather into snapshot_json
    async with _test_session_factory() as db:
        result = await db.execute(
            sa_select(SessionModel).where(SessionModel.session_id == session_id)
        )
        row = result.scalar_one_or_none()
        assert row is not None
        snap = dict(row.snapshot_json or {})
        snap["weather"] = {"track_condition": "dry", "ambient_temp_c": 20.0}
        row.snapshot_json = snap
        await db.commit()

    response = await client.post("/api/sessions/backfill-weather")
    assert response.status_code == 200
    data = response.json()
    assert data["skipped"] >= 1
    assert data["backfilled"] == 0


@pytest.mark.asyncio
async def test_backfill_weather_with_centroid_and_date(
    client: AsyncClient, synthetic_csv_bytes: bytes
) -> None:
    """POST /api/sessions/backfill-weather uses gps_centroid + date for lookup (lines 576-630)."""
    from datetime import UTC, datetime

    from cataclysm.equipment import SessionConditions, TrackCondition
    from sqlalchemy import select as sa_select

    from backend.api.db.models import Session as SessionModel
    from backend.tests.conftest import _test_session_factory

    upload_resp = await client.post(
        "/api/sessions/upload",
        files=[("files", ("test.csv", synthetic_csv_bytes, "text/csv"))],
    )
    session_id = upload_resp.json()["session_ids"][0]

    # Ensure no existing weather in snapshot
    async with _test_session_factory() as db:
        result = await db.execute(
            sa_select(SessionModel).where(SessionModel.session_id == session_id)
        )
        row = result.scalar_one_or_none()
        assert row is not None
        snap = dict(row.snapshot_json or {})
        snap.pop("weather", None)
        snap["gps_centroid"] = {"lat": 33.53, "lon": -86.62}
        row.snapshot_json = snap
        row.session_date = datetime(2026, 2, 22, 10, 0, tzinfo=UTC)
        await db.commit()

    # Clear in-memory weather
    sd = session_store.get_session(session_id)
    if sd is not None:
        sd.weather = None

    mock_weather = SessionConditions(
        track_condition=TrackCondition.DRY,
        ambient_temp_c=22.0,
        humidity_pct=50.0,
    )

    with patch(
        "cataclysm.weather_client.lookup_weather",
        new_callable=AsyncMock,
        return_value=mock_weather,
    ):
        response = await client.post("/api/sessions/backfill-weather")

    assert response.status_code == 200
    data = response.json()
    assert data["backfilled"] >= 1
    assert data["failed"] == 0


@pytest.mark.asyncio
async def test_backfill_weather_lookup_returns_none_increments_failed(
    client: AsyncClient, synthetic_csv_bytes: bytes
) -> None:
    """POST /api/sessions/backfill-weather increments failed when lookup returns None."""
    from datetime import UTC, datetime

    from sqlalchemy import select as sa_select

    from backend.api.db.models import Session as SessionModel
    from backend.tests.conftest import _test_session_factory

    upload_resp = await client.post(
        "/api/sessions/upload",
        files=[("files", ("test.csv", synthetic_csv_bytes, "text/csv"))],
    )
    session_id = upload_resp.json()["session_ids"][0]

    async with _test_session_factory() as db:
        result = await db.execute(
            sa_select(SessionModel).where(SessionModel.session_id == session_id)
        )
        row = result.scalar_one_or_none()
        assert row is not None
        snap = dict(row.snapshot_json or {})
        snap.pop("weather", None)
        snap["gps_centroid"] = {"lat": 33.53, "lon": -86.62}
        row.snapshot_json = snap
        row.session_date = datetime(2026, 2, 22, 10, 0, tzinfo=UTC)
        await db.commit()

    with patch(
        "cataclysm.weather_client.lookup_weather",
        new_callable=AsyncMock,
        return_value=None,
    ):
        response = await client.post("/api/sessions/backfill-weather")

    assert response.status_code == 200
    data = response.json()
    assert data["failed"] >= 1


@pytest.mark.asyncio
async def test_backfill_weather_skips_missing_centroid_with_no_memory(
    client: AsyncClient, synthetic_csv_bytes: bytes
) -> None:
    """POST /api/sessions/backfill-weather skips when no centroid in DB and not in memory."""
    from sqlalchemy import select as sa_select

    from backend.api.db.models import Session as SessionModel
    from backend.tests.conftest import _test_session_factory

    upload_resp = await client.post(
        "/api/sessions/upload",
        files=[("files", ("test.csv", synthetic_csv_bytes, "text/csv"))],
    )
    session_id = upload_resp.json()["session_ids"][0]

    async with _test_session_factory() as db:
        result = await db.execute(
            sa_select(SessionModel).where(SessionModel.session_id == session_id)
        )
        row = result.scalar_one_or_none()
        assert row is not None
        # No centroid, no weather in snapshot
        row.snapshot_json = {}
        await db.commit()

    # Remove from memory so there is no in-memory fallback
    session_store.delete_session(session_id)

    response = await client.post("/api/sessions/backfill-weather")
    assert response.status_code == 200
    data = response.json()
    assert data["skipped"] >= 1


@pytest.mark.asyncio
async def test_backfill_weather_via_memory_fallback(
    client: AsyncClient, synthetic_csv_bytes: bytes
) -> None:
    """POST /api/sessions/backfill-weather falls back to in-memory session when no centroid."""
    from cataclysm.equipment import SessionConditions, TrackCondition
    from sqlalchemy import select as sa_select

    from backend.api.db.models import Session as SessionModel
    from backend.tests.conftest import _test_session_factory

    upload_resp = await client.post(
        "/api/sessions/upload",
        files=[("files", ("test.csv", synthetic_csv_bytes, "text/csv"))],
    )
    session_id = upload_resp.json()["session_ids"][0]

    # Remove centroid from DB so memory fallback is triggered
    async with _test_session_factory() as db:
        result = await db.execute(
            sa_select(SessionModel).where(SessionModel.session_id == session_id)
        )
        row = result.scalar_one_or_none()
        assert row is not None
        snap = dict(row.snapshot_json or {})
        snap.pop("gps_centroid", None)
        snap.pop("weather", None)
        row.snapshot_json = snap
        await db.commit()

    # Clear weather from the in-memory session
    sd = session_store.get_session(session_id)
    assert sd is not None
    sd.weather = None

    mock_weather = SessionConditions(
        track_condition=TrackCondition.DRY,
        ambient_temp_c=20.0,
    )

    async def _set_weather_side_effect(sd_arg: object) -> None:
        sd_arg.weather = mock_weather  # type: ignore[attr-defined]

    with patch(
        "backend.api.routers.sessions._auto_fetch_weather",
        new_callable=AsyncMock,
        side_effect=_set_weather_side_effect,
    ):
        response = await client.post("/api/sessions/backfill-weather")

    assert response.status_code == 200
    data = response.json()
    # Session was backfilled via memory fallback
    assert data["backfilled"] >= 1


@pytest.mark.asyncio
async def test_backfill_weather_skips_null_lat_lon(
    client: AsyncClient, synthetic_csv_bytes: bytes
) -> None:
    """POST /api/sessions/backfill-weather skips when centroid lat/lon are None (lines 578-580)."""
    from sqlalchemy import select as sa_select

    from backend.api.db.models import Session as SessionModel
    from backend.tests.conftest import _test_session_factory

    upload_resp = await client.post(
        "/api/sessions/upload",
        files=[("files", ("test.csv", synthetic_csv_bytes, "text/csv"))],
    )
    session_id = upload_resp.json()["session_ids"][0]

    async with _test_session_factory() as db:
        result = await db.execute(
            sa_select(SessionModel).where(SessionModel.session_id == session_id)
        )
        row = result.scalar_one_or_none()
        assert row is not None
        snap = dict(row.snapshot_json or {})
        snap.pop("weather", None)
        snap["gps_centroid"] = {"lat": None, "lon": None}  # null coords
        row.snapshot_json = snap
        await db.commit()

    response = await client.post("/api/sessions/backfill-weather")
    assert response.status_code == 200
    data = response.json()
    assert data["skipped"] >= 1


@pytest.mark.asyncio
async def test_backfill_weather_no_session_date_skips(client: AsyncClient) -> None:
    """POST /api/sessions/backfill-weather skips sessions with no session_date (lines 587-589).

    Uses a mock DB row to avoid SQLite NOT NULL constraint on session_date.
    """
    mock_row = MagicMock()
    mock_row.session_id = "no-date-session"
    mock_row.session_date = None  # triggers skip at lines 587-589
    mock_row.snapshot_json = {"gps_centroid": {"lat": 33.53, "lon": -86.62}}  # has centroid

    with patch(
        "backend.api.routers.sessions.list_sessions_for_user",
        new_callable=AsyncMock,
        return_value=[mock_row],
    ):
        response = await client.post("/api/sessions/backfill-weather")

    assert response.status_code == 200
    data = response.json()
    assert data["skipped"] >= 1
    assert data["total"] == 1


@pytest.mark.asyncio
async def test_backfill_weather_returns_summary_totals(
    client: AsyncClient, synthetic_csv_bytes: bytes
) -> None:
    """POST /api/sessions/backfill-weather response includes backfilled/skipped/failed/total."""
    response = await client.post("/api/sessions/backfill-weather")
    assert response.status_code == 200
    data = response.json()
    assert "backfilled" in data
    assert "skipped" in data
    assert "failed" in data
    assert "total" in data
    assert data["total"] == data["backfilled"] + data["skipped"] + data["failed"]


# ===========================================================================
# get_lap_summaries — line 649
# ===========================================================================


@pytest.mark.asyncio
async def test_get_laps_session_not_found(client: AsyncClient) -> None:
    """GET /api/sessions/{id}/laps returns 404 for unknown session (line 649)."""
    response = await client.get("/api/sessions/unknown-sess/laps")
    assert response.status_code == 404
    assert "unknown-sess" in response.json()["detail"]


# ===========================================================================
# get_lap_data — line 673
# ===========================================================================


@pytest.mark.asyncio
async def test_get_lap_data_session_not_found(client: AsyncClient) -> None:
    """GET /api/sessions/{id}/laps/{n}/data returns 404 for unknown session (line 673)."""
    response = await client.get("/api/sessions/unknown-sess/laps/1/data")
    assert response.status_code == 404


# ===========================================================================
# get_lap_tags — lines 703-712
# ===========================================================================


@pytest.mark.asyncio
async def test_get_lap_tags_session_not_found(client: AsyncClient) -> None:
    """GET /api/sessions/{id}/laps/{n}/tags returns 404 for unknown session (lines 703-705)."""
    response = await client.get("/api/sessions/unknown-sess/laps/1/tags")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_lap_tags_lap_not_found(client: AsyncClient, synthetic_csv_bytes: bytes) -> None:
    """GET /api/sessions/{id}/laps/{n}/tags returns 404 for unknown lap (lines 706-710)."""
    upload_resp = await client.post(
        "/api/sessions/upload",
        files=[("files", ("test.csv", synthetic_csv_bytes, "text/csv"))],
    )
    session_id = upload_resp.json()["session_ids"][0]

    response = await client.get(f"/api/sessions/{session_id}/laps/9999/tags")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_lap_tags_success(client: AsyncClient, synthetic_csv_bytes: bytes) -> None:
    """GET /api/sessions/{id}/laps/{n}/tags returns tags for a valid lap (lines 703-712)."""
    upload_resp = await client.post(
        "/api/sessions/upload",
        files=[("files", ("test.csv", synthetic_csv_bytes, "text/csv"))],
    )
    session_id = upload_resp.json()["session_ids"][0]

    laps_resp = await client.get(f"/api/sessions/{session_id}/laps")
    first_lap = laps_resp.json()[0]["lap_number"]

    response = await client.get(f"/api/sessions/{session_id}/laps/{first_lap}/tags")
    assert response.status_code == 200
    data = response.json()
    assert data["lap_number"] == first_lap
    assert isinstance(data["tags"], list)


# ===========================================================================
# set_lap_tags — lines 723-734
# ===========================================================================


@pytest.mark.asyncio
async def test_set_lap_tags_session_not_found(client: AsyncClient) -> None:
    """PUT /api/sessions/{id}/laps/{n}/tags returns 404 for unknown session (lines 723-725)."""
    response = await client.put(
        "/api/sessions/unknown-sess/laps/1/tags",
        json=["outlaw", "pb"],
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_set_lap_tags_lap_not_found(client: AsyncClient, synthetic_csv_bytes: bytes) -> None:
    """PUT /api/sessions/{id}/laps/{n}/tags returns 404 for unknown lap (lines 726-730)."""
    upload_resp = await client.post(
        "/api/sessions/upload",
        files=[("files", ("test.csv", synthetic_csv_bytes, "text/csv"))],
    )
    session_id = upload_resp.json()["session_ids"][0]

    response = await client.put(
        f"/api/sessions/{session_id}/laps/9999/tags",
        json=["pb"],
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_set_lap_tags_success(client: AsyncClient, synthetic_csv_bytes: bytes) -> None:
    """PUT /api/sessions/{id}/laps/{n}/tags sets and returns tags (lines 723-734)."""
    upload_resp = await client.post(
        "/api/sessions/upload",
        files=[("files", ("test.csv", synthetic_csv_bytes, "text/csv"))],
    )
    session_id = upload_resp.json()["session_ids"][0]

    laps_resp = await client.get(f"/api/sessions/{session_id}/laps")
    first_lap = laps_resp.json()[0]["lap_number"]

    tags = ["pb", "outlaw"]
    response = await client.put(
        f"/api/sessions/{session_id}/laps/{first_lap}/tags",
        json=tags,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["lap_number"] == first_lap
    assert sorted(data["tags"]) == sorted(tags)


@pytest.mark.asyncio
async def test_set_lap_tags_replaces_existing(
    client: AsyncClient, synthetic_csv_bytes: bytes
) -> None:
    """PUT /api/sessions/{id}/laps/{n}/tags replaces previous tags on second call (line 733)."""
    upload_resp = await client.post(
        "/api/sessions/upload",
        files=[("files", ("test.csv", synthetic_csv_bytes, "text/csv"))],
    )
    session_id = upload_resp.json()["session_ids"][0]

    laps_resp = await client.get(f"/api/sessions/{session_id}/laps")
    first_lap = laps_resp.json()[0]["lap_number"]

    # First set
    await client.put(
        f"/api/sessions/{session_id}/laps/{first_lap}/tags",
        json=["old-tag"],
    )

    # Second set — should replace
    response = await client.put(
        f"/api/sessions/{session_id}/laps/{first_lap}/tags",
        json=["new-tag"],
    )
    assert response.status_code == 200
    assert response.json()["tags"] == ["new-tag"]

    # Verify GET also reflects new tags
    get_resp = await client.get(f"/api/sessions/{session_id}/laps/{first_lap}/tags")
    assert get_resp.json()["tags"] == ["new-tag"]


@pytest.mark.asyncio
async def test_set_lap_tags_empty_list(client: AsyncClient, synthetic_csv_bytes: bytes) -> None:
    """PUT /api/sessions/{id}/laps/{n}/tags with empty list clears all tags."""
    upload_resp = await client.post(
        "/api/sessions/upload",
        files=[("files", ("test.csv", synthetic_csv_bytes, "text/csv"))],
    )
    session_id = upload_resp.json()["session_ids"][0]

    laps_resp = await client.get(f"/api/sessions/{session_id}/laps")
    first_lap = laps_resp.json()[0]["lap_number"]

    # Set some tags first
    await client.put(
        f"/api/sessions/{session_id}/laps/{first_lap}/tags",
        json=["some-tag"],
    )

    # Clear all tags
    response = await client.put(
        f"/api/sessions/{session_id}/laps/{first_lap}/tags",
        json=[],
    )
    assert response.status_code == 200
    assert response.json()["tags"] == []


# ===========================================================================
# Direct-function tests for upload_sessions inner paths (lines 237-281)
# These bypass the HTTP layer to avoid SQLite constraints and fixture
# interference, ensuring coverage of the CSV-bytes-persist and coaching paths.
# ===========================================================================


@pytest.mark.asyncio
async def test_upload_inner_csv_bytes_persist_path() -> None:
    """upload_sessions inner try block — CSV bytes merge + coaching trigger (lines 260-281).

    Invokes the endpoint function directly with async mocks to exercise the
    session-persist, CSV-bytes-persist, and auto-coaching branches.
    """

    from fastapi import UploadFile as _UploadFile

    from backend.api.config import Settings
    from backend.api.routers.sessions import upload_sessions

    csv_bytes = build_synthetic_csv(n_laps=2)

    named_file = MagicMock(spec=_UploadFile)
    named_file.filename = "direct_test.csv"
    named_file.read = AsyncMock(return_value=csv_bytes)

    # Mock db with all needed async ops
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    )
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.merge = AsyncMock()
    mock_db.rollback = AsyncMock()

    mock_settings = MagicMock(spec=Settings)

    with (
        patch(
            "backend.api.routers.sessions.ensure_user_exists",
            new_callable=AsyncMock,
        ),
        patch(
            "backend.api.routers.sessions.store_session_db",
            new_callable=AsyncMock,
        ),
        patch(
            "backend.api.routers.sessions.trigger_auto_coaching",
            new_callable=AsyncMock,
        ) as mock_coaching,
        patch(
            "backend.api.routers.sessions._auto_fetch_weather",
            new_callable=AsyncMock,
        ),
    ):
        result = await upload_sessions(
            files=[named_file],
            settings=mock_settings,
            current_user=_TEST_USER,  # type: ignore[arg-type]
            db=mock_db,
        )

    assert len(result.session_ids) == 1
    # Confirm coaching was triggered
    mock_coaching.assert_called_once()


@pytest.mark.asyncio
async def test_upload_inner_csv_bytes_sqlalchemy_error_path() -> None:
    """upload_sessions SQLAlchemy error on CSV bytes merge triggers rollback (lines 273-275)."""
    from fastapi import UploadFile as _UploadFile
    from sqlalchemy.exc import SQLAlchemyError

    from backend.api.config import Settings
    from backend.api.routers.sessions import upload_sessions

    csv_bytes = build_synthetic_csv(n_laps=2)

    named_file = MagicMock(spec=_UploadFile)
    named_file.filename = "direct_test2.csv"
    named_file.read = AsyncMock(return_value=csv_bytes)

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    )
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.merge = AsyncMock(side_effect=SQLAlchemyError("disk full"))
    mock_db.rollback = AsyncMock()

    mock_settings = MagicMock(spec=Settings)

    with (
        patch("backend.api.routers.sessions.ensure_user_exists", new_callable=AsyncMock),
        patch("backend.api.routers.sessions.store_session_db", new_callable=AsyncMock),
        patch("backend.api.routers.sessions.trigger_auto_coaching", new_callable=AsyncMock),
        patch("backend.api.routers.sessions._auto_fetch_weather", new_callable=AsyncMock),
    ):
        result = await upload_sessions(
            files=[named_file],
            settings=mock_settings,
            current_user=_TEST_USER,  # type: ignore[arg-type]
            db=mock_db,
        )

    # Session should still be returned despite CSV bytes failure
    assert len(result.session_ids) == 1
    mock_db.rollback.assert_called_once()


@pytest.mark.asyncio
async def test_upload_inner_coaching_value_error_path() -> None:
    """upload_sessions handles ValueError from trigger_auto_coaching (lines 279-281)."""
    from fastapi import UploadFile as _UploadFile

    from backend.api.config import Settings
    from backend.api.routers.sessions import upload_sessions

    csv_bytes = build_synthetic_csv(n_laps=2)

    named_file = MagicMock(spec=_UploadFile)
    named_file.filename = "coaching_err.csv"
    named_file.read = AsyncMock(return_value=csv_bytes)

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    )
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.merge = AsyncMock()
    mock_db.rollback = AsyncMock()

    with (
        patch("backend.api.routers.sessions.ensure_user_exists", new_callable=AsyncMock),
        patch("backend.api.routers.sessions.store_session_db", new_callable=AsyncMock),
        patch(
            "backend.api.routers.sessions.trigger_auto_coaching",
            new_callable=AsyncMock,
            side_effect=ValueError("model error"),
        ),
        patch("backend.api.routers.sessions._auto_fetch_weather", new_callable=AsyncMock),
    ):
        result = await upload_sessions(
            files=[named_file],
            settings=MagicMock(spec=Settings),
            current_user=_TEST_USER,  # type: ignore[arg-type]
            db=mock_db,
        )

    # Upload still succeeds despite coaching error
    assert len(result.session_ids) == 1


# ===========================================================================
# Direct-function tests for backfill_weather success path (lines 591-630)
# These bypass the HTTP layer to guarantee the lookup_weather branch runs.
# ===========================================================================


@pytest.mark.asyncio
async def test_backfill_weather_direct_success_path() -> None:
    """backfill_weather: centroid + date → lookup succeeds → snapshot updated (lines 591-630)."""
    from datetime import UTC, datetime

    from cataclysm.equipment import SessionConditions, TrackCondition

    from backend.api.routers.sessions import backfill_weather

    mock_weather = SessionConditions(
        track_condition=TrackCondition.DRY,
        ambient_temp_c=22.0,
        track_temp_c=35.0,
        humidity_pct=50.0,
        wind_speed_kmh=8.0,
        wind_direction_deg=180.0,
        precipitation_mm=0.0,
        weather_source="open-meteo",
    )

    mock_row = MagicMock()
    mock_row.session_id = "backfill-sess-1"
    mock_row.session_date = datetime(2026, 2, 22, 10, 0, tzinfo=UTC)
    mock_row.snapshot_json = {"gps_centroid": {"lat": 33.53, "lon": -86.62}}

    mock_db = AsyncMock()
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()

    mock_user = MagicMock()
    mock_user.user_id = _TEST_USER.user_id

    with (
        patch(
            "backend.api.routers.sessions.list_sessions_for_user",
            new_callable=AsyncMock,
            return_value=[mock_row],
        ),
        patch(
            "cataclysm.weather_client.lookup_weather",
            new_callable=AsyncMock,
            return_value=mock_weather,
        ),
    ):
        result = await backfill_weather(current_user=mock_user, db=mock_db)

    assert result["backfilled"] == 1
    assert result["skipped"] == 0
    assert result["failed"] == 0
    assert result["total"] == 1
    mock_db.flush.assert_called_once()


@pytest.mark.asyncio
async def test_backfill_weather_direct_lookup_returns_none() -> None:
    """backfill_weather: lookup returns None → failed counter incremented (lines 593-595)."""
    from datetime import UTC, datetime

    from backend.api.routers.sessions import backfill_weather

    mock_row = MagicMock()
    mock_row.session_id = "backfill-sess-2"
    mock_row.session_date = datetime(2026, 2, 22, 10, 0, tzinfo=UTC)
    mock_row.snapshot_json = {"gps_centroid": {"lat": 33.53, "lon": -86.62}}

    mock_db = AsyncMock()
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()

    mock_user = MagicMock()
    mock_user.user_id = _TEST_USER.user_id

    with (
        patch(
            "backend.api.routers.sessions.list_sessions_for_user",
            new_callable=AsyncMock,
            return_value=[mock_row],
        ),
        patch(
            "cataclysm.weather_client.lookup_weather",
            new_callable=AsyncMock,
            return_value=None,
        ),
    ):
        result = await backfill_weather(current_user=mock_user, db=mock_db)

    assert result["failed"] == 1
    assert result["backfilled"] == 0


@pytest.mark.asyncio
async def test_backfill_weather_direct_lookup_exception() -> None:
    """backfill_weather: OSError in lookup → failed counter incremented (lines 628-630)."""
    from datetime import UTC, datetime

    from backend.api.routers.sessions import backfill_weather

    mock_row = MagicMock()
    mock_row.session_id = "backfill-sess-3"
    mock_row.session_date = datetime(2026, 2, 22, 10, 0, tzinfo=UTC)
    mock_row.snapshot_json = {"gps_centroid": {"lat": 33.53, "lon": -86.62}}

    mock_db = AsyncMock()
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()

    mock_user = MagicMock()
    mock_user.user_id = _TEST_USER.user_id

    with (
        patch(
            "backend.api.routers.sessions.list_sessions_for_user",
            new_callable=AsyncMock,
            return_value=[mock_row],
        ),
        patch(
            "cataclysm.weather_client.lookup_weather",
            new_callable=AsyncMock,
            side_effect=OSError("network timeout"),
        ),
    ):
        result = await backfill_weather(current_user=mock_user, db=mock_db)

    assert result["failed"] == 1
    assert result["backfilled"] == 0


@pytest.mark.asyncio
async def test_backfill_weather_direct_also_updates_memory() -> None:
    """backfill_weather: after successful lookup, also updates in-memory session (lines 615-617)."""
    from datetime import UTC, datetime

    from cataclysm.equipment import SessionConditions, TrackCondition

    from backend.api.routers.sessions import backfill_weather

    mock_weather = SessionConditions(
        track_condition=TrackCondition.DRY,
        ambient_temp_c=20.0,
        track_temp_c=30.0,
        humidity_pct=45.0,
    )

    session_id = "in-memory-backfill-sess"
    mock_row = MagicMock()
    mock_row.session_id = session_id
    mock_row.session_date = datetime(2026, 2, 22, 10, 0, tzinfo=UTC)
    mock_row.snapshot_json = {"gps_centroid": {"lat": 33.53, "lon": -86.62}}

    mock_db = AsyncMock()
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()

    mock_user = MagicMock()
    mock_user.user_id = _TEST_USER.user_id

    # Put a session into the in-memory store with no weather
    sd = _make_session_data(session_id=session_id)
    sd.weather = None
    session_store._store[session_id] = sd

    try:
        with (
            patch(
                "backend.api.routers.sessions.list_sessions_for_user",
                new_callable=AsyncMock,
                return_value=[mock_row],
            ),
            patch(
                "cataclysm.weather_client.lookup_weather",
                new_callable=AsyncMock,
                return_value=mock_weather,
            ),
        ):
            result = await backfill_weather(current_user=mock_user, db=mock_db)

        assert result["backfilled"] == 1
        # In-memory session should now have weather set
        assert session_store._store[session_id].weather is mock_weather
    finally:
        session_store._store.pop(session_id, None)


@pytest.mark.asyncio
async def test_backfill_weather_direct_skip_null_lat() -> None:
    """backfill_weather: centroid with lat=None skips session (lines 578-580)."""
    from datetime import UTC, datetime

    from backend.api.routers.sessions import backfill_weather

    mock_row = MagicMock()
    mock_row.session_id = "null-lat-sess"
    mock_row.session_date = datetime(2026, 2, 22, 10, 0, tzinfo=UTC)
    mock_row.snapshot_json = {"gps_centroid": {"lat": None, "lon": -86.62}}

    mock_db = AsyncMock()
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()

    mock_user = MagicMock()
    mock_user.user_id = _TEST_USER.user_id

    with patch(
        "backend.api.routers.sessions.list_sessions_for_user",
        new_callable=AsyncMock,
        return_value=[mock_row],
    ):
        result = await backfill_weather(current_user=mock_user, db=mock_db)

    assert result["skipped"] == 1
    assert result["backfilled"] == 0


@pytest.mark.asyncio
async def test_backfill_weather_direct_no_session_date() -> None:
    """backfill_weather: session_date=None skips session (lines 585-589)."""
    from backend.api.routers.sessions import backfill_weather

    mock_row = MagicMock()
    mock_row.session_id = "no-date-sess-direct"
    mock_row.session_date = None
    mock_row.snapshot_json = {"gps_centroid": {"lat": 33.53, "lon": -86.62}}

    mock_db = AsyncMock()
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()

    mock_user = MagicMock()
    mock_user.user_id = _TEST_USER.user_id

    with patch(
        "backend.api.routers.sessions.list_sessions_for_user",
        new_callable=AsyncMock,
        return_value=[mock_row],
    ):
        result = await backfill_weather(current_user=mock_user, db=mock_db)

    assert result["skipped"] == 1
    assert result["total"] == 1


@pytest.mark.asyncio
async def test_backfill_weather_direct_memory_fallback_success() -> None:
    """backfill_weather: no centroid → memory session fallback succeeds (lines 548-570)."""
    from cataclysm.equipment import SessionConditions, TrackCondition

    from backend.api.routers.sessions import backfill_weather

    session_id = "mem-fallback-sess"
    mock_weather = SessionConditions(
        track_condition=TrackCondition.DRY,
        ambient_temp_c=20.0,
        track_temp_c=30.0,
        humidity_pct=45.0,
        wind_speed_kmh=5.0,
        wind_direction_deg=90.0,
        precipitation_mm=0.0,
        weather_source="open-meteo",
    )

    mock_row = MagicMock()
    mock_row.session_id = session_id
    mock_row.session_date = None
    mock_row.snapshot_json = {}  # no centroid, no weather

    mock_db = AsyncMock()
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()

    mock_user = MagicMock()
    mock_user.user_id = _TEST_USER.user_id

    # Put a session in memory without weather
    sd = _make_session_data(session_id=session_id)
    sd.weather = None
    session_store._store[session_id] = sd

    async def _set_weather_on_sd(sd_arg: object) -> None:
        sd_arg.weather = mock_weather  # type: ignore[attr-defined]

    try:
        with (
            patch(
                "backend.api.routers.sessions.list_sessions_for_user",
                new_callable=AsyncMock,
                return_value=[mock_row],
            ),
            patch(
                "backend.api.routers.sessions._auto_fetch_weather",
                new_callable=AsyncMock,
                side_effect=_set_weather_on_sd,
            ),
        ):
            result = await backfill_weather(current_user=mock_user, db=mock_db)

        assert result["backfilled"] == 1
        assert result["skipped"] == 0
    finally:
        session_store._store.pop(session_id, None)


@pytest.mark.asyncio
async def test_backfill_weather_direct_memory_fallback_exception() -> None:
    """backfill_weather: memory fallback raises OSError → skipped (line 571-573)."""
    from backend.api.routers.sessions import backfill_weather

    session_id = "mem-fallback-err-sess"

    mock_row = MagicMock()
    mock_row.session_id = session_id
    mock_row.session_date = None
    mock_row.snapshot_json = {}  # no centroid

    mock_db = AsyncMock()
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()

    mock_user = MagicMock()
    mock_user.user_id = _TEST_USER.user_id

    # Put a session in memory without weather
    sd = _make_session_data(session_id=session_id)
    sd.weather = None
    session_store._store[session_id] = sd

    try:
        with (
            patch(
                "backend.api.routers.sessions.list_sessions_for_user",
                new_callable=AsyncMock,
                return_value=[mock_row],
            ),
            patch(
                "backend.api.routers.sessions._auto_fetch_weather",
                new_callable=AsyncMock,
                side_effect=OSError("network error"),
            ),
        ):
            result = await backfill_weather(current_user=mock_user, db=mock_db)

        assert result["skipped"] == 1
        assert result["backfilled"] == 0
    finally:
        session_store._store.pop(session_id, None)


# ===========================================================================
# Direct-function tests for list_sessions fallback paths (lines 303, 306-315, 342-346)
# ===========================================================================


@pytest.mark.asyncio
async def test_list_sessions_direct_in_memory_path() -> None:
    """list_sessions: in-memory session path → session score computed (lines 306-315)."""
    from backend.api.routers.sessions import list_sessions

    session_id = "list-mem-sess"
    sd = _make_session_data(session_id=session_id)
    sd.weather = None
    session_store._store[session_id] = sd

    mock_row = MagicMock()
    mock_row.session_id = session_id
    mock_row.snapshot_json = None

    mock_db = AsyncMock()
    mock_user = MagicMock()
    mock_user.user_id = _TEST_USER.user_id

    try:
        with (
            patch(
                "backend.api.routers.sessions.list_sessions_for_user",
                new_callable=AsyncMock,
                return_value=[mock_row],
            ),
            patch(
                "backend.api.routers.sessions._compute_session_score",
                new_callable=AsyncMock,
                return_value=85.0,
            ),
        ):
            result = await list_sessions(current_user=mock_user, db=mock_db)

        assert result.total == 1
        assert result.items[0].session_id == session_id
        assert result.items[0].session_score == pytest.approx(85.0)
    finally:
        session_store._store.pop(session_id, None)


@pytest.mark.asyncio
async def test_list_sessions_direct_db_fallback_with_weather() -> None:
    """list_sessions: DB-only row with weather in snapshot_json (lines 342-365)."""
    from datetime import date

    from backend.api.routers.sessions import list_sessions

    mock_row = MagicMock()
    mock_row.session_id = "db-only-sess"
    mock_row.track_name = "Barber Motorsports Park"
    mock_row.session_date = date(2026, 2, 22)
    mock_row.n_laps = 10
    mock_row.n_clean_laps = 8
    mock_row.best_lap_time_s = 100.5
    mock_row.top3_avg_time_s = 101.0
    mock_row.avg_lap_time_s = 105.0
    mock_row.consistency_score = 0.85
    mock_row.snapshot_json = {
        "weather": {
            "ambient_temp_c": 22.5,
            "track_condition": "dry",
            "humidity_pct": 55.0,
            "wind_speed_kmh": 10.0,
            "precipitation_mm": 0.0,
        },
        "gps_quality": {"overall_score": 0.9, "grade": "A"},
    }

    mock_db = AsyncMock()
    mock_user = MagicMock()
    mock_user.user_id = _TEST_USER.user_id

    # Session NOT in memory — forces DB-only fallback at line 341
    with patch(
        "backend.api.routers.sessions.list_sessions_for_user",
        new_callable=AsyncMock,
        return_value=[mock_row],
    ):
        result = await list_sessions(current_user=mock_user, db=mock_db)

    assert result.total == 1
    item = result.items[0]
    assert item.session_id == "db-only-sess"
    assert item.track_name == "Barber Motorsports Park"
    assert item.weather_temp_c == pytest.approx(22.5)
    assert item.weather_condition == "dry"
    assert item.gps_quality_score == pytest.approx(0.9)
    assert item.gps_quality_grade == "A"


@pytest.mark.asyncio
async def test_list_sessions_direct_db_fallback_no_weather_no_gps() -> None:
    """list_sessions: DB-only row with empty snapshot returns None for all weather/GPS fields."""
    from datetime import date

    from backend.api.routers.sessions import list_sessions

    mock_row = MagicMock()
    mock_row.session_id = "db-bare-sess"
    mock_row.track_name = "Road Atlanta"
    mock_row.session_date = date(2026, 1, 1)
    mock_row.n_laps = 5
    mock_row.n_clean_laps = 4
    mock_row.best_lap_time_s = 80.0
    mock_row.top3_avg_time_s = 81.0
    mock_row.avg_lap_time_s = 83.0
    mock_row.consistency_score = None
    mock_row.snapshot_json = {}  # empty — no weather, no GPS

    mock_db = AsyncMock()
    mock_user = MagicMock()
    mock_user.user_id = _TEST_USER.user_id

    with patch(
        "backend.api.routers.sessions.list_sessions_for_user",
        new_callable=AsyncMock,
        return_value=[mock_row],
    ):
        result = await list_sessions(current_user=mock_user, db=mock_db)

    assert result.total == 1
    item = result.items[0]
    assert item.weather_temp_c is None
    assert item.gps_quality_score is None


# ===========================================================================
# Direct-function tests for delete_all_sessions (lines 432-438)
# ===========================================================================


@pytest.mark.asyncio
async def test_delete_all_sessions_direct_with_sessions() -> None:
    """delete_all_sessions: iterates, calls delete_session_db + memory clear (lines 432-438)."""
    from backend.api.routers.sessions import delete_all_sessions

    session_id_1 = "del-all-sess-1"
    session_id_2 = "del-all-sess-2"

    mock_row_1 = MagicMock()
    mock_row_1.session_id = session_id_1
    mock_row_2 = MagicMock()
    mock_row_2.session_id = session_id_2

    mock_db = AsyncMock()
    mock_db.commit = AsyncMock()

    mock_user = MagicMock()
    mock_user.user_id = _TEST_USER.user_id

    # Put sessions in memory
    for sid in [session_id_1, session_id_2]:
        sd = _make_session_data(session_id=sid)
        session_store._store[sid] = sd

    try:
        with (
            patch(
                "backend.api.routers.sessions.list_sessions_for_user",
                new_callable=AsyncMock,
                return_value=[mock_row_1, mock_row_2],
            ),
            patch(
                "backend.api.routers.sessions.delete_session_db",
                new_callable=AsyncMock,
                return_value=True,
            ) as mock_delete_db,
            patch(
                "backend.api.routers.sessions.clear_coaching_data",
                new_callable=AsyncMock,
            ) as mock_clear_coaching,
        ):
            result = await delete_all_sessions(current_user=mock_user, db=mock_db)

        assert result["message"] == "Deleted 2 session(s)"
        assert mock_delete_db.call_count == 2
        assert mock_clear_coaching.call_count == 2
        # Memory store should be cleared
        assert session_id_1 not in session_store._store
        assert session_id_2 not in session_store._store
    finally:
        session_store._store.pop(session_id_1, None)
        session_store._store.pop(session_id_2, None)


# ===========================================================================
# Direct-function tests for delete_session (lines 449-453)
# ===========================================================================


@pytest.mark.asyncio
async def test_delete_session_direct_success() -> None:
    """delete_session: DB deletion succeeds → memory cleared + coaching cleared (lines 449-453)."""
    from backend.api.routers.sessions import delete_session

    session_id = "del-direct-sess"
    sd = _make_session_data(session_id=session_id)
    session_store._store[session_id] = sd

    mock_db = AsyncMock()
    mock_user = MagicMock()
    mock_user.user_id = _TEST_USER.user_id

    try:
        with (
            patch(
                "backend.api.routers.sessions.delete_session_db",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "backend.api.routers.sessions.clear_coaching_data",
                new_callable=AsyncMock,
            ) as mock_clear,
        ):
            result = await delete_session(
                session_id=session_id,
                current_user=mock_user,
                db=mock_db,
            )

        assert f"{session_id} deleted" in result["message"]
        mock_clear.assert_called_once_with(session_id)
        assert session_id not in session_store._store
    finally:
        session_store._store.pop(session_id, None)


# ===========================================================================
# Residual coverage for lines 310-312, 450, 541-542
# ===========================================================================


@pytest.mark.asyncio
async def test_list_sessions_restores_weather_from_snapshot() -> None:
    """list_sessions: restores weather from snapshot_json when sd.weather is None."""
    from backend.api.routers.sessions import list_sessions

    session_id = "restore-weather-sess"
    sd = _make_session_data(session_id=session_id)
    sd.weather = None  # not set — triggers the restore path
    session_store._store[session_id] = sd

    mock_row = MagicMock()
    mock_row.session_id = session_id
    # snapshot_json contains weather data that restore_weather_from_snapshot will parse
    mock_row.snapshot_json = {
        "weather": {
            "track_condition": "dry",
            "ambient_temp_c": 20.0,
            "track_temp_c": 32.0,
            "humidity_pct": 55.0,
            "wind_speed_kmh": 8.0,
            "wind_direction_deg": 180.0,
            "precipitation_mm": 0.0,
            "weather_source": "open-meteo",
        }
    }

    mock_db = AsyncMock()
    mock_user = MagicMock()
    mock_user.user_id = _TEST_USER.user_id

    try:
        with (
            patch(
                "backend.api.routers.sessions.list_sessions_for_user",
                new_callable=AsyncMock,
                return_value=[mock_row],
            ),
            patch(
                "backend.api.routers.sessions._compute_session_score",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            result = await list_sessions(current_user=mock_user, db=mock_db)

        assert result.total == 1
        # Weather should have been restored on sd from snapshot
        assert sd.weather is not None
        assert sd.weather.ambient_temp_c == pytest.approx(20.0)
    finally:
        session_store._store.pop(session_id, None)


@pytest.mark.asyncio
async def test_delete_session_direct_not_found_raises_404() -> None:
    """delete_session: db_deleted=False raises HTTPException 404 (line 450)."""
    from fastapi import HTTPException as _HTTPException

    from backend.api.routers.sessions import delete_session

    mock_db = AsyncMock()
    mock_user = MagicMock()
    mock_user.user_id = _TEST_USER.user_id

    with (
        patch(
            "backend.api.routers.sessions.delete_session_db",
            new_callable=AsyncMock,
            return_value=False,  # session does not exist or not owned
        ),
        pytest.raises(_HTTPException) as exc_info,
    ):
        await delete_session(
            session_id="ghost-session",
            current_user=mock_user,
            db=mock_db,
        )

    assert exc_info.value.status_code == 404
    assert "ghost-session" in exc_info.value.detail


@pytest.mark.asyncio
async def test_backfill_weather_direct_skip_existing_weather() -> None:
    """backfill_weather: snap already has weather → skipped immediately (lines 541-542)."""
    from backend.api.routers.sessions import backfill_weather

    mock_row = MagicMock()
    mock_row.session_id = "already-has-weather"
    mock_row.session_date = None
    mock_row.snapshot_json = {"weather": {"track_condition": "dry", "ambient_temp_c": 20.0}}

    mock_db = AsyncMock()
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()

    mock_user = MagicMock()
    mock_user.user_id = _TEST_USER.user_id

    with patch(
        "backend.api.routers.sessions.list_sessions_for_user",
        new_callable=AsyncMock,
        return_value=[mock_row],
    ):
        result = await backfill_weather(current_user=mock_user, db=mock_db)

    assert result["skipped"] == 1
    assert result["backfilled"] == 0
    assert result["total"] == 1
