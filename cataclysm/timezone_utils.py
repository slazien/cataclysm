"""Timezone utilities for converting session dates to local time.

Uses ``timezonefinder`` to map GPS coordinates to an IANA timezone,
then converts the UTC session datetime to a local time string with
timezone abbreviation (e.g. ``"Mar 15, 2026 · 1:32 PM EDT"``).
"""

from __future__ import annotations

import logging
import math
from datetime import datetime
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import pandas as pd

if TYPE_CHECKING:
    from timezonefinder import TimezoneFinder

logger = logging.getLogger(__name__)

# Lazy singleton — created on first call to avoid import-time cost
_tf_instance: TimezoneFinder | None = None


def _get_tf() -> TimezoneFinder:
    """Return a cached :class:`TimezoneFinder` instance."""
    global _tf_instance  # noqa: PLW0603
    if _tf_instance is None:
        from timezonefinder import TimezoneFinder as _TimezoneFinder

        _tf_instance = _TimezoneFinder(in_memory=True)
    return _tf_instance


def get_timezone_name(lat: float, lon: float) -> str | None:
    """Return the IANA timezone name for *lat*/*lon*, or ``None`` on failure.

    Examples: ``"America/New_York"``, ``"Europe/Berlin"``.
    """
    try:
        tf = _get_tf()
        return tf.timezone_at(lat=lat, lng=lon)
    except Exception:
        logger.debug("timezonefinder lookup failed for lat=%s lon=%s", lat, lon, exc_info=True)
        return None


def localize_session_date(
    session_date_utc: str,
    timezone_name: str,
) -> str | None:
    """Convert a UTC session date string to local time.

    Parameters
    ----------
    session_date_utc:
        Date string in one of the RaceChrono formats
        (``"DD/MM/YYYY HH:MM"``) or ISO (``"YYYY-MM-DD HH:MM:SS"``).
    timezone_name:
        IANA timezone name, e.g. ``"America/New_York"``.

    Returns
    -------
    Localized string like ``"Mar 21, 2026 · 8:31 AM EDT"``, or ``None`` on failure.
    """
    try:
        tz = ZoneInfo(timezone_name)
    except (KeyError, Exception):
        return None

    # Parse the UTC date string
    utc_dt: datetime | None = None
    for fmt in [
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y,%H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%d/%m/%Y",
    ]:
        try:
            utc_dt = datetime.strptime(session_date_utc.strip(), fmt).replace(
                tzinfo=ZoneInfo("UTC"),
            )
            break
        except ValueError:
            continue

    if utc_dt is None:
        return None

    local_dt = utc_dt.astimezone(tz)
    abbrev = local_dt.strftime("%Z")  # e.g. "EDT", "EST", "CET"
    # Format: "Mar 21, 2026 · 8:31 AM EDT"
    time_str = local_dt.strftime("%-I:%M %p")  # "8:31 AM" (no leading zero)
    date_str = local_dt.strftime("%b %-d, %Y")  # "Mar 21, 2026"
    return f"{date_str} · {time_str} {abbrev}"


def resolve_session_timezone(
    df: pd.DataFrame,
    track_name: str | None,
) -> str | None:
    """Resolve IANA timezone from session telemetry GPS or track_db fallback."""
    # Try GPS from telemetry
    if "lat" in df.columns and "lon" in df.columns:
        lat_series = df["lat"].dropna()
        lon_series = df["lon"].dropna()
        if len(lat_series) > 0 and len(lon_series) > 0:
            lat = float(lat_series.iloc[0])
            lon = float(lon_series.iloc[0])
            if not (math.isnan(lat) or math.isnan(lon)):
                tz = get_timezone_name(lat, lon)
                if tz is not None:
                    return tz

    # Fallback: track_db center coords
    if track_name:
        try:
            from cataclysm.track_db import lookup_track

            info = lookup_track(track_name)
            if info and info.center_lat and info.center_lon:
                return get_timezone_name(info.center_lat, info.center_lon)
        except Exception:
            logger.debug("track_db fallback failed for %s", track_name, exc_info=True)

    return None


def session_date_to_iso(date_str: str) -> str:
    """Convert a RaceChrono date string to ISO 8601 UTC format.

    Returns the original string unchanged if parsing fails.
    """
    cleaned = date_str.strip()
    for fmt in [
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y,%H:%M",
        "%m/%d/%Y %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M",
        "%d/%m/%Y",
        "%Y-%m-%d",
    ]:
        try:
            dt = datetime.strptime(cleaned, fmt)  # noqa: DTZ007
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            continue
    return date_str
