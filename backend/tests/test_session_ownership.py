"""Tests for session ownership enforcement (IDOR protection).

Verifies that ``get_session_for_user()`` correctly enforces session ownership,
preventing unauthorized cross-user access while allowing dev-user bypass and
anonymous session access.
"""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import MagicMock

import pytest

from backend.api.services.session_store import (
    SessionData,
    clear_all,
    get_session_for_user,
    store_session,
)


def _make_session_data(session_id: str, user_id: str | None = None) -> SessionData:
    """Create a minimal ``SessionData`` with mocked pipeline objects.

    Only ``session_id`` and ``user_id`` matter for ownership tests — the heavy
    pipeline fields (parsed, processed, corners, etc.) are mocked out.
    """
    snapshot = MagicMock()
    snapshot.session_id = session_id
    snapshot.session_date_parsed = MagicMock()

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


class TestGetSessionForUser:
    """Tests for ``get_session_for_user()`` ownership enforcement."""

    def test_owner_can_access_own_session(self) -> None:
        """User A can access a session they own."""
        sd = _make_session_data("sess-1", user_id="user-a")
        store_session("sess-1", sd)

        result = get_session_for_user("sess-1", "user-a")
        assert result is not None
        assert result.session_id == "sess-1"
        assert result.user_id == "user-a"

    def test_other_user_cannot_access_session(self) -> None:
        """User B cannot access User A's session (IDOR protection)."""
        sd = _make_session_data("sess-1", user_id="user-a")
        store_session("sess-1", sd)

        result = get_session_for_user("sess-1", "user-b")
        assert result is None

    def test_dev_user_can_access_any_session(self) -> None:
        """The dev-user bypass can access any session regardless of ownership."""
        sd = _make_session_data("sess-1", user_id="user-a")
        store_session("sess-1", sd)

        result = get_session_for_user("sess-1", "dev-user")
        assert result is not None
        assert result.session_id == "sess-1"

    def test_session_without_user_id_accessible_by_anyone(self) -> None:
        """Sessions with no user_id set are accessible by any user."""
        sd = _make_session_data("sess-anon", user_id=None)
        store_session("sess-anon", sd)

        result_a = get_session_for_user("sess-anon", "user-a")
        result_b = get_session_for_user("sess-anon", "user-b")
        result_dev = get_session_for_user("sess-anon", "dev-user")

        assert result_a is not None
        assert result_b is not None
        assert result_dev is not None

    def test_nonexistent_session_returns_none(self) -> None:
        """Requesting a session that doesn't exist returns None."""
        result = get_session_for_user("does-not-exist", "user-a")
        assert result is None

    def test_nonexistent_session_returns_none_for_dev_user(self) -> None:
        """Even dev-user gets None for a non-existent session."""
        result = get_session_for_user("does-not-exist", "dev-user")
        assert result is None

    def test_multiple_users_isolated(self) -> None:
        """Each user can only see their own sessions, not others'."""
        sd_a = _make_session_data("sess-a", user_id="user-a")
        sd_b = _make_session_data("sess-b", user_id="user-b")
        store_session("sess-a", sd_a)
        store_session("sess-b", sd_b)

        # User A can access their session but not User B's
        assert get_session_for_user("sess-a", "user-a") is not None
        assert get_session_for_user("sess-b", "user-a") is None

        # User B can access their session but not User A's
        assert get_session_for_user("sess-b", "user-b") is not None
        assert get_session_for_user("sess-a", "user-b") is None

    def test_dev_user_bypasses_all_ownership(self) -> None:
        """Dev-user can access sessions owned by different users."""
        sd_a = _make_session_data("sess-a", user_id="user-a")
        sd_b = _make_session_data("sess-b", user_id="user-b")
        store_session("sess-a", sd_a)
        store_session("sess-b", sd_b)

        assert get_session_for_user("sess-a", "dev-user") is not None
        assert get_session_for_user("sess-b", "dev-user") is not None

    def test_returns_correct_session_data(self) -> None:
        """The returned SessionData is the exact same object that was stored."""
        sd = _make_session_data("sess-1", user_id="user-a")
        store_session("sess-1", sd)

        result = get_session_for_user("sess-1", "user-a")
        assert result is sd
