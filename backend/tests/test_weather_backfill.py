"""Tests for the weather backfill service (lazy retry + background + rebackfill)."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from cataclysm.equipment import SessionConditions, TrackCondition

from backend.api.services.weather_backfill import (
    WEATHER_RETRY_COOLDOWN_S,
    _weather_retry_cooldown,
    rebackfill_all_sessions,
    record_weather_attempt,
    should_retry_weather,
    weather_to_dict,
)


class TestShouldRetryWeather:
    """Tests for the cooldown-based retry gating."""

    def setup_method(self) -> None:
        _weather_retry_cooldown.clear()

    def test_first_attempt_always_allowed(self) -> None:
        assert should_retry_weather("never-seen") is True

    def test_blocked_within_cooldown(self) -> None:
        record_weather_attempt("sess-1")
        assert should_retry_weather("sess-1") is False

    def test_allowed_after_cooldown(self) -> None:
        record_weather_attempt("sess-2")
        # Simulate time passing by backdating the entry
        _weather_retry_cooldown["sess-2"] = time.monotonic() - WEATHER_RETRY_COOLDOWN_S - 1
        assert should_retry_weather("sess-2") is True

    def test_independent_sessions(self) -> None:
        record_weather_attempt("sess-a")
        assert should_retry_weather("sess-a") is False
        assert should_retry_weather("sess-b") is True


class TestWeatherToDict:
    """Tests for the weather serialization helper."""

    def test_serializes_all_fields(self) -> None:
        w = SessionConditions(
            track_condition=TrackCondition.WET,
            ambient_temp_c=15.5,
            track_temp_c=20.0,
            humidity_pct=80.0,
            wind_speed_kmh=25.0,
            wind_direction_deg=270.0,
            precipitation_mm=3.2,
            surface_water_mm=0.45,
            weather_source="open-meteo",
            weather_confidence=0.85,
            dew_point_c=12.0,
        )
        d = weather_to_dict(w)
        assert d["track_condition"] == "wet"
        assert d["ambient_temp_c"] == pytest.approx(15.5)
        assert d["track_temp_c"] == pytest.approx(20.0)
        assert d["humidity_pct"] == pytest.approx(80.0)
        assert d["wind_speed_kmh"] == pytest.approx(25.0)
        assert d["wind_direction_deg"] == pytest.approx(270.0)
        assert d["precipitation_mm"] == pytest.approx(3.2)
        assert d["surface_water_mm"] == pytest.approx(0.45)
        assert d["weather_source"] == "open-meteo"
        assert d["weather_confidence"] == pytest.approx(0.85)
        assert d["dew_point_c"] == pytest.approx(12.0)
        assert d["track_condition_is_manual"] is False

    def test_dry_condition_string(self) -> None:
        w = SessionConditions(
            track_condition=TrackCondition.DRY,
            ambient_temp_c=30.0,
            weather_source="open-meteo",
        )
        d = weather_to_dict(w)
        assert d["track_condition"] == "dry"

    def test_new_surface_water_fields_default_none(self) -> None:
        """New fields serialize to None when not set."""
        w = SessionConditions(
            track_condition=TrackCondition.DRY,
            weather_source="open-meteo",
        )
        d = weather_to_dict(w)
        assert d["surface_water_mm"] is None
        assert d["weather_confidence"] is None
        assert d["dew_point_c"] is None


# ---------------------------------------------------------------------------
# Rebackfill tests — helpers
# ---------------------------------------------------------------------------

_DB_FACTORY_PATH = "backend.api.db.database.async_session_factory"
_LOOKUP_PATH = "backend.api.services.weather_backfill.lookup_weather"
_GET_SESSION_PATH = "backend.api.services.session_store.get_session"
_DELAY_PATH = "backend.api.services.weather_backfill.REBACKFILL_BATCH_DELAY_S"


def _make_session_row(
    session_id: str,
    *,
    weather: dict[str, object] | None = None,
    lat: float = 33.53,
    lon: float = -86.62,
    session_date: datetime | None = None,
) -> MagicMock:
    """Build a mock DB session row for rebackfill tests."""
    snap: dict[str, object] = {
        "gps_centroid": {"lat": lat, "lon": lon},
    }
    if weather is not None:
        snap["weather"] = weather
    row = MagicMock()
    row.session_id = session_id
    row.snapshot_json = snap
    row.session_date = session_date or datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
    return row


def _mock_db_factory(rows: list[MagicMock]) -> AsyncMock:
    """Create a mock async_session_factory returning the given rows."""
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = rows

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.commit = AsyncMock()

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    factory = MagicMock(return_value=mock_ctx)
    return factory


# ---------------------------------------------------------------------------
# Rebackfill tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rebackfill_updates_model_derived_sessions() -> None:
    """Rebackfill re-processes sessions and returns updated count."""
    wet_result = SessionConditions(
        track_condition=TrackCondition.WET,
        ambient_temp_c=10.0,
        humidity_pct=95.0,
        precipitation_mm=5.0,
        surface_water_mm=1.2,
        weather_source="open-meteo-v2",
        weather_confidence=0.9,
    )

    row = _make_session_row(
        "sess-rebackfill-1",
        weather={"track_condition": "dry", "weather_source": "open-meteo"},
    )
    factory = _mock_db_factory([row])

    with (
        patch(_LOOKUP_PATH, new_callable=AsyncMock, return_value=wet_result),
        patch(_DB_FACTORY_PATH, factory),
        patch(_GET_SESSION_PATH, return_value=None),
        patch(_DELAY_PATH, 0),
    ):
        stats = await rebackfill_all_sessions()

    assert stats["updated"] == 1
    assert stats["skipped_manual"] == 0
    assert stats["failed"] == 0
    assert stats["total"] == 1

    # Verify the row's snapshot was updated
    saved_weather = row.snapshot_json["weather"]
    assert saved_weather["track_condition"] == "wet"
    assert saved_weather["surface_water_mm"] == pytest.approx(1.2)
    assert saved_weather["weather_confidence"] == pytest.approx(0.9)


@pytest.mark.asyncio
async def test_rebackfill_skips_manual_overrides() -> None:
    """Sessions with track_condition_is_manual=True are skipped."""
    manual_row = _make_session_row(
        "sess-manual",
        weather={
            "track_condition": "wet",
            "track_condition_is_manual": True,
            "weather_source": "manual",
        },
    )
    auto_row = _make_session_row(
        "sess-auto",
        weather={
            "track_condition": "dry",
            "track_condition_is_manual": False,
            "weather_source": "open-meteo",
        },
    )

    damp_result = SessionConditions(
        track_condition=TrackCondition.DAMP,
        ambient_temp_c=18.0,
        humidity_pct=75.0,
        precipitation_mm=0.3,
        surface_water_mm=0.15,
        weather_source="open-meteo-v2",
        weather_confidence=0.7,
    )

    factory = _mock_db_factory([manual_row, auto_row])

    with (
        patch(
            _LOOKUP_PATH,
            new_callable=AsyncMock,
            return_value=damp_result,
        ),
        patch(_DB_FACTORY_PATH, factory),
        patch(_GET_SESSION_PATH, return_value=None),
        patch(_DELAY_PATH, 0),
    ):
        stats = await rebackfill_all_sessions()

    assert stats["skipped_manual"] == 1
    assert stats["updated"] == 1
    assert stats["total"] == 2

    # Manual row should NOT have been modified
    assert manual_row.snapshot_json["weather"]["track_condition"] == "wet"
    assert manual_row.snapshot_json["weather"]["weather_source"] == "manual"

    # Auto row SHOULD have been updated
    assert auto_row.snapshot_json["weather"]["track_condition"] == "damp"


@pytest.mark.asyncio
async def test_rebackfill_handles_api_failure_gracefully() -> None:
    """When lookup_weather returns None, the session is counted as failed."""
    row = _make_session_row(
        "sess-fail",
        weather={"track_condition": "dry", "weather_source": "open-meteo"},
    )
    factory = _mock_db_factory([row])

    with (
        patch(_LOOKUP_PATH, new_callable=AsyncMock, return_value=None),
        patch(_DB_FACTORY_PATH, factory),
        patch(_DELAY_PATH, 0),
    ):
        stats = await rebackfill_all_sessions()

    assert stats["failed"] == 1
    assert stats["updated"] == 0
    assert stats["total"] == 1

    # Original weather should be untouched
    assert row.snapshot_json["weather"]["track_condition"] == "dry"


@pytest.mark.asyncio
async def test_rebackfill_handles_exception_gracefully() -> None:
    """When lookup_weather raises, the session is counted as failed."""
    row = _make_session_row(
        "sess-exc",
        weather={"track_condition": "dry", "weather_source": "open-meteo"},
    )
    factory = _mock_db_factory([row])

    with (
        patch(
            _LOOKUP_PATH,
            new_callable=AsyncMock,
            side_effect=RuntimeError("API timeout"),
        ),
        patch(_DB_FACTORY_PATH, factory),
        patch(_DELAY_PATH, 0),
    ):
        stats = await rebackfill_all_sessions()

    assert stats["failed"] == 1
    assert stats["updated"] == 0


@pytest.mark.asyncio
async def test_rebackfill_skips_sessions_without_coords() -> None:
    """Sessions without GPS centroid and no in-memory data are skipped."""
    row = MagicMock()
    row.session_id = "sess-no-gps"
    row.snapshot_json = {"weather": {"track_condition": "dry"}}
    row.session_date = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)

    factory = _mock_db_factory([row])

    with (
        patch(_DB_FACTORY_PATH, factory),
        patch(_GET_SESSION_PATH, return_value=None),
        patch(_DELAY_PATH, 0),
    ):
        stats = await rebackfill_all_sessions()

    assert stats["skipped_no_coords"] == 1
    assert stats["updated"] == 0


@pytest.mark.asyncio
async def test_rebackfill_preserves_track_temp_and_timezone() -> None:
    """Rebackfill preserves existing track_temp_c and timezone_name."""
    row = _make_session_row(
        "sess-preserve",
        weather={
            "track_condition": "dry",
            "track_temp_c": 42.5,
            "timezone_name": "America/New_York",
            "weather_source": "open-meteo",
        },
    )

    new_weather = SessionConditions(
        track_condition=TrackCondition.WET,
        ambient_temp_c=10.0,
        humidity_pct=90.0,
        precipitation_mm=4.0,
        weather_source="open-meteo-v2",
    )

    factory = _mock_db_factory([row])

    with (
        patch(
            _LOOKUP_PATH,
            new_callable=AsyncMock,
            return_value=new_weather,
        ),
        patch(_DB_FACTORY_PATH, factory),
        patch(_GET_SESSION_PATH, return_value=None),
        patch(_DELAY_PATH, 0),
    ):
        stats = await rebackfill_all_sessions()

    assert stats["updated"] == 1
    saved = row.snapshot_json["weather"]
    assert saved["track_temp_c"] == pytest.approx(42.5)
    assert saved["track_condition"] == "wet"
