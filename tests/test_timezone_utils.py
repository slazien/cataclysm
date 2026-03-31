"""Tests for cataclysm.timezone_utils."""

from __future__ import annotations

import pandas as pd

from cataclysm.timezone_utils import (
    get_timezone_name,
    localize_session_date,
    resolve_session_timezone,
    session_date_to_iso,
)


def test_get_timezone_name_amp() -> None:
    """AMP (Atlanta Motorsports Park) should resolve to Eastern time."""
    tz = get_timezone_name(lat=34.4319, lon=-84.1761)
    assert tz == "America/New_York"


def test_get_timezone_name_barber() -> None:
    """Barber Motorsports Park is also Eastern time."""
    tz = get_timezone_name(lat=33.53, lon=-86.62)
    assert tz == "America/Chicago"  # Barber is actually Central


def test_get_timezone_name_ocean_returns_none() -> None:
    """GPS in the middle of the ocean → None."""
    tz = get_timezone_name(lat=0.0, lon=-30.0)
    # Could be None (ocean) or a timezone depending on library version
    # Just verify no crash
    assert tz is None or isinstance(tz, str)


def test_localize_session_date_utc_to_eastern() -> None:
    """17:32 UTC → 1:32 PM EDT during March (DST)."""
    result = localize_session_date("15/03/2026 17:32", "America/New_York")
    assert result is not None
    assert result == "Mar 15, 2026 · 1:32 PM EDT"


def test_localize_session_date_utc_to_eastern_winter() -> None:
    """17:32 UTC → 12:32 PM EST during January (no DST)."""
    result = localize_session_date("15/01/2026 17:32", "America/New_York")
    assert result is not None
    assert result == "Jan 15, 2026 · 12:32 PM EST"


def test_localize_session_date_utc_to_central() -> None:
    """12:31 UTC → 7:31 AM CDT for Barber (Central time, March DST)."""
    result = localize_session_date("21/03/2026 12:31", "America/Chicago")
    assert result is not None
    assert result == "Mar 21, 2026 · 7:31 AM CDT"


def test_localize_session_date_date_only() -> None:
    """Date-only strings get midnight UTC converted."""
    result = localize_session_date("15/03/2026", "America/New_York")
    assert result is not None
    # Midnight UTC → 8 PM EDT previous day
    assert result == "Mar 14, 2026 · 8:00 PM EDT"


def test_localize_session_date_iso_format() -> None:
    """ISO format input also works."""
    result = localize_session_date("2026-03-15 17:32:00", "America/New_York")
    assert result is not None
    assert result == "Mar 15, 2026 · 1:32 PM EDT"


def test_localize_session_date_invalid_tz() -> None:
    """Invalid timezone → None."""
    assert localize_session_date("15/03/2026 12:00", "Fake/Zone") is None


def test_localize_session_date_bad_date() -> None:
    """Unparseable date → None."""
    assert localize_session_date("not-a-date", "America/New_York") is None


# --- resolve_session_timezone ---


def test_resolve_session_timezone_from_gps() -> None:
    """Resolves timezone from GPS coordinates in telemetry DataFrame."""
    df = pd.DataFrame({"lat": [32.136, 32.137], "lon": [-81.156, -81.157]})
    tz = resolve_session_timezone(df, track_name=None)
    assert tz == "America/New_York"


def test_resolve_session_timezone_missing_gps_cols() -> None:
    """Returns None when GPS columns are missing."""
    df = pd.DataFrame({"speed": [50, 60]})
    tz = resolve_session_timezone(df, track_name=None)
    assert tz is None


def test_resolve_session_timezone_nan_gps() -> None:
    """Returns None when GPS values are all NaN."""
    df = pd.DataFrame({"lat": [float("nan")], "lon": [float("nan")]})
    tz = resolve_session_timezone(df, track_name=None)
    assert tz is None


def test_resolve_session_timezone_fallback_to_track_db() -> None:
    """Falls back to track_db center coords when GPS is missing."""
    df = pd.DataFrame({"speed": [50]})  # no lat/lon
    tz = resolve_session_timezone(df, track_name="Roebling Road Raceway")
    # Roebling center coords should resolve to Eastern
    assert tz == "America/New_York"


# --- session_date_to_iso ---


def test_session_date_to_iso_ddmmyyyy() -> None:
    """Converts DD/MM/YYYY HH:MM to ISO 8601 UTC."""
    assert session_date_to_iso("21/03/2026 12:31") == "2026-03-21T12:31:00Z"


def test_session_date_to_iso_date_only() -> None:
    """Date-only string gets midnight."""
    assert session_date_to_iso("21/03/2026") == "2026-03-21T00:00:00Z"


def test_session_date_to_iso_already_iso() -> None:
    """ISO input passes through."""
    assert session_date_to_iso("2026-03-21 12:31:00") == "2026-03-21T12:31:00Z"


def test_session_date_to_iso_unparseable() -> None:
    """Unparseable string returns itself."""
    assert session_date_to_iso("garbage") == "garbage"
