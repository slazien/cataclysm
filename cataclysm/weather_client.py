"""Async client for the Open-Meteo weather API.

Fetches historical or forecast weather data for a given GPS coordinate and
datetime, then classifies the track surface condition (dry/damp/wet) using
a physics-based surface water balance model.

The model tracks effective surface water as a time series over a 12-hour
lookback + 2-hour forward window, accounting for:
- Precipitation (rain + showers)
- Evaporation (bulk-transfer: VPD x wind + radiation boost)
- Runoff (exponential drainage above asphalt holding capacity)
- Condensation (dew formation when near dew point)

Two endpoints are used depending on session age:
- **Forecast** (``api.open-meteo.com``) for sessions within the last ~16 days.
- **Historical** (``archive-api.open-meteo.com``) for older sessions.

Falls back to legacy precipitation-threshold classification when the API
response lacks the required fields (rain, showers, dew_point_2m,
direct_radiation).
"""

from __future__ import annotations

import logging
import math
from datetime import UTC, datetime, timedelta

import httpx

from cataclysm.equipment import SessionConditions, TrackCondition

logger = logging.getLogger(__name__)

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
REQUEST_TIMEOUT_S = 10.0
FORECAST_WINDOW_DAYS = 16

HOURLY_PARAMS = (
    "temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m,"
    "rain,showers,direct_radiation,dew_point_2m,cloud_cover"
)

# --- Legacy fallback constants (used when new API fields unavailable) ---
LOOKBACK_HOURS = 6
ACCUMULATED_WET_MM = 2.0
ACCUMULATED_DAMP_MM = 0.5
INSTANT_WET_MM = 1.0
INSTANT_DAMP_MM = 0.1

# ---------------------------------------------------------------------------
# Surface water model constants
# ---------------------------------------------------------------------------
_AERO_COEFF = 0.013  # aerodynamic transfer coefficient (tuned for asphalt)
_RAD_COEFF = 0.0015  # radiation-enhanced evaporation coefficient
_MIN_WIND_MS = 0.5  # minimum turbulent mixing (m/s)

_HOLDING_CAPACITY_MM = 0.8  # thin film asphalt can hold before drainage
_RUNOFF_RATE = 0.5  # fraction of excess that drains per hour

_DEW_SPREAD_THRESHOLD_C = 2.0
_DEW_COEFF = 0.008


# ---------------------------------------------------------------------------
# Surface water physics — pure functions
# ---------------------------------------------------------------------------


def compute_evaporation_rate(
    temp_c: float,
    rh_pct: float,
    wind_kmh: float,
    radiation_wm2: float,
) -> float:
    """Bulk-transfer evaporation rate from wet asphalt (mm/hr).

    Based on Penman aerodynamic term: E = C * u * VPD, plus a
    radiation enhancement term. VPD (vapor pressure deficit) is the
    difference between saturation and actual vapor pressure -- when
    humidity is 100%, VPD=0 and evaporation stops.

    Returns >= 0.0; cannot produce negative (condensation is separate).
    """
    # Tetens formula: saturation vapor pressure (hPa)
    e_s = 6.1078 * math.exp(17.27 * temp_c / (temp_c + 237.3))
    e_a = e_s * (rh_pct / 100.0)
    vpd = max(0.0, e_s - e_a)

    wind_ms = max(_MIN_WIND_MS, wind_kmh / 3.6)
    rad = max(0.0, radiation_wm2)

    aero = _AERO_COEFF * wind_ms * vpd
    rad_boost = _RAD_COEFF * rad * vpd / max(e_s, 1.0)
    return aero + rad_boost


def compute_runoff(surface_water_mm: float) -> float:
    """Exponential drainage above asphalt holding capacity (mm/hr)."""
    if surface_water_mm <= _HOLDING_CAPACITY_MM:
        return 0.0
    excess = surface_water_mm - _HOLDING_CAPACITY_MM
    return excess * _RUNOFF_RATE


def compute_condensation(
    temp_c: float,
    dew_point_c: float,
    wind_kmh: float,
) -> float:
    """Dew deposition rate when near saturation (mm/hr)."""
    spread = temp_c - dew_point_c
    if spread >= _DEW_SPREAD_THRESHOLD_C:
        return 0.0
    wind_ms = max(_MIN_WIND_MS, wind_kmh / 3.6)
    fraction = 1.0 - spread / _DEW_SPREAD_THRESHOLD_C
    return _DEW_COEFF * wind_ms * fraction


# ---------------------------------------------------------------------------
# Surface water balance model
# ---------------------------------------------------------------------------


def compute_surface_water(
    hourly: dict[str, list[float]],
    session_idx: int,
    lookback: int = 12,
    forward: int = 2,
) -> float:
    """Compute peak surface water (mm) during the session window.

    Steps hourly through (session_idx - lookback) to (session_idx + forward),
    maintaining W(t) = max(0, W(t-1) + precipitation + condensation
                              - evaporation - runoff).
    Returns max W observed during session window (indices >= session_idx).
    """
    n = len(hourly["rain"])
    start = max(0, session_idx - lookback)
    end = min(n, session_idx + forward + 1)

    water = 0.0
    peak_session = 0.0

    for i in range(start, end):
        precip = float(hourly["rain"][i]) + float(hourly.get("showers", [0.0] * n)[i])
        evap = compute_evaporation_rate(
            temp_c=float(hourly["temperature_2m"][i]),
            rh_pct=float(hourly["relative_humidity_2m"][i]),
            wind_kmh=float(hourly["wind_speed_10m"][i]),
            radiation_wm2=float(hourly["direct_radiation"][i]),
        )
        cond = compute_condensation(
            temp_c=float(hourly["temperature_2m"][i]),
            dew_point_c=float(hourly["dew_point_2m"][i]),
            wind_kmh=float(hourly["wind_speed_10m"][i]),
        )
        ro = compute_runoff(water)
        water = max(0.0, water + precip + cond - evap - ro)
        if i >= session_idx:
            peak_session = max(peak_session, water)

    return round(peak_session, 4)


# ---------------------------------------------------------------------------
# Classification and confidence
# ---------------------------------------------------------------------------

_WET_THRESHOLD_MM = 0.10
_DAMP_THRESHOLD_MM = 0.01


def classify_surface_water(peak_water_mm: float) -> TrackCondition:
    """Map peak surface water film thickness to track condition."""
    if peak_water_mm >= _WET_THRESHOLD_MM:
        return TrackCondition.WET
    if peak_water_mm >= _DAMP_THRESHOLD_MM:
        return TrackCondition.DAMP
    return TrackCondition.DRY


def compute_weather_confidence(
    cloud_cover_pct: list[float],
    precip_values: list[float],
    has_full_window: bool,
) -> float:
    """Estimate reliability of the surface water classification (0-1)."""
    conf = 1.0

    # Cloud variability penalty
    if len(cloud_cover_pct) >= 3:
        mean = sum(cloud_cover_pct) / len(cloud_cover_pct)
        variance = sum((x - mean) ** 2 for x in cloud_cover_pct) / len(cloud_cover_pct)
        cloud_std = variance**0.5
        conf -= min(0.3, cloud_std / 100.0)

    # Patchy precipitation penalty
    if precip_values:
        n_rainy = sum(1 for p in precip_values if p > 0.05)
        n_total = len(precip_values)
        if 0 < n_rainy < n_total:
            rain_fraction = n_rainy / n_total
            patchiness = 4 * rain_fraction * (1 - rain_fraction)
            conf -= 0.2 * patchiness

    # Missing data penalty
    if not has_full_window:
        conf -= 0.2

    return round(max(0.0, min(1.0, conf)), 2)


def _pick_api_url(session_dt: datetime) -> str:
    """Return the forecast or archive URL based on session age."""
    now = datetime.now(UTC)
    if (now - session_dt) <= timedelta(days=FORECAST_WINDOW_DAYS):
        return FORECAST_URL
    return ARCHIVE_URL


# --- Legacy fallback (used when new API fields unavailable) ---


def _infer_track_condition(
    current_precip_mm: float,
    accumulated_precip_mm: float,
) -> TrackCondition:
    """Map precipitation to a track surface condition.

    Uses both the current-hour reading and accumulated precipitation
    over the lookback window to catch "rain stopped but track still wet".
    """
    # Current-hour takes priority for active rain
    if current_precip_mm > INSTANT_WET_MM:
        return TrackCondition.WET
    if current_precip_mm > INSTANT_DAMP_MM:
        return TrackCondition.DAMP

    # Lookback: recent accumulated rain → track surface still wet
    if accumulated_precip_mm > ACCUMULATED_WET_MM:
        return TrackCondition.WET
    if accumulated_precip_mm > ACCUMULATED_DAMP_MM:
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


def _sum_lookback_precipitation(
    precip_values: list[float],
    session_idx: int,
    lookback_hours: int,
) -> float:
    """Sum precipitation over the *lookback_hours* ending at *session_idx*."""
    start_idx = max(0, session_idx - lookback_hours)
    return sum(float(precip_values[i]) for i in range(start_idx, session_idx + 1))


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

    The query fetches the session day *plus* the preceding day so that
    early-morning sessions have enough lookback data for accumulated
    precipitation.

    Args:
        lat: Latitude in decimal degrees.
        lon: Longitude in decimal degrees.
        session_datetime: The UTC datetime of the session.

    Returns:
        A :class:`SessionConditions` with weather data, or ``None`` if the
        lookup failed.
    """
    api_url = _pick_api_url(session_datetime)
    # Fetch two days: previous day + session day for lookback window
    prev_day = (session_datetime - timedelta(days=1)).strftime("%Y-%m-%d")
    session_day = session_datetime.strftime("%Y-%m-%d")
    params = {
        "latitude": str(lat),
        "longitude": str(lon),
        "hourly": HOURLY_PARAMS,
        "start_date": prev_day,
        "end_date": session_day,
        "timezone": "UTC",
    }

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_S) as client:
            response = await client.get(api_url, params=params)
            response.raise_for_status()

        data = response.json()
        hourly = data.get("hourly")
        if not hourly or not hourly.get("time"):
            logger.warning("Open-Meteo returned empty hourly data for %s", session_day)
            return None

        idx = _find_closest_hour_index(hourly["time"], session_datetime)
        n_hours = len(hourly["time"])
        has_full_window = idx >= 12 and idx + 2 < n_hours

        # Prefer new model (rain+showers); fall back to legacy (precipitation)
        if "rain" in hourly and "dew_point_2m" in hourly and "direct_radiation" in hourly:
            # Build hourly dict with float lists for the balance model
            hourly_floats: dict[str, list[float]] = {
                "rain": [float(v) for v in hourly["rain"]],
                "showers": [float(v) for v in hourly.get("showers", [0.0] * n_hours)],
                "temperature_2m": [float(v) for v in hourly["temperature_2m"]],
                "relative_humidity_2m": [float(v) for v in hourly["relative_humidity_2m"]],
                "wind_speed_10m": [float(v) for v in hourly["wind_speed_10m"]],
                "direct_radiation": [float(v) for v in hourly["direct_radiation"]],
                "dew_point_2m": [float(v) for v in hourly["dew_point_2m"]],
            }

            peak_water = compute_surface_water(hourly_floats, idx, lookback=12, forward=2)
            condition = classify_surface_water(peak_water)

            # Confidence from session window (session hour +/- 3)
            win_start = max(0, idx - 3)
            win_end = min(n_hours, idx + 4)
            cloud_win = [
                float(v) for v in hourly.get("cloud_cover", [50.0] * n_hours)[win_start:win_end]
            ]
            precip_win = [
                hourly_floats["rain"][i] + hourly_floats["showers"][i]
                for i in range(win_start, win_end)
            ]
            confidence = compute_weather_confidence(cloud_win, precip_win, has_full_window)

            current_precip = hourly_floats["rain"][idx] + hourly_floats["showers"][idx]
            dew_pt: float | None = float(hourly["dew_point_2m"][idx])
        else:
            # Legacy fallback
            logger.info("Falling back to legacy precipitation classification")
            current_precip = float(hourly.get("precipitation", [0.0] * n_hours)[idx])
            accumulated = _sum_lookback_precipitation(
                hourly.get("precipitation", [0.0] * n_hours),
                idx,
                LOOKBACK_HOURS,
            )
            condition = _infer_track_condition(current_precip, accumulated)
            peak_water = None
            confidence = None
            dew_pt = None

        return SessionConditions(
            track_condition=condition,
            ambient_temp_c=float(hourly["temperature_2m"][idx]),
            humidity_pct=float(hourly["relative_humidity_2m"][idx]),
            wind_speed_kmh=float(hourly["wind_speed_10m"][idx]),
            wind_direction_deg=float(hourly["wind_direction_10m"][idx]),
            precipitation_mm=current_precip,
            weather_source="open-meteo",
            surface_water_mm=peak_water,
            weather_confidence=confidence,
            dew_point_c=dew_pt,
        )

    except httpx.HTTPStatusError as exc:
        logger.warning(
            "Open-Meteo API returned status %d for lat=%s lon=%s date=%s",
            exc.response.status_code,
            lat,
            lon,
            session_day,
        )
        return None
    except (httpx.RequestError, ValueError, KeyError, IndexError, TypeError) as exc:
        logger.warning(
            "Open-Meteo lookup failed for lat=%s lon=%s date=%s: %s",
            lat,
            lon,
            session_day,
            exc,
        )
        return None
