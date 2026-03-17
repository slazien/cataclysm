"""Tests for the weather backfill service (lazy retry + background)."""

from __future__ import annotations

import time

import pytest

from backend.api.services.weather_backfill import (
    WEATHER_RETRY_COOLDOWN_S,
    _weather_retry_cooldown,
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
        from cataclysm.equipment import SessionConditions, TrackCondition

        w = SessionConditions(
            track_condition=TrackCondition.WET,
            ambient_temp_c=15.5,
            track_temp_c=20.0,
            humidity_pct=80.0,
            wind_speed_kmh=25.0,
            wind_direction_deg=270.0,
            precipitation_mm=3.2,
            weather_source="open-meteo",
        )
        d = weather_to_dict(w)
        assert d["track_condition"] == "wet"
        assert d["ambient_temp_c"] == pytest.approx(15.5)
        assert d["track_temp_c"] == pytest.approx(20.0)
        assert d["humidity_pct"] == pytest.approx(80.0)
        assert d["wind_speed_kmh"] == pytest.approx(25.0)
        assert d["wind_direction_deg"] == pytest.approx(270.0)
        assert d["precipitation_mm"] == pytest.approx(3.2)
        assert d["weather_source"] == "open-meteo"

    def test_dry_condition_string(self) -> None:
        from cataclysm.equipment import SessionConditions, TrackCondition

        w = SessionConditions(
            track_condition=TrackCondition.DRY,
            ambient_temp_c=30.0,
            weather_source="open-meteo",
        )
        d = weather_to_dict(w)
        assert d["track_condition"] == "dry"
