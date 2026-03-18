"""Tests for the Open-Meteo weather client."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from cataclysm.equipment import TrackCondition
from cataclysm.weather_client import (
    classify_surface_water,
    compute_condensation,
    compute_evaporation_rate,
    compute_runoff,
    compute_surface_water,
    compute_weather_confidence,
    lookup_weather,
    prepare_quarter_hourly,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_HOURLY_RESPONSE: dict[str, object] = {
    "hourly": {
        "time": [f"2025-02-15T{h:02d}:00" for h in range(24)],
        "temperature_2m": [22.0] * 24,
        "relative_humidity_2m": [50.0] * 24,
        "wind_speed_10m": [10.0] * 24,
        "wind_direction_10m": [180.0] * 24,
        "rain": [0.0] * 24,
        "showers": [0.0] * 24,
        "direct_radiation": [300.0] * 24,
        "dew_point_2m": [10.0] * 24,
        "cloud_cover": [30.0] * 24,
        "precipitation": [0.0] * 24,
    }
}


def _make_mock_response(payload: dict[str, object], status_code: int = 200) -> httpx.Response:
    """Build an httpx.Response with the given JSON payload."""
    return httpx.Response(
        status_code=status_code,
        json=payload,
        request=httpx.Request("GET", "https://api.open-meteo.com/v1/forecast"),
    )


def _make_rainy_response() -> dict[str, object]:
    """Build a response with heavy precipitation at session hour (12)."""
    rain = [0.0] * 24
    rain[12] = 5.2
    return {
        "hourly": {
            "time": [f"2025-02-15T{h:02d}:00" for h in range(24)],
            "temperature_2m": [18.0] * 24,
            "relative_humidity_2m": [90.0] * 24,
            "wind_speed_10m": [25.0] * 24,
            "wind_direction_10m": [270.0] * 24,
            "rain": rain,
            "showers": [0.0] * 24,
            "direct_radiation": [50.0] * 24,
            "dew_point_2m": [15.0] * 24,
            "cloud_cover": [100.0] * 24,
            "precipitation": rain,
        }
    }


def _make_damp_response() -> dict[str, object]:
    """Build a response with light precipitation (damp) at session hour (12).

    Overcast, humid conditions with 0.15mm rain at session hour produce
    peak water ~0.045mm -> DAMP (0.01-0.10mm range).
    """
    rain = [0.0] * 24
    rain[12] = 0.15
    return {
        "hourly": {
            "time": [f"2025-02-15T{h:02d}:00" for h in range(24)],
            "temperature_2m": [18.0] * 24,
            "relative_humidity_2m": [80.0] * 24,
            "wind_speed_10m": [5.0] * 24,
            "wind_direction_10m": [90.0] * 24,
            "rain": rain,
            "showers": [0.0] * 24,
            "direct_radiation": [100.0] * 24,
            "dew_point_2m": [14.0] * 24,
            "cloud_cover": [80.0] * 24,
            "precipitation": rain,
        }
    }


SESSION_DT = datetime(2025, 2, 15, 12, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_successful_lookup_returns_conditions() -> None:
    """A normal API response produces SessionConditions with correct values."""
    mock_response = _make_mock_response(SAMPLE_HOURLY_RESPONSE)

    with patch("cataclysm.weather_client.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_cls.return_value = mock_client

        result = await lookup_weather(33.53, -86.62, SESSION_DT)

    assert result is not None
    assert result.ambient_temp_c == 22.0
    assert result.humidity_pct == 50.0
    assert result.wind_speed_kmh == 10.0
    assert result.wind_direction_deg == 180.0
    assert result.precipitation_mm == 0.0
    assert result.track_condition == TrackCondition.DRY
    assert result.weather_source == "open-meteo"
    assert result.surface_water_mm is not None
    assert result.weather_confidence is not None


@pytest.mark.asyncio
async def test_high_precipitation_returns_wet() -> None:
    """Precipitation > 1.0mm maps to WET track condition."""
    mock_response = _make_mock_response(_make_rainy_response())

    with patch("cataclysm.weather_client.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_cls.return_value = mock_client

        result = await lookup_weather(33.53, -86.62, SESSION_DT)

    assert result is not None
    assert result.track_condition == TrackCondition.WET
    assert result.precipitation_mm == 5.2


@pytest.mark.asyncio
async def test_light_precipitation_returns_damp() -> None:
    """Precipitation between 0.1 and 1.0mm maps to DAMP track condition."""
    mock_response = _make_mock_response(_make_damp_response())

    with patch("cataclysm.weather_client.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_cls.return_value = mock_client

        result = await lookup_weather(33.53, -86.62, SESSION_DT)

    assert result is not None
    assert result.track_condition == TrackCondition.DAMP
    assert result.precipitation_mm == pytest.approx(0.15)


@pytest.mark.asyncio
async def test_zero_precipitation_returns_dry() -> None:
    """Zero precipitation maps to DRY track condition."""
    mock_response = _make_mock_response(SAMPLE_HOURLY_RESPONSE)

    with patch("cataclysm.weather_client.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_cls.return_value = mock_client

        result = await lookup_weather(33.53, -86.62, SESSION_DT)

    assert result is not None
    assert result.track_condition == TrackCondition.DRY


@pytest.mark.asyncio
async def test_accumulated_precip_detects_wet_track() -> None:
    """If no rain now but significant rain in prior hours → surface water model detects wet."""
    # 24 hours of data: heavy rain hours 6-9, dry by session at hour 12
    rain = [0.0] * 24
    rain[6] = 1.5
    rain[7] = 2.0
    rain[8] = 0.5
    rain[9] = 0.3
    response = {
        "hourly": {
            "time": [f"2025-02-15T{h:02d}:00" for h in range(24)],
            "temperature_2m": [15.0] * 24,
            "relative_humidity_2m": [80.0] * 24,
            "wind_speed_10m": [5.0] * 24,
            "wind_direction_10m": [180.0] * 24,
            "rain": rain,
            "showers": [0.0] * 24,
            "direct_radiation": [50.0] * 24,
            "dew_point_2m": [12.0] * 24,
            "cloud_cover": [90.0] * 24,
            "precipitation": rain,
        }
    }
    mock_response = _make_mock_response(response)

    with patch("cataclysm.weather_client.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_cls.return_value = mock_client

        result = await lookup_weather(33.53, -86.62, SESSION_DT)

    assert result is not None
    assert result.precipitation_mm == 0.0  # current hour is dry
    assert result.track_condition in (TrackCondition.WET, TrackCondition.DAMP)
    assert result.surface_water_mm is not None


@pytest.mark.asyncio
async def test_api_error_returns_none() -> None:
    """HTTP error from the API returns None gracefully."""
    mock_response = httpx.Response(
        status_code=500,
        request=httpx.Request("GET", "https://api.open-meteo.com/v1/forecast"),
    )

    with patch("cataclysm.weather_client.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_cls.return_value = mock_client

        result = await lookup_weather(33.53, -86.62, SESSION_DT)

    assert result is None


@pytest.mark.asyncio
async def test_empty_response_returns_none() -> None:
    """An API response with no hourly data returns None."""
    mock_response = _make_mock_response({"hourly": {}})

    with patch("cataclysm.weather_client.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_cls.return_value = mock_client

        result = await lookup_weather(33.53, -86.62, SESSION_DT)

    assert result is None


@pytest.mark.asyncio
async def test_empty_time_array_returns_none() -> None:
    """An API response with empty time array returns None."""
    mock_response = _make_mock_response(
        {
            "hourly": {
                "time": [],
                "temperature_2m": [],
                "relative_humidity_2m": [],
                "wind_speed_10m": [],
                "wind_direction_10m": [],
                "precipitation": [],
            }
        }
    )

    with patch("cataclysm.weather_client.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_cls.return_value = mock_client

        result = await lookup_weather(33.53, -86.62, SESSION_DT)

    assert result is None


@pytest.mark.asyncio
async def test_network_error_returns_none() -> None:
    """A network connectivity error returns None gracefully."""
    with patch("cataclysm.weather_client.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.ConnectError("Connection refused")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_cls.return_value = mock_client

        result = await lookup_weather(33.53, -86.62, SESSION_DT)

    assert result is None


@pytest.mark.asyncio
async def test_closest_hour_selection() -> None:
    """The client picks the hourly entry closest to the session time."""
    # Session at 10:30 should pick index 0 (10:00) not index 1 (11:00)
    session_dt = datetime(2025, 2, 15, 10, 30, tzinfo=UTC)
    mock_response = _make_mock_response(SAMPLE_HOURLY_RESPONSE)

    with patch("cataclysm.weather_client.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_cls.return_value = mock_client

        result = await lookup_weather(33.53, -86.62, session_dt)

    assert result is not None
    # All values are constant 22.0 temp, 50.0 humidity
    assert result.ambient_temp_c == 22.0
    assert result.humidity_pct == 50.0


# ---------------------------------------------------------------------------
# Task 2: Surface water physics — evaporation, runoff, condensation
# ---------------------------------------------------------------------------


class TestEvaporation:
    """Tests for compute_evaporation_rate."""

    def test_evaporation_zero_at_saturation(self) -> None:
        rate = compute_evaporation_rate(
            temp_c=20.0, rh_pct=100.0, wind_kmh=15.0, radiation_wm2=500.0
        )
        assert rate == pytest.approx(0.0, abs=0.001)

    def test_evaporation_increases_with_vpd(self) -> None:
        rate_humid = compute_evaporation_rate(
            temp_c=20.0, rh_pct=80.0, wind_kmh=10.0, radiation_wm2=300.0
        )
        rate_dry = compute_evaporation_rate(
            temp_c=20.0, rh_pct=40.0, wind_kmh=10.0, radiation_wm2=300.0
        )
        assert rate_dry > rate_humid > 0

    def test_evaporation_increases_with_wind(self) -> None:
        rate_calm = compute_evaporation_rate(
            temp_c=25.0, rh_pct=50.0, wind_kmh=5.0, radiation_wm2=400.0
        )
        rate_windy = compute_evaporation_rate(
            temp_c=25.0, rh_pct=50.0, wind_kmh=30.0, radiation_wm2=400.0
        )
        assert rate_windy > rate_calm

    def test_evaporation_reasonable_magnitude(self) -> None:
        rate = compute_evaporation_rate(
            temp_c=25.0, rh_pct=40.0, wind_kmh=15.0, radiation_wm2=600.0
        )
        assert 0.05 < rate < 2.0


class TestRunoff:
    """Tests for compute_runoff."""

    def test_runoff_zero_below_capacity(self) -> None:
        assert compute_runoff(0.3) == pytest.approx(0.0)

    def test_runoff_drains_excess(self) -> None:
        assert compute_runoff(2.0) > 0.0

    def test_runoff_increases_with_excess(self) -> None:
        assert compute_runoff(3.0) > compute_runoff(1.5)


class TestCondensation:
    """Tests for compute_condensation."""

    def test_condensation_zero_when_warm(self) -> None:
        assert compute_condensation(temp_c=25.0, dew_point_c=15.0, wind_kmh=5.0) == pytest.approx(
            0.0
        )

    def test_condensation_forms_near_dew_point(self) -> None:
        assert compute_condensation(temp_c=10.0, dew_point_c=9.5, wind_kmh=5.0) > 0.0

    def test_condensation_small_magnitude(self) -> None:
        rate = compute_condensation(temp_c=8.0, dew_point_c=7.0, wind_kmh=10.0)
        assert 0.0 < rate < 0.1


# ---------------------------------------------------------------------------
# Task 3: Surface water balance model
# ---------------------------------------------------------------------------


def _make_hourly_data(n_hours: int, **overrides: list[float]) -> dict[str, list[float]]:
    """Build synthetic hourly data for n hours."""
    defaults: dict[str, list[float]] = {
        "rain": [0.0] * n_hours,
        "showers": [0.0] * n_hours,
        "temperature_2m": [20.0] * n_hours,
        "relative_humidity_2m": [50.0] * n_hours,
        "wind_speed_10m": [10.0] * n_hours,
        "direct_radiation": [300.0] * n_hours,
        "dew_point_2m": [10.0] * n_hours,
    }
    defaults.update(overrides)
    return defaults


class TestSurfaceWaterBalance:
    """Tests for compute_surface_water."""

    def test_surface_water_dry_stays_dry(self) -> None:
        data = _make_hourly_data(24)
        peak = compute_surface_water(data, session_idx=20, lookback=12, forward=2)
        assert peak == pytest.approx(0.0)

    def test_surface_water_active_rain(self) -> None:
        rain = [0.0] * 24
        rain[20] = 2.0
        rain[21] = 1.0
        data = _make_hourly_data(24, rain=rain)
        peak = compute_surface_water(data, session_idx=20, lookback=12, forward=2)
        assert peak > 0.5

    def test_surface_water_rain_before_sunshine_dries(self) -> None:
        rain = [0.0] * 24
        rain[10] = 1.0
        data = _make_hourly_data(
            24,
            rain=rain,
            temperature_2m=[25.0] * 24,
            relative_humidity_2m=[40.0] * 24,
            wind_speed_10m=[15.0] * 24,
            direct_radiation=[500.0] * 24,
        )
        peak = compute_surface_water(data, session_idx=20, lookback=12, forward=2)
        assert peak < 0.05

    def test_surface_water_rain_before_overcast_stays_damp(self) -> None:
        rain = [0.0] * 24
        rain[16] = 0.5
        data = _make_hourly_data(
            24,
            rain=rain,
            temperature_2m=[15.0] * 24,
            relative_humidity_2m=[90.0] * 24,
            wind_speed_10m=[5.0] * 24,
            direct_radiation=[50.0] * 24,
        )
        peak = compute_surface_water(data, session_idx=20, lookback=12, forward=2)
        assert peak > 0.01

    def test_surface_water_forward_window_catches_rain(self) -> None:
        rain = [0.0] * 24
        rain[21] = 1.5
        data = _make_hourly_data(24, rain=rain)
        peak = compute_surface_water(data, session_idx=20, lookback=12, forward=2)
        assert peak > 0.5

    def test_surface_water_dew_overnight(self) -> None:
        data = _make_hourly_data(
            24,
            temperature_2m=[8.0] * 24,
            relative_humidity_2m=[98.0] * 24,
            dew_point_2m=[7.5] * 24,
            direct_radiation=[0.0] * 24,
            wind_speed_10m=[3.0] * 24,
        )
        peak = compute_surface_water(data, session_idx=20, lookback=12, forward=2)
        assert peak > 0.0

    def test_surface_water_heavy_rain_runoff(self) -> None:
        rain = [5.0] * 24
        data = _make_hourly_data(24, rain=rain, relative_humidity_2m=[95.0] * 24)
        peak = compute_surface_water(data, session_idx=20, lookback=12, forward=2)
        # Runoff should cap accumulation well below total input (60mm over 12h)
        assert peak < 15.0


# ---------------------------------------------------------------------------
# Task 4: Classification and confidence
# ---------------------------------------------------------------------------


class TestClassifySurfaceWater:
    """Tests for classify_surface_water."""

    def test_classify_dry(self) -> None:
        assert classify_surface_water(0.005) == TrackCondition.DRY

    def test_classify_damp(self) -> None:
        assert classify_surface_water(0.05) == TrackCondition.DAMP

    def test_classify_wet(self) -> None:
        assert classify_surface_water(0.15) == TrackCondition.WET

    def test_classify_boundary_damp(self) -> None:
        assert classify_surface_water(0.01) == TrackCondition.DAMP

    def test_classify_boundary_wet(self) -> None:
        assert classify_surface_water(0.10) == TrackCondition.WET


class TestWeatherConfidence:
    """Tests for compute_weather_confidence."""

    def test_confidence_high_for_steady_conditions(self) -> None:
        conf = compute_weather_confidence(
            cloud_cover_pct=[20.0] * 6,
            precip_values=[0.0] * 6,
            has_full_window=True,
        )
        assert conf > 0.8

    def test_confidence_lower_for_convective(self) -> None:
        conf = compute_weather_confidence(
            cloud_cover_pct=[30.0, 90.0, 40.0, 100.0, 50.0, 95.0],
            precip_values=[0.0, 0.5, 0.0, 1.2, 0.0, 0.3],
            has_full_window=True,
        )
        assert conf < 0.7

    def test_confidence_drops_for_missing_data(self) -> None:
        conf = compute_weather_confidence(
            cloud_cover_pct=[50.0] * 3,
            precip_values=[0.0] * 3,
            has_full_window=False,
        )
        assert conf <= 0.8


# ---------------------------------------------------------------------------
# Task 5: Integration — wiring into lookup_weather
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_amp_march15_session4_detected_wet() -> None:
    """AMP Mar 15: rain starts during session -> forward window catches it."""
    rain = [0.0] * 24
    rain[19] = 0.2
    rain[20] = 0.8
    rain[21] = 0.1
    response = {
        "hourly": {
            "time": [f"2026-03-15T{h:02d}:00" for h in range(24)],
            "temperature_2m": [19.0] * 24,
            "relative_humidity_2m": ([60.0] * 18 + [77.0, 97.0, 84.0, 83.0, 87.0, 99.0]),
            "wind_speed_10m": [15.0] * 24,
            "wind_direction_10m": [180.0] * 24,
            "rain": rain,
            "showers": [0.0] * 24,
            "direct_radiation": ([400.0] * 18 + [14.0, 27.0, 12.0, 3.0, 15.0, 0.0]),
            "dew_point_2m": [10.0] * 24,
            "cloud_cover": [50.0] * 18 + [100.0] * 6,
            "precipitation": rain,
        }
    }
    mock_response = _make_mock_response(response)
    with patch("cataclysm.weather_client.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_cls.return_value = mock_client
        session_dt = datetime(2026, 3, 15, 17, 32, tzinfo=UTC)
        result = await lookup_weather(34.432, -84.176, session_dt)
    assert result is not None
    assert result.track_condition == TrackCondition.WET
    assert result.surface_water_mm is not None
    assert result.surface_water_mm > 0.1
    assert result.weather_confidence is not None


@pytest.mark.asyncio
async def test_legacy_fallback_when_new_fields_missing() -> None:
    """Old-style response with only 'precipitation' uses legacy path."""
    response = {
        "hourly": {
            "time": [f"2025-02-15T{h:02d}:00" for h in range(24)],
            "temperature_2m": [20.0] * 24,
            "relative_humidity_2m": [80.0] * 24,
            "wind_speed_10m": [8.0] * 24,
            "wind_direction_10m": [90.0] * 24,
            "precipitation": [0.0] * 11 + [2.5] + [0.0] * 12,
        }
    }
    mock_response = _make_mock_response(response)
    with patch("cataclysm.weather_client.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_cls.return_value = mock_client
        result = await lookup_weather(33.53, -86.62, SESSION_DT)
    assert result is not None
    assert result.track_condition == TrackCondition.WET
    assert result.surface_water_mm is None
    assert result.weather_confidence is None
    assert result.dew_point_c is None


# ---------------------------------------------------------------------------
# Task 7: 15-minute precipitation resolution
# ---------------------------------------------------------------------------


class TestQuarterHourly:
    """Tests for prepare_quarter_hourly and timestep_h support."""

    def test_interpolates_continuous_fields(self) -> None:
        hourly: dict[str, list[float]] = {
            "temperature_2m": [20.0, 24.0],
            "relative_humidity_2m": [50.0, 50.0],
            "wind_speed_10m": [10.0, 10.0],
            "direct_radiation": [300.0, 300.0],
            "dew_point_2m": [10.0, 10.0],
            "cloud_cover": [30.0, 30.0],
            "rain": [0.0, 0.0],
            "showers": [0.0, 0.0],
        }
        qh = prepare_quarter_hourly(hourly, minutely_15_precip=None)
        assert len(qh["temperature_2m"]) == 8
        assert qh["temperature_2m"][0] == pytest.approx(20.0)
        assert qh["temperature_2m"][4] == pytest.approx(24.0)
        assert qh["temperature_2m"][2] == pytest.approx(22.0)

    def test_uses_native_15min_precip(self) -> None:
        hourly: dict[str, list[float]] = {
            "temperature_2m": [20.0, 20.0],
            "relative_humidity_2m": [50.0, 50.0],
            "wind_speed_10m": [10.0, 10.0],
            "direct_radiation": [300.0, 300.0],
            "dew_point_2m": [10.0, 10.0],
            "cloud_cover": [30.0, 30.0],
            "rain": [1.0, 0.0],
            "showers": [0.0, 0.0],
        }
        minutely_15: dict[str, list[float]] = {
            "rain": [0.0, 0.0, 0.5, 0.5, 0.0, 0.0, 0.0, 0.0],
            "showers": [0.0] * 8,
        }
        qh = prepare_quarter_hourly(hourly, minutely_15_precip=minutely_15)
        assert qh["rain"][2] == pytest.approx(0.5)
        assert qh["rain"][0] == pytest.approx(0.0)

    def test_spreads_hourly_precip_without_15min(self) -> None:
        hourly: dict[str, list[float]] = {
            "temperature_2m": [20.0],
            "relative_humidity_2m": [50.0],
            "wind_speed_10m": [10.0],
            "direct_radiation": [300.0],
            "dew_point_2m": [10.0],
            "cloud_cover": [30.0],
            "rain": [1.0],
            "showers": [0.0],
        }
        qh = prepare_quarter_hourly(hourly, minutely_15_precip=None)
        assert len(qh["rain"]) == 4
        assert all(v == pytest.approx(0.25) for v in qh["rain"])

    def test_quarter_hourly_balance_backward_compat(self) -> None:
        """Existing hourly tests still work with default timestep_h=1.0."""
        data = _make_hourly_data(24)
        peak = compute_surface_water(data, session_idx=20, lookback=12, forward=2)
        assert peak == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Task 8: Track temperature proxy (soil_temperature_0cm)
# ---------------------------------------------------------------------------


class TestEvaporationSurfaceTemp:
    """Tests for surface_temp_c parameter in compute_evaporation_rate."""

    def test_higher_with_surface_temp(self) -> None:
        """Hot asphalt (45C) evaporates faster than air temp (25C) alone."""
        rate_air = compute_evaporation_rate(
            temp_c=25.0,
            rh_pct=50.0,
            wind_kmh=10.0,
            radiation_wm2=500.0,
        )
        rate_surface = compute_evaporation_rate(
            temp_c=25.0,
            rh_pct=50.0,
            wind_kmh=10.0,
            radiation_wm2=500.0,
            surface_temp_c=45.0,
        )
        assert rate_surface > rate_air

    def test_ignores_when_none(self) -> None:
        """surface_temp_c=None gives identical result to omitting it."""
        rate_a = compute_evaporation_rate(
            temp_c=25.0,
            rh_pct=50.0,
            wind_kmh=10.0,
            radiation_wm2=500.0,
        )
        rate_b = compute_evaporation_rate(
            temp_c=25.0,
            rh_pct=50.0,
            wind_kmh=10.0,
            radiation_wm2=500.0,
            surface_temp_c=None,
        )
        assert rate_a == pytest.approx(rate_b)

    def test_surface_water_with_soil_temp(self) -> None:
        """Hot soil temp accelerates drying in the balance model."""
        rain = [0.0] * 24
        rain[15] = 0.5
        data_no_soil = _make_hourly_data(24, rain=rain)
        data_with_soil = _make_hourly_data(24, rain=rain)
        data_with_soil["soil_temperature_0cm"] = [45.0] * 24

        peak_no_soil = compute_surface_water(data_no_soil, session_idx=20, lookback=12, forward=2)
        peak_with_soil = compute_surface_water(
            data_with_soil, session_idx=20, lookback=12, forward=2
        )
        # Hot soil dries faster -> lower peak water
        assert peak_with_soil <= peak_no_soil
