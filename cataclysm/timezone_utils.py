"""Timezone utilities for converting session dates to local time.

Uses ``timezonefinder`` to map GPS coordinates to an IANA timezone,
then converts the UTC session datetime to a local time string with
timezone abbreviation (e.g. ``"15/03/2026 13:32 EDT"``).
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

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
    """Convert a UTC session date string to local time with timezone abbreviation.

    Parameters
    ----------
    session_date_utc:
        Date string in one of the RaceChrono formats
        (``"DD/MM/YYYY HH:MM"`` or ``"DD/MM/YYYY"``).
    timezone_name:
        IANA timezone name, e.g. ``"America/New_York"``.

    Returns
    -------
    Localized string like ``"15/03/2026 13:32 EDT"``, or ``None`` on failure.
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
            utc_dt = datetime.strptime(session_date_utc.strip(), fmt).replace(  # noqa: DTZ007
                tzinfo=ZoneInfo("UTC"),
            )
            break
        except ValueError:
            continue

    if utc_dt is None:
        return None

    local_dt = utc_dt.astimezone(tz)
    abbrev = local_dt.strftime("%Z")  # e.g. "EDT", "EST", "CET"
    return f"{local_dt.strftime('%d/%m/%Y %H:%M')} {abbrev}"
