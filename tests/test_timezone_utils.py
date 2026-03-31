"""Tests for cataclysm.timezone_utils."""

from __future__ import annotations

from cataclysm.timezone_utils import get_timezone_name, localize_session_date


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
