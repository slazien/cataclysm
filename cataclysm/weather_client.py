"""Async client for the Open-Meteo weather API.

Fetches historical or forecast weather data for a given GPS coordinate and
datetime, then maps it to a :class:`~cataclysm.equipment.SessionConditions`
dataclass.  The API is free and requires no API key.

Two endpoints are used depending on session age:
- **Forecast** (``api.open-meteo.com``) for sessions within the last ~16 days.
- **Historical** (``archive-api.open-meteo.com``) for older sessions.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

import httpx

from cataclysm.equipment import SessionConditions, TrackCondition

logger = logging.getLogger(__name__)

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
REQUEST_TIMEOUT_S = 10.0
FORECAST_WINDOW_DAYS = 16

HOURLY_PARAMS = (
    "temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m,precipitation"
)


def _pick_api_url(session_dt: datetime) -> str:
    """Return the forecast or archive URL based on session age."""
    now = datetime.now(UTC)
    if (now - session_dt) <= timedelta(days=FORECAST_WINDOW_DAYS):
        return FORECAST_URL
    return ARCHIVE_URL


def _infer_track_condition(precipitation_mm: float) -> TrackCondition:
    """Map precipitation to a track surface condition."""
    if precipitation_mm > 1.0:
        return TrackCondition.WET
    if precipitation_mm > 0.1:
        return TrackCondition.DAMP
    return TrackCondition.DRY


def _find_closest_hour_index(times: list[str], target: datetime) -> int:
    """Return the index of the hourly timestamp closest to *target*."""
    best_idx = 0
    best_diff = float("inf")
    for i, t in enumerate(times):
        # Open-Meteo returns ISO timestamps without timezone
        dt = datetime.fromisoformat(t).replace(tzinfo=UTC)
        diff = abs((dt - target).total_seconds())
        if diff < best_diff:
            best_diff = diff
            best_idx = i
    return best_idx


async def lookup_weather(
    lat: float,
    lon: float,
    session_datetime: datetime,
) -> SessionConditions | None:
    """Look up weather conditions for a GPS location and datetime.

    Queries the Open-Meteo API (forecast or historical archive depending
    on session age) and returns a populated
    :class:`~cataclysm.equipment.SessionConditions`, or ``None`` on any
    error.

    Args:
        lat: Latitude in decimal degrees.
        lon: Longitude in decimal degrees.
        session_datetime: The UTC datetime of the session.

    Returns:
        A :class:`SessionConditions` with weather data, or ``None`` if the
        lookup failed.
    """
    api_url = _pick_api_url(session_datetime)
    date_str = session_datetime.strftime("%Y-%m-%d")
    params = {
        "latitude": str(lat),
        "longitude": str(lon),
        "hourly": HOURLY_PARAMS,
        "start_date": date_str,
        "end_date": date_str,
        "timezone": "UTC",
    }

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_S) as client:
            response = await client.get(api_url, params=params)
            response.raise_for_status()

        data = response.json()
        hourly = data.get("hourly")
        if not hourly or not hourly.get("time"):
            logger.warning("Open-Meteo returned empty hourly data for %s", date_str)
            return None

        idx = _find_closest_hour_index(hourly["time"], session_datetime)

        temp_c = hourly["temperature_2m"][idx]
        humidity = hourly["relative_humidity_2m"][idx]
        wind_speed = hourly["wind_speed_10m"][idx]
        wind_dir = hourly["wind_direction_10m"][idx]
        precip = hourly["precipitation"][idx]

        return SessionConditions(
            track_condition=_infer_track_condition(precip),
            ambient_temp_c=float(temp_c),
            humidity_pct=float(humidity),
            wind_speed_kmh=float(wind_speed),
            wind_direction_deg=float(wind_dir),
            precipitation_mm=float(precip),
            weather_source="open-meteo",
        )

    except httpx.HTTPStatusError as exc:
        logger.warning(
            "Open-Meteo API returned status %d for lat=%s lon=%s date=%s",
            exc.response.status_code,
            lat,
            lon,
            date_str,
        )
        return None
    except (httpx.RequestError, ValueError, KeyError, IndexError, TypeError) as exc:
        logger.warning(
            "Open-Meteo lookup failed for lat=%s lon=%s date=%s: %s",
            lat,
            lon,
            date_str,
            exc,
        )
        return None
