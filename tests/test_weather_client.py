"""Tests for the Open-Meteo weather client."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from cataclysm.equipment import TrackCondition
from cataclysm.weather_client import lookup_weather

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_HOURLY_RESPONSE: dict[str, object] = {
    "hourly": {
        "time": [
            "2025-02-15T10:00",
            "2025-02-15T11:00",
            "2025-02-15T12:00",
            "2025-02-15T13:00",
        ],
        "temperature_2m": [22.0, 24.0, 25.0, 24.5],
        "relative_humidity_2m": [55.0, 58.0, 60.0, 62.0],
        "wind_speed_10m": [10.0, 12.0, 15.0, 14.0],
        "wind_direction_10m": [170.0, 175.0, 180.0, 185.0],
        "precipitation": [0.0, 0.0, 0.0, 0.0],
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
    """Build a response with heavy precipitation."""
    return {
        "hourly": {
            "time": ["2025-02-15T12:00"],
            "temperature_2m": [18.0],
            "relative_humidity_2m": [90.0],
            "wind_speed_10m": [25.0],
            "wind_direction_10m": [270.0],
            "precipitation": [5.2],
        }
    }


def _make_damp_response() -> dict[str, object]:
    """Build a response with light precipitation (damp)."""
    return {
        "hourly": {
            "time": ["2025-02-15T12:00"],
            "temperature_2m": [20.0],
            "relative_humidity_2m": [80.0],
            "wind_speed_10m": [8.0],
            "wind_direction_10m": [90.0],
            "precipitation": [0.5],
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
    assert result.ambient_temp_c == 25.0
    assert result.humidity_pct == 60.0
    assert result.wind_speed_kmh == 15.0
    assert result.wind_direction_deg == 180.0
    assert result.precipitation_mm == 0.0
    assert result.track_condition == TrackCondition.DRY
    assert result.weather_source == "open-meteo"


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
    assert result.precipitation_mm == 0.5


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
    # Index 0 values: temp=22.0, humidity=55.0 (closest to 10:30)
    assert result.ambient_temp_c == 22.0
    assert result.humidity_pct == 55.0
