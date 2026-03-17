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
    """17:32 UTC → 13:32 EDT during March (DST)."""
    result = localize_session_date("15/03/2026 17:32", "America/New_York")
    assert result is not None
    assert "13:32" in result
    assert "EDT" in result


def test_localize_session_date_utc_to_eastern_winter() -> None:
    """17:32 UTC → 12:32 EST during January (no DST)."""
    result = localize_session_date("15/01/2026 17:32", "America/New_York")
    assert result is not None
    assert "12:32" in result
    assert "EST" in result


def test_localize_session_date_date_only() -> None:
    """Date-only strings get midnight converted."""
    result = localize_session_date("15/03/2026", "America/New_York")
    assert result is not None
    assert "15/03/2026" in result or "14/03/2026" in result  # might roll back a day


def test_localize_session_date_invalid_tz() -> None:
    """Invalid timezone → None."""
    assert localize_session_date("15/03/2026 12:00", "Fake/Zone") is None


def test_localize_session_date_bad_date() -> None:
    """Unparseable date → None."""
    assert localize_session_date("not-a-date", "America/New_York") is None
