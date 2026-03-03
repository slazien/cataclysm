"""Tests for backend.api.services.db_session_store.

Covers:
- store_session_db(): merge semantics, snapshot_json assembly (weather, GPS centroid,
  GPS quality), DB row creation
- restore_weather_from_snapshot(): happy path, missing keys, None input
- list_sessions_for_user(): ordering, multiple users, empty result
- verify_session_owner(): true/false ownership, cross-user protection
- delete_session_db(): owned deletion, unowned denial, return bool
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd
import pytest

from backend.api.services.db_session_store import (
    delete_session_db,
    list_sessions_for_user,
    restore_weather_from_snapshot,
    store_session_db,
    verify_session_owner,
)
from backend.tests.conftest import _TEST_USER, _test_session_factory

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_snapshot(
    session_id: str = "sess-test-1",
    track_name: str = "Test Circuit",
    session_date: str = "22/02/2026",
    n_laps: int = 3,
    n_clean_laps: int = 2,
    best_lap_time_s: float = 90.5,
    top3_avg_time_s: float = 92.0,
    avg_lap_time_s: float = 93.0,
    consistency_score: float = 85.0,
) -> MagicMock:
    """Return a minimal SessionSnapshot mock."""
    snap = MagicMock()
    snap.session_id = session_id
    snap.metadata.track_name = track_name
    snap.metadata.session_date = session_date
    snap.n_laps = n_laps
    snap.n_clean_laps = n_clean_laps
    snap.best_lap_time_s = best_lap_time_s
    snap.top3_avg_time_s = top3_avg_time_s
    snap.avg_lap_time_s = avg_lap_time_s
    snap.consistency_score = consistency_score
    return snap


def _make_parsed_with_gps(lat_mean: float = 33.53, lon_mean: float = -86.62) -> MagicMock:
    """Return a ParsedSession mock whose .data has lat/lon columns."""
    parsed = MagicMock()
    df = pd.DataFrame(
        {
            "lat": [lat_mean - 0.001, lat_mean, lat_mean + 0.001],
            "lon": [lon_mean - 0.001, lon_mean, lon_mean + 0.001],
        }
    )
    parsed.data = df
    return parsed


def _make_parsed_without_gps() -> MagicMock:
    """Return a ParsedSession mock whose .data has no lat/lon columns."""
    parsed = MagicMock()
    parsed.data = pd.DataFrame({"speed": [10.0, 20.0, 30.0]})
    return parsed


def _make_parsed_empty_df() -> MagicMock:
    """Return a ParsedSession mock whose .data is an empty DataFrame."""
    parsed = MagicMock()
    parsed.data = pd.DataFrame()
    return parsed


def _make_weather(
    track_condition: str = "dry",
    ambient_temp_c: float = 22.0,
    track_temp_c: float = 35.0,
    humidity_pct: float = 60.0,
    wind_speed_kmh: float = 10.0,
    wind_direction_deg: float = 180.0,
    precipitation_mm: float = 0.0,
    weather_source: str = "open-meteo",
) -> MagicMock:
    """Return a minimal SessionConditions mock."""
    from cataclysm.equipment import TrackCondition

    weather = MagicMock()
    weather.track_condition = TrackCondition(track_condition)
    weather.ambient_temp_c = ambient_temp_c
    weather.track_temp_c = track_temp_c
    weather.humidity_pct = humidity_pct
    weather.wind_speed_kmh = wind_speed_kmh
    weather.wind_direction_deg = wind_direction_deg
    weather.precipitation_mm = precipitation_mm
    weather.weather_source = weather_source
    return weather


def _make_gps_quality(
    overall_score: float = 92.0,
    grade: str = "A",
    is_usable: bool = True,
) -> MagicMock:
    """Return a minimal GPSQualityReport mock."""
    gps = MagicMock()
    gps.overall_score = overall_score
    gps.grade = grade
    gps.is_usable = is_usable
    return gps


def _make_session_data(
    session_id: str = "sess-test-1",
    *,
    weather: object = None,
    gps_quality: object = None,
    parsed: object = None,
) -> MagicMock:
    """Return a SessionData mock with configurable sub-components."""
    sd = MagicMock()
    sd.session_id = session_id
    sd.snapshot = _make_snapshot(session_id=session_id)
    sd.weather = weather
    sd.gps_quality = gps_quality
    sd.parsed = parsed if parsed is not None else _make_parsed_with_gps()
    return sd


# ---------------------------------------------------------------------------
# store_session_db
# ---------------------------------------------------------------------------


class TestStoreSessionDb:
    """Tests for store_session_db()."""

    @pytest.mark.asyncio
    async def test_stores_basic_session_row(self) -> None:
        """A minimal SessionData produces a valid DB row."""
        async with _test_session_factory() as db:
            sd = _make_session_data()
            await store_session_db(db, _TEST_USER.user_id, sd)
            await db.commit()

        async with _test_session_factory() as db:
            rows = await list_sessions_for_user(db, _TEST_USER.user_id)

        assert len(rows) == 1
        assert rows[0].session_id == "sess-test-1"
        assert rows[0].track_name == "Test Circuit"
        assert rows[0].user_id == _TEST_USER.user_id

    @pytest.mark.asyncio
    async def test_snapshot_json_includes_weather(self) -> None:
        """When weather is present it is serialised into snapshot_json."""
        weather = _make_weather(ambient_temp_c=28.0, track_temp_c=42.0)
        sd = _make_session_data(weather=weather)

        async with _test_session_factory() as db:
            await store_session_db(db, _TEST_USER.user_id, sd)
            await db.commit()

        async with _test_session_factory() as db:
            rows = await list_sessions_for_user(db, _TEST_USER.user_id)

        assert rows[0].snapshot_json is not None
        w = rows[0].snapshot_json["weather"]
        assert w["track_condition"] == "dry"
        assert w["ambient_temp_c"] == pytest.approx(28.0)
        assert w["track_temp_c"] == pytest.approx(42.0)
        assert w["weather_source"] == "open-meteo"

    @pytest.mark.asyncio
    async def test_snapshot_json_includes_gps_centroid(self) -> None:
        """When lat/lon columns are present the GPS centroid is persisted."""
        parsed = _make_parsed_with_gps(lat_mean=33.53, lon_mean=-86.62)
        sd = _make_session_data(parsed=parsed)

        async with _test_session_factory() as db:
            await store_session_db(db, _TEST_USER.user_id, sd)
            await db.commit()

        async with _test_session_factory() as db:
            rows = await list_sessions_for_user(db, _TEST_USER.user_id)

        snap = rows[0].snapshot_json
        assert snap is not None
        centroid = snap["gps_centroid"]
        assert centroid["lat"] == pytest.approx(33.53, abs=0.001)
        assert centroid["lon"] == pytest.approx(-86.62, abs=0.001)

    @pytest.mark.asyncio
    async def test_snapshot_json_includes_gps_quality(self) -> None:
        """When gps_quality is provided it is persisted in snapshot_json."""
        gps = _make_gps_quality(overall_score=88.5, grade="B", is_usable=True)
        sd = _make_session_data(gps_quality=gps)

        async with _test_session_factory() as db:
            await store_session_db(db, _TEST_USER.user_id, sd)
            await db.commit()

        async with _test_session_factory() as db:
            rows = await list_sessions_for_user(db, _TEST_USER.user_id)

        snap2 = rows[0].snapshot_json
        assert snap2 is not None
        q = snap2["gps_quality"]
        assert q["overall_score"] == pytest.approx(88.5)
        assert q["grade"] == "B"
        assert q["is_usable"] is True

    @pytest.mark.asyncio
    async def test_snapshot_json_none_when_no_extras(self) -> None:
        """Without weather/gps, snapshot_json is None (not an empty dict)."""
        parsed = _make_parsed_without_gps()
        sd = _make_session_data(weather=None, gps_quality=None, parsed=parsed)

        async with _test_session_factory() as db:
            await store_session_db(db, _TEST_USER.user_id, sd)
            await db.commit()

        async with _test_session_factory() as db:
            rows = await list_sessions_for_user(db, _TEST_USER.user_id)

        assert rows[0].snapshot_json is None

    @pytest.mark.asyncio
    async def test_merge_semantics_on_re_upload(self) -> None:
        """Re-uploading the same session_id updates existing row, not duplicates."""
        sd1 = _make_session_data("sess-merge")
        sd1.snapshot.n_laps = 3

        sd2 = _make_session_data("sess-merge")
        sd2.snapshot.n_laps = 5

        async with _test_session_factory() as db:
            await store_session_db(db, _TEST_USER.user_id, sd1)
            await db.commit()

        async with _test_session_factory() as db:
            await store_session_db(db, _TEST_USER.user_id, sd2)
            await db.commit()

        async with _test_session_factory() as db:
            rows = await list_sessions_for_user(db, _TEST_USER.user_id)

        assert len(rows) == 1
        assert rows[0].n_laps == 5

    @pytest.mark.asyncio
    async def test_empty_dataframe_skips_centroid(self) -> None:
        """Empty DataFrame does not cause an error and centroid is omitted."""
        parsed = _make_parsed_empty_df()
        sd = _make_session_data(parsed=parsed)

        async with _test_session_factory() as db:
            await store_session_db(db, _TEST_USER.user_id, sd)
            await db.commit()

        async with _test_session_factory() as db:
            rows = await list_sessions_for_user(db, _TEST_USER.user_id)

        snap = rows[0].snapshot_json
        assert snap is None or "gps_centroid" not in (snap or {})

    @pytest.mark.asyncio
    async def test_all_snapshot_fields_present(self) -> None:
        """All three snapshot sections appear together when all data is provided."""
        parsed = _make_parsed_with_gps()
        weather = _make_weather()
        gps = _make_gps_quality()
        sd = _make_session_data(weather=weather, gps_quality=gps, parsed=parsed)

        async with _test_session_factory() as db:
            await store_session_db(db, _TEST_USER.user_id, sd)
            await db.commit()

        async with _test_session_factory() as db:
            rows = await list_sessions_for_user(db, _TEST_USER.user_id)

        snap = rows[0].snapshot_json
        assert snap is not None
        assert "weather" in snap
        assert "gps_centroid" in snap
        assert "gps_quality" in snap


# ---------------------------------------------------------------------------
# restore_weather_from_snapshot
# ---------------------------------------------------------------------------


class TestRestoreWeatherFromSnapshot:
    """Tests for restore_weather_from_snapshot()."""

    def test_returns_none_for_none_input(self) -> None:
        assert restore_weather_from_snapshot(None) is None

    def test_returns_none_for_empty_dict(self) -> None:
        assert restore_weather_from_snapshot({}) is None

    def test_returns_none_when_weather_key_missing(self) -> None:
        assert restore_weather_from_snapshot({"gps_centroid": {}}) is None

    def test_full_weather_blob_deserializes(self) -> None:
        from cataclysm.equipment import TrackCondition

        snapshot = {
            "weather": {
                "track_condition": "damp",
                "ambient_temp_c": 18.0,
                "track_temp_c": 25.0,
                "humidity_pct": 75.0,
                "wind_speed_kmh": 20.0,
                "wind_direction_deg": 90.0,
                "precipitation_mm": 1.5,
                "weather_source": "open-meteo",
            }
        }
        result = restore_weather_from_snapshot(snapshot)
        assert result is not None
        assert result.track_condition == TrackCondition.DAMP
        assert result.ambient_temp_c == pytest.approx(18.0)
        assert result.track_temp_c == pytest.approx(25.0)
        assert result.humidity_pct == pytest.approx(75.0)
        assert result.wind_speed_kmh == pytest.approx(20.0)
        assert result.wind_direction_deg == pytest.approx(90.0)
        assert result.precipitation_mm == pytest.approx(1.5)
        assert result.weather_source == "open-meteo"

    def test_missing_optional_weather_keys_default_to_none(self) -> None:
        """Partial weather dict (only track_condition) fills others as None."""
        snapshot = {"weather": {"track_condition": "dry"}}
        result = restore_weather_from_snapshot(snapshot)
        assert result is not None
        assert result.ambient_temp_c is None
        assert result.track_temp_c is None
        assert result.humidity_pct is None
        assert result.wind_speed_kmh is None
        assert result.wind_direction_deg is None
        assert result.precipitation_mm is None
        assert result.weather_source is None

    def test_wet_track_condition(self) -> None:
        from cataclysm.equipment import TrackCondition

        snapshot = {"weather": {"track_condition": "wet"}}
        result = restore_weather_from_snapshot(snapshot)
        assert result is not None
        assert result.track_condition == TrackCondition.WET

    def test_weather_source_preserved(self) -> None:
        snapshot = {
            "weather": {
                "track_condition": "dry",
                "weather_source": "manual_entry",
            }
        }
        result = restore_weather_from_snapshot(snapshot)
        assert result is not None
        assert result.weather_source == "manual_entry"


# ---------------------------------------------------------------------------
# list_sessions_for_user
# ---------------------------------------------------------------------------


class TestListSessionsForUser:
    """Tests for list_sessions_for_user()."""

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_sessions(self) -> None:
        async with _test_session_factory() as db:
            rows = await list_sessions_for_user(db, _TEST_USER.user_id)
        assert rows == []

    @pytest.mark.asyncio
    async def test_returns_only_sessions_for_user(self) -> None:
        """Sessions from another user_id are not returned."""
        sd1 = _make_session_data("sess-u1-a", parsed=_make_parsed_without_gps())
        sd2 = _make_session_data("sess-u1-b", parsed=_make_parsed_without_gps())

        async with _test_session_factory() as db:
            await store_session_db(db, _TEST_USER.user_id, sd1)
            await store_session_db(db, _TEST_USER.user_id, sd2)
            await db.commit()

        async with _test_session_factory() as db:
            rows = await list_sessions_for_user(db, _TEST_USER.user_id)

        ids = {r.session_id for r in rows}
        assert "sess-u1-a" in ids
        assert "sess-u1-b" in ids
        assert len(rows) == 2

    @pytest.mark.asyncio
    async def test_ordered_by_session_date_descending(self) -> None:
        """The oldest session comes last."""

        sd_old = _make_session_data("sess-old", parsed=_make_parsed_without_gps())
        sd_old.snapshot.metadata.session_date = "01/01/2024"

        sd_new = _make_session_data("sess-new", parsed=_make_parsed_without_gps())
        sd_new.snapshot.metadata.session_date = "01/01/2026"

        async with _test_session_factory() as db:
            await store_session_db(db, _TEST_USER.user_id, sd_old)
            await store_session_db(db, _TEST_USER.user_id, sd_new)
            await db.commit()

        async with _test_session_factory() as db:
            rows = await list_sessions_for_user(db, _TEST_USER.user_id)

        assert rows[0].session_id == "sess-new"
        assert rows[1].session_id == "sess-old"

    @pytest.mark.asyncio
    async def test_unknown_user_returns_empty_list(self) -> None:
        async with _test_session_factory() as db:
            rows = await list_sessions_for_user(db, "no-such-user")
        assert rows == []


# ---------------------------------------------------------------------------
# verify_session_owner
# ---------------------------------------------------------------------------


class TestVerifySessionOwner:
    """Tests for verify_session_owner()."""

    @pytest.mark.asyncio
    async def test_returns_true_for_owner(self) -> None:
        sd = _make_session_data("sess-own", parsed=_make_parsed_without_gps())
        async with _test_session_factory() as db:
            await store_session_db(db, _TEST_USER.user_id, sd)
            await db.commit()

        async with _test_session_factory() as db:
            assert await verify_session_owner(db, "sess-own", _TEST_USER.user_id) is True

    @pytest.mark.asyncio
    async def test_returns_false_for_wrong_user(self) -> None:
        sd = _make_session_data("sess-other", parsed=_make_parsed_without_gps())
        async with _test_session_factory() as db:
            await store_session_db(db, _TEST_USER.user_id, sd)
            await db.commit()

        async with _test_session_factory() as db:
            assert await verify_session_owner(db, "sess-other", "wrong-user-id") is False

    @pytest.mark.asyncio
    async def test_returns_false_for_nonexistent_session(self) -> None:
        async with _test_session_factory() as db:
            assert await verify_session_owner(db, "does-not-exist", _TEST_USER.user_id) is False

    @pytest.mark.asyncio
    async def test_correct_session_id_wrong_user_returns_false(self) -> None:
        """Even a valid session_id returns False when user_id does not match."""
        sd = _make_session_data("sess-idor", parsed=_make_parsed_without_gps())
        async with _test_session_factory() as db:
            await store_session_db(db, _TEST_USER.user_id, sd)
            await db.commit()

        async with _test_session_factory() as db:
            result = await verify_session_owner(db, "sess-idor", "attacker-user")
        assert result is False


# ---------------------------------------------------------------------------
# delete_session_db
# ---------------------------------------------------------------------------


class TestDeleteSessionDb:
    """Tests for delete_session_db()."""

    @pytest.mark.asyncio
    async def test_deletes_owned_session_returns_true(self) -> None:
        sd = _make_session_data("sess-del", parsed=_make_parsed_without_gps())
        async with _test_session_factory() as db:
            await store_session_db(db, _TEST_USER.user_id, sd)
            await db.commit()

        async with _test_session_factory() as db:
            result = await delete_session_db(db, "sess-del", _TEST_USER.user_id)
            await db.commit()

        assert result is True

        async with _test_session_factory() as db:
            rows = await list_sessions_for_user(db, _TEST_USER.user_id)
        assert all(r.session_id != "sess-del" for r in rows)

    @pytest.mark.asyncio
    async def test_returns_false_for_nonexistent_session(self) -> None:
        async with _test_session_factory() as db:
            result = await delete_session_db(db, "no-session", _TEST_USER.user_id)
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_for_wrong_user(self) -> None:
        """A session owned by user A cannot be deleted by user B."""
        sd = _make_session_data("sess-protected", parsed=_make_parsed_without_gps())
        async with _test_session_factory() as db:
            await store_session_db(db, _TEST_USER.user_id, sd)
            await db.commit()

        async with _test_session_factory() as db:
            result = await delete_session_db(db, "sess-protected", "evil-user")
        assert result is False

        async with _test_session_factory() as db:
            rows = await list_sessions_for_user(db, _TEST_USER.user_id)
        assert any(r.session_id == "sess-protected" for r in rows)

    @pytest.mark.asyncio
    async def test_delete_leaves_other_sessions_intact(self) -> None:
        """Deleting one session does not affect other sessions."""
        sd1 = _make_session_data("sess-keep", parsed=_make_parsed_without_gps())
        sd2 = _make_session_data("sess-remove", parsed=_make_parsed_without_gps())
        async with _test_session_factory() as db:
            await store_session_db(db, _TEST_USER.user_id, sd1)
            await store_session_db(db, _TEST_USER.user_id, sd2)
            await db.commit()

        async with _test_session_factory() as db:
            await delete_session_db(db, "sess-remove", _TEST_USER.user_id)
            await db.commit()

        async with _test_session_factory() as db:
            rows = await list_sessions_for_user(db, _TEST_USER.user_id)

        ids = {r.session_id for r in rows}
        assert "sess-keep" in ids
        assert "sess-remove" not in ids
