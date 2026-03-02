"""Tests for backend.api.services.session_store — edge case coverage.

Targets uncovered lines:
- Lines 62-64: set_session_weather() — when session exists vs. not in store
- Lines 70-72: _evict_oldest() — LRU eviction when store exceeds MAX_SESSIONS
- Line 91: get_session() debug log — miss when store is non-empty
- Line 122: delete_session() warning log — attempt to delete non-existent session

Also covers store/get/delete/list_sessions and the list_sessions sort.
"""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from backend.api.services.session_store import (
    MAX_SESSIONS,
    SessionData,
    clear_all,
    delete_session,
    get_session,
    list_sessions,
    set_session_weather,
    store_session,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session_data(
    session_id: str = "sess-1",
    user_id: str | None = None,
    date_parsed: object = None,
) -> SessionData:
    """Create a minimal SessionData with mocked pipeline objects."""
    snapshot = MagicMock()
    snapshot.session_id = session_id
    snapshot.session_date_parsed = date_parsed if date_parsed is not None else MagicMock()

    return SessionData(
        session_id=session_id,
        snapshot=snapshot,
        parsed=MagicMock(),
        processed=MagicMock(),
        corners=[],
        all_lap_corners={},
        user_id=user_id,
    )


@pytest.fixture(autouse=True)
def _clean_store() -> Generator[None, None, None]:
    """Clear the in-memory session store before and after each test."""
    clear_all()
    yield
    clear_all()


# ---------------------------------------------------------------------------
# set_session_weather — lines 62-64
# ---------------------------------------------------------------------------


class TestSetSessionWeather:
    """Tests for set_session_weather()."""

    def test_attaches_weather_to_existing_session(self) -> None:
        """Weather is attached when the session is in the store."""
        from cataclysm.equipment import SessionConditions, TrackCondition

        sd = _make_session_data("sess-weather")
        store_session("sess-weather", sd)

        weather = SessionConditions(
            track_condition=TrackCondition.DRY,
            ambient_temp_c=22.0,
        )
        set_session_weather("sess-weather", weather)

        result = get_session("sess-weather")
        assert result is not None
        assert result.weather is weather
        assert result.weather.ambient_temp_c == pytest.approx(22.0)

    def test_no_op_when_session_not_in_store(self) -> None:
        """set_session_weather silently does nothing for unknown sessions."""
        from cataclysm.equipment import SessionConditions, TrackCondition

        weather = SessionConditions(track_condition=TrackCondition.WET)
        # Must not raise
        set_session_weather("no-such-session", weather)

    def test_weather_is_not_set_on_other_sessions(self) -> None:
        """Weather assignment only affects the targeted session."""
        from cataclysm.equipment import SessionConditions, TrackCondition

        sd_a = _make_session_data("sess-a")
        sd_b = _make_session_data("sess-b")
        store_session("sess-a", sd_a)
        store_session("sess-b", sd_b)

        weather = SessionConditions(track_condition=TrackCondition.DAMP)
        set_session_weather("sess-a", weather)

        assert get_session("sess-a").weather is weather  # type: ignore[union-attr]
        assert get_session("sess-b").weather is None  # type: ignore[union-attr]

    def test_weather_can_be_overwritten(self) -> None:
        """Calling set_session_weather twice replaces the weather value."""
        from cataclysm.equipment import SessionConditions, TrackCondition

        sd = _make_session_data("sess-overwrite")
        store_session("sess-overwrite", sd)

        w1 = SessionConditions(track_condition=TrackCondition.DRY)
        w2 = SessionConditions(track_condition=TrackCondition.WET)

        set_session_weather("sess-overwrite", w1)
        set_session_weather("sess-overwrite", w2)

        result = get_session("sess-overwrite")
        assert result is not None
        assert result.weather is w2


# ---------------------------------------------------------------------------
# _evict_oldest — lines 70-72 (LRU eviction)
# ---------------------------------------------------------------------------


class TestEvictOldest:
    """Tests for the LRU eviction logic inside store_session."""

    def test_eviction_occurs_when_max_sessions_exceeded(self) -> None:
        """When more than MAX_SESSIONS are stored, oldest are evicted."""
        from datetime import datetime

        # Store MAX_SESSIONS + 2 sessions with real dates so list_sessions() can sort
        n = MAX_SESSIONS + 2
        for i in range(n):
            sid = f"sess-{i:04d}"
            store_session(sid, _make_session_data(sid, date_parsed=datetime(2025, 1, 1)))

        # Measure store size directly via get_session() rather than list_sessions()
        # to avoid sorting issues. Count how many of the inserted IDs are still present.
        still_present = sum(1 for i in range(n) if get_session(f"sess-{i:04d}") is not None)
        assert still_present <= MAX_SESSIONS

    def test_oldest_session_is_evicted_first(self) -> None:
        """The first inserted session is evicted when capacity is exceeded."""
        first_id = "sess-first-in"
        store_session(first_id, _make_session_data(first_id))

        for i in range(MAX_SESSIONS):
            store_session(f"sess-filler-{i:04d}", _make_session_data(f"sess-filler-{i:04d}"))

        # The very first session should have been evicted
        assert get_session(first_id) is None

    def test_newest_sessions_survive_eviction(self) -> None:
        """Newly inserted sessions are not evicted when old ones are displaced."""
        # Fill the store to capacity, then add one more
        for i in range(MAX_SESSIONS):
            store_session(f"sess-old-{i:04d}", _make_session_data(f"sess-old-{i:04d}"))

        newest_id = "sess-newest"
        store_session(newest_id, _make_session_data(newest_id))

        assert get_session(newest_id) is not None

    def test_exactly_max_sessions_no_eviction(self) -> None:
        """Storing exactly MAX_SESSIONS items does not evict any session."""
        first_id = "sess-exact-first"
        store_session(first_id, _make_session_data(first_id))

        for i in range(MAX_SESSIONS - 1):
            store_session(f"sess-pad-{i:04d}", _make_session_data(f"sess-pad-{i:04d}"))

        # The first session should still be present
        assert get_session(first_id) is not None


# ---------------------------------------------------------------------------
# get_session — line 91 (debug log on miss with non-empty store)
# ---------------------------------------------------------------------------


class TestGetSession:
    """Tests for get_session(), including the debug log branch."""

    def test_returns_none_for_empty_store(self) -> None:
        assert get_session("any-id") is None

    def test_returns_session_when_present(self) -> None:
        sd = _make_session_data("sess-get")
        store_session("sess-get", sd)
        assert get_session("sess-get") is sd

    def test_returns_none_and_logs_when_store_nonempty(self) -> None:
        """When the store is non-empty but the session is missing, None is returned.

        This exercises line 91 — the debug log branch.
        """
        store_session("sess-other", _make_session_data("sess-other"))

        with patch("backend.api.services.session_store.logger") as mock_logger:
            result = get_session("sess-missing")

        assert result is None
        mock_logger.debug.assert_called_once()
        call_args = mock_logger.debug.call_args[0]
        assert "sess-missing" in call_args[1]

    def test_returns_none_without_log_when_store_empty(self) -> None:
        """When the store is empty, None is returned without a debug log."""
        with patch("backend.api.services.session_store.logger") as mock_logger:
            result = get_session("sess-missing")

        assert result is None
        mock_logger.debug.assert_not_called()


# ---------------------------------------------------------------------------
# delete_session — line 122 (warning log for non-existent session)
# ---------------------------------------------------------------------------


class TestDeleteSession:
    """Tests for delete_session(), including the warning log branch."""

    def test_deletes_existing_session_returns_true(self) -> None:
        sd = _make_session_data("sess-del")
        store_session("sess-del", sd)
        assert delete_session("sess-del") is True
        assert get_session("sess-del") is None

    def test_returns_false_for_missing_session(self) -> None:
        """Deleting a non-existent session returns False and logs a warning.

        This exercises line 122 — the warning branch.
        """
        assert delete_session("no-such-session") is False

    def test_logs_warning_on_missing_delete(self) -> None:
        """A warning is logged when deleting a session that does not exist."""
        with patch("backend.api.services.session_store.logger") as mock_logger:
            delete_session("ghost-session")

        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args[0]
        assert "ghost-session" in call_args[1]

    def test_delete_logs_info_on_success(self) -> None:
        """An info message is logged when a session is successfully deleted."""
        store_session("sess-info-del", _make_session_data("sess-info-del"))
        with patch("backend.api.services.session_store.logger") as mock_logger:
            delete_session("sess-info-del")

        mock_logger.info.assert_called()

    def test_multiple_deletes_of_same_id(self) -> None:
        """Second delete of same session_id returns False."""
        store_session("sess-dup-del", _make_session_data("sess-dup-del"))
        assert delete_session("sess-dup-del") is True
        assert delete_session("sess-dup-del") is False


# ---------------------------------------------------------------------------
# list_sessions
# ---------------------------------------------------------------------------


class TestListSessions:
    """Tests for list_sessions() sort order."""

    def test_empty_store_returns_empty_list(self) -> None:
        assert list_sessions() == []

    def test_sessions_sorted_newest_first(self) -> None:
        """Sessions are returned newest-first based on session_date_parsed."""
        from datetime import datetime

        old_date = datetime(2024, 1, 1)
        new_date = datetime(2026, 1, 1)

        sd_old = _make_session_data("sess-old", date_parsed=old_date)
        sd_new = _make_session_data("sess-new", date_parsed=new_date)

        store_session("sess-old", sd_old)
        store_session("sess-new", sd_new)

        result = list_sessions()
        assert result[0].session_id == "sess-new"
        assert result[1].session_id == "sess-old"

    def test_single_session_list(self) -> None:
        sd = _make_session_data("sess-single")
        store_session("sess-single", sd)
        result = list_sessions()
        assert len(result) == 1
        assert result[0].session_id == "sess-single"


# ---------------------------------------------------------------------------
# clear_all
# ---------------------------------------------------------------------------


class TestClearAll:
    """Tests for clear_all()."""

    def test_clears_all_sessions_and_returns_count(self) -> None:
        store_session("s1", _make_session_data("s1"))
        store_session("s2", _make_session_data("s2"))
        store_session("s3", _make_session_data("s3"))

        count = clear_all()

        assert count == 3
        assert list_sessions() == []

    def test_clear_empty_store_returns_zero(self) -> None:
        assert clear_all() == 0
