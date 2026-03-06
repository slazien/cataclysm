"""Tests for anonymous upload and session claiming features.

Covers:
- anon_rate_limit.py: check_and_record_anon_upload, expiry logic
- Anonymous upload path in sessions router (get_optional_user returns None)
- POST /api/sessions/claim endpoint
- session_store.py: claim_session, cleanup_expired_anonymous
"""

from __future__ import annotations

import time
from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from backend.api.dependencies import get_current_user, get_optional_user
from backend.api.main import app
from backend.api.services import session_store
from backend.api.services.session_store import (
    ANON_SESSION_TTL,
    SessionData,
    claim_session,
    cleanup_expired_anonymous,
    clear_all,
    get_session,
    get_session_for_user,
    store_session,
)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_session_data(
    session_id: str = "sess-1",
    user_id: str | None = None,
    is_anonymous: bool = False,
    client_ip: str | None = None,
    created_at: float | None = None,
) -> SessionData:
    """Create a minimal SessionData with mocked pipeline objects."""
    snapshot = MagicMock()
    snapshot.session_id = session_id
    snapshot.session_date_parsed = MagicMock()

    sd = SessionData(
        session_id=session_id,
        snapshot=snapshot,
        parsed=MagicMock(),
        processed=MagicMock(),
        corners=[],
        all_lap_corners={},
        user_id=user_id,
        is_anonymous=is_anonymous,
        client_ip=client_ip,
    )
    if created_at is not None:
        sd.created_at = created_at
    return sd


@pytest.fixture(autouse=True)
def _clean_store() -> Generator[None, None, None]:
    """Clear the in-memory session store before and after each test."""
    clear_all()
    yield
    clear_all()


@pytest.fixture
def _reset_rate_limit() -> Generator[None, None, None]:
    """Reset the in-memory anonymous rate limit state before and after each test."""
    import backend.api.services.anon_rate_limit as rl

    rl._ip_timestamps.clear()
    rl._global_timestamps.clear()
    yield
    rl._ip_timestamps.clear()
    rl._global_timestamps.clear()


# ---------------------------------------------------------------------------
# Unit tests: anon_rate_limit module
# ---------------------------------------------------------------------------


class TestCheckAndRecordAnonUpload:
    """Tests for check_and_record_anon_upload()."""

    @pytest.fixture(autouse=True)
    def _reset(self, _reset_rate_limit: None) -> None:
        """Use shared rate limit reset fixture for every test in this class."""

    def test_fresh_ip_is_allowed(self) -> None:
        """A brand-new IP with no prior uploads is allowed."""
        from backend.api.services.anon_rate_limit import check_and_record_anon_upload

        allowed, reason = check_and_record_anon_upload("10.0.0.1")
        assert allowed is True
        assert reason == ""

    def test_ip_under_limit_is_allowed(self) -> None:
        """An IP with fewer than MAX_ANON_PER_IP uploads in the window is allowed."""
        import backend.api.services.anon_rate_limit as rl
        from backend.api.services.anon_rate_limit import (
            MAX_ANON_PER_IP,
            check_and_record_anon_upload,
        )

        ip = "10.0.0.2"
        # Seed the IP with 1 fewer than the limit (bypassing atomic record)
        rl._ip_timestamps[ip] = [time.time()] * (MAX_ANON_PER_IP - 1)

        allowed, reason = check_and_record_anon_upload(ip)
        # At exactly MAX_ANON_PER_IP - 1, the next call should be blocked since
        # check_and_record is atomic and records on allow. With MAX_ANON_PER_IP - 1
        # pre-seeded, the check sees < limit and allows (recording makes it MAX_ANON_PER_IP).
        assert allowed is True
        assert reason == ""

    def test_ip_at_limit_is_blocked(self) -> None:
        """An IP that has hit MAX_ANON_PER_IP uploads is blocked on next call."""
        import backend.api.services.anon_rate_limit as rl
        from backend.api.services.anon_rate_limit import (
            MAX_ANON_PER_IP,
            check_and_record_anon_upload,
        )

        ip = "10.0.0.3"
        # Pre-seed to the limit
        rl._ip_timestamps[ip] = [time.time()] * MAX_ANON_PER_IP

        allowed, reason = check_and_record_anon_upload(ip)
        assert allowed is False
        assert "sign in" in reason.lower()

    def test_ip_blocked_message_mentions_signing_in(self) -> None:
        """The IP-limit rejection message advises the user to sign in."""
        import backend.api.services.anon_rate_limit as rl
        from backend.api.services.anon_rate_limit import (
            MAX_ANON_PER_IP,
            check_and_record_anon_upload,
        )

        ip = "10.0.0.4"
        rl._ip_timestamps[ip] = [time.time()] * MAX_ANON_PER_IP

        _, reason = check_and_record_anon_upload(ip)
        assert "sign in" in reason.lower()

    def test_global_cap_blocks_new_ip(self) -> None:
        """When the global daily cap is exhausted, a fresh IP is blocked."""
        import backend.api.services.anon_rate_limit as rl
        from backend.api.services.anon_rate_limit import (
            MAX_ANON_GLOBAL_DAILY,
            check_and_record_anon_upload,
        )

        # Fill the global list to the cap
        rl._global_timestamps[:] = [time.time()] * MAX_ANON_GLOBAL_DAILY

        allowed, reason = check_and_record_anon_upload("brand-new-ip")
        assert allowed is False
        assert "capacity" in reason.lower()

    def test_global_cap_message_mentions_capacity(self) -> None:
        """The global-cap rejection message mentions capacity."""
        import backend.api.services.anon_rate_limit as rl
        from backend.api.services.anon_rate_limit import (
            MAX_ANON_GLOBAL_DAILY,
            check_and_record_anon_upload,
        )

        rl._global_timestamps[:] = [time.time()] * MAX_ANON_GLOBAL_DAILY

        _, reason = check_and_record_anon_upload("any-ip")
        assert "capacity" in reason.lower()

    def test_different_ips_have_separate_counters(self) -> None:
        """Rate limits are per-IP; exhausting one IP does not block another."""
        import backend.api.services.anon_rate_limit as rl
        from backend.api.services.anon_rate_limit import (
            MAX_ANON_PER_IP,
            check_and_record_anon_upload,
        )

        ip_a = "10.1.1.1"
        ip_b = "10.1.1.2"
        rl._ip_timestamps[ip_a] = [time.time()] * MAX_ANON_PER_IP

        allowed_a, _ = check_and_record_anon_upload(ip_a)
        assert allowed_a is False

        allowed_b, _ = check_and_record_anon_upload(ip_b)
        assert allowed_b is True

    def test_old_ip_entries_expire_after_window(self) -> None:
        """Timestamps older than WINDOW_SECONDS are pruned and don't count."""
        import backend.api.services.anon_rate_limit as rl
        from backend.api.services.anon_rate_limit import (
            MAX_ANON_PER_IP,
            WINDOW_SECONDS,
            check_and_record_anon_upload,
        )

        ip = "10.2.2.2"
        stale_ts = time.time() - WINDOW_SECONDS - 1
        rl._ip_timestamps[ip] = [stale_ts] * MAX_ANON_PER_IP

        # All entries are stale — should be allowed
        allowed, _ = check_and_record_anon_upload(ip)
        assert allowed is True

    def test_global_old_entries_expire_after_window(self) -> None:
        """Stale global timestamps are pruned before checking the cap."""
        import backend.api.services.anon_rate_limit as rl
        from backend.api.services.anon_rate_limit import (
            MAX_ANON_GLOBAL_DAILY,
            WINDOW_SECONDS,
            check_and_record_anon_upload,
        )

        stale_ts = time.time() - WINDOW_SECONDS - 1
        rl._global_timestamps[:] = [stale_ts] * MAX_ANON_GLOBAL_DAILY

        allowed, _ = check_and_record_anon_upload("fresh-ip")
        assert allowed is True

    def test_mixed_old_and_new_timestamps_for_ip(self) -> None:
        """Only in-window timestamps count toward the per-IP limit."""
        import backend.api.services.anon_rate_limit as rl
        from backend.api.services.anon_rate_limit import (
            WINDOW_SECONDS,
            check_and_record_anon_upload,
        )

        ip = "10.3.3.3"
        stale_ts = time.time() - WINDOW_SECONDS - 1
        # 2 stale + 1 fresh = 1 in-window entry, well under limit of 3
        rl._ip_timestamps[ip] = [stale_ts, stale_ts, time.time()]

        allowed, _ = check_and_record_anon_upload(ip)
        assert allowed is True

    def test_allowed_upload_is_recorded_atomically(self) -> None:
        """When an upload is allowed, the timestamp is recorded immediately."""
        import backend.api.services.anon_rate_limit as rl
        from backend.api.services.anon_rate_limit import check_and_record_anon_upload

        ip = "10.4.4.4"
        initial_global = len(rl._global_timestamps)
        initial_ip = len(rl._ip_timestamps.get(ip, []))

        allowed, _ = check_and_record_anon_upload(ip)
        assert allowed is True
        assert len(rl._global_timestamps) == initial_global + 1
        assert len(rl._ip_timestamps[ip]) == initial_ip + 1

    def test_blocked_upload_is_not_recorded(self) -> None:
        """When an upload is blocked, no timestamp is added."""
        import backend.api.services.anon_rate_limit as rl
        from backend.api.services.anon_rate_limit import (
            MAX_ANON_PER_IP,
            check_and_record_anon_upload,
        )

        ip = "10.5.5.5"
        rl._ip_timestamps[ip] = [time.time()] * MAX_ANON_PER_IP
        initial_count = len(rl._ip_timestamps[ip])
        initial_global = len(rl._global_timestamps)

        allowed, _ = check_and_record_anon_upload(ip)
        assert allowed is False
        assert len(rl._ip_timestamps[ip]) == initial_count
        assert len(rl._global_timestamps) == initial_global

    def test_consecutive_allowed_uploads_fill_quota(self) -> None:
        """Calling check_and_record_anon_upload MAX_ANON_PER_IP times exhausts the quota."""
        from backend.api.services.anon_rate_limit import (
            MAX_ANON_PER_IP,
            check_and_record_anon_upload,
        )

        ip = "10.6.6.6"
        for i in range(MAX_ANON_PER_IP):
            allowed, _ = check_and_record_anon_upload(ip)
            assert allowed is True, f"Expected allowed on call {i + 1}"

        # Next call should be blocked
        allowed, reason = check_and_record_anon_upload(ip)
        assert allowed is False
        assert reason != ""


# ---------------------------------------------------------------------------
# Unit tests: session_store.claim_session
# ---------------------------------------------------------------------------


class TestClaimSession:
    """Tests for session_store.claim_session()."""

    def test_claim_sets_not_anonymous(self) -> None:
        """Claiming marks is_anonymous=False on the session."""
        sd = _make_session_data("sess-claim-1", is_anonymous=True)
        store_session("sess-claim-1", sd)

        result = claim_session("sess-claim-1", "user-abc")
        assert result is True
        assert sd.is_anonymous is False

    def test_claim_sets_user_id(self) -> None:
        """Claiming sets the user_id on the session data."""
        sd = _make_session_data("sess-claim-2", is_anonymous=True)
        store_session("sess-claim-2", sd)

        claim_session("sess-claim-2", "user-xyz")
        assert sd.user_id == "user-xyz"

    def test_claim_nonexistent_session_returns_false(self) -> None:
        """Claiming a non-existent session returns False."""
        result = claim_session("no-such-session", "user-abc")
        assert result is False

    def test_claim_already_owned_session_returns_false(self) -> None:
        """Claiming a session that is not anonymous returns False."""
        sd = _make_session_data("sess-owned", user_id="user-a", is_anonymous=False)
        store_session("sess-owned", sd)

        result = claim_session("sess-owned", "user-b")
        assert result is False

    def test_claimed_session_no_longer_anonymous(self) -> None:
        """After claiming, the session is marked as owned (not anonymous)."""
        sd = _make_session_data("sess-claim-3", is_anonymous=True)
        store_session("sess-claim-3", sd)

        claim_session("sess-claim-3", "owner-user")

        updated = get_session("sess-claim-3")
        assert updated is not None
        assert updated.is_anonymous is False
        assert updated.user_id == "owner-user"

    def test_claimed_session_only_accessible_to_owner(self) -> None:
        """After claiming, get_session_for_user enforces ownership."""
        sd = _make_session_data("sess-claim-4", is_anonymous=True)
        store_session("sess-claim-4", sd)

        claim_session("sess-claim-4", "owner-user")

        assert get_session_for_user("sess-claim-4", "owner-user") is not None
        assert get_session_for_user("sess-claim-4", "other-user") is None

    def test_claim_returns_true_on_success(self) -> None:
        """claim_session returns True when the session exists and is anonymous."""
        sd = _make_session_data("sess-claim-ok", is_anonymous=True)
        store_session("sess-claim-ok", sd)

        assert claim_session("sess-claim-ok", "user-new") is True

    def test_claim_logs_info(self) -> None:
        """A successful claim emits an info log."""
        sd = _make_session_data("sess-claim-log", is_anonymous=True)
        store_session("sess-claim-log", sd)

        with patch("backend.api.services.session_store.logger") as mock_logger:
            claim_session("sess-claim-log", "user-log-test")

        mock_logger.info.assert_called()
        log_args = str(mock_logger.info.call_args)
        assert "sess-claim-log" in log_args or "user-log-test" in log_args


# ---------------------------------------------------------------------------
# Unit tests: session_store.cleanup_expired_anonymous
# ---------------------------------------------------------------------------


class TestCleanupExpiredAnonymous:
    """Tests for session_store.cleanup_expired_anonymous()."""

    def test_removes_expired_anonymous_sessions(self) -> None:
        """Anonymous sessions older than TTL are removed."""
        expired_ts = time.time() - ANON_SESSION_TTL - 1
        sd = _make_session_data("sess-expired", is_anonymous=True, created_at=expired_ts)
        store_session("sess-expired", sd)

        count = cleanup_expired_anonymous()
        assert count == 1
        assert get_session("sess-expired") is None

    def test_keeps_fresh_anonymous_sessions(self) -> None:
        """Anonymous sessions within TTL are not removed."""
        fresh_ts = time.time() - 100  # 100 seconds old, well within 24h
        sd = _make_session_data("sess-fresh", is_anonymous=True, created_at=fresh_ts)
        store_session("sess-fresh", sd)

        count = cleanup_expired_anonymous()
        assert count == 0
        assert get_session("sess-fresh") is not None

    def test_does_not_remove_non_anonymous_sessions(self) -> None:
        """Non-anonymous sessions are never cleaned up, even if old."""
        old_ts = time.time() - ANON_SESSION_TTL - 9999
        sd = _make_session_data(
            "sess-auth-old", user_id="user-a", is_anonymous=False, created_at=old_ts
        )
        store_session("sess-auth-old", sd)

        count = cleanup_expired_anonymous()
        assert count == 0
        assert get_session("sess-auth-old") is not None

    def test_returns_count_of_removed_sessions(self) -> None:
        """cleanup_expired_anonymous returns the exact number of removed sessions."""
        expired_ts = time.time() - ANON_SESSION_TTL - 1
        for i in range(3):
            sd = _make_session_data(f"sess-exp-{i}", is_anonymous=True, created_at=expired_ts)
            store_session(f"sess-exp-{i}", sd)

        count = cleanup_expired_anonymous()
        assert count == 3

    def test_returns_zero_when_nothing_to_clean(self) -> None:
        """Returns 0 when there are no expired anonymous sessions."""
        count = cleanup_expired_anonymous()
        assert count == 0

    def test_mixed_sessions_only_removes_expired_anonymous(self) -> None:
        """Only expired anonymous sessions are removed; all others stay."""
        expired_ts = time.time() - ANON_SESSION_TTL - 1
        fresh_ts = time.time() - 60

        expired_anon = _make_session_data("anon-old", is_anonymous=True, created_at=expired_ts)
        fresh_anon = _make_session_data("anon-new", is_anonymous=True, created_at=fresh_ts)
        auth_old = _make_session_data(
            "auth-old", user_id="u", is_anonymous=False, created_at=expired_ts
        )

        store_session("anon-old", expired_anon)
        store_session("anon-new", fresh_anon)
        store_session("auth-old", auth_old)

        count = cleanup_expired_anonymous()
        assert count == 1
        assert get_session("anon-old") is None
        assert get_session("anon-new") is not None
        assert get_session("auth-old") is not None

    def test_all_expired_anon_removed_authenticated_untouched(self) -> None:
        """Multiple expired anon sessions are all removed; auth session stays."""
        expired_ts = time.time() - ANON_SESSION_TTL - 1

        for i in range(5):
            sd = _make_session_data(f"anon-exp-{i}", is_anonymous=True, created_at=expired_ts)
            store_session(f"anon-exp-{i}", sd)

        auth_sd = _make_session_data("auth-keep", user_id="u", is_anonymous=False)
        store_session("auth-keep", auth_sd)

        count = cleanup_expired_anonymous()
        assert count == 5
        for i in range(5):
            assert get_session(f"anon-exp-{i}") is None
        assert get_session("auth-keep") is not None


# ---------------------------------------------------------------------------
# Integration tests: anonymous upload endpoint
# ---------------------------------------------------------------------------


class TestAnonUploadEndpoint:
    """Integration tests for the anonymous upload path in POST /api/sessions/upload."""

    @pytest.fixture(autouse=True)
    def _rate_limit_reset(self, _reset_rate_limit: None) -> None:
        """Reset anonymous rate limit state before each test in this class."""

    @pytest.fixture
    def _anon_user(self) -> Generator[None, None, None]:
        """Override get_optional_user to return None (anonymous request)."""
        app.dependency_overrides[get_optional_user] = lambda: None
        yield
        # Restore original override from conftest
        from backend.tests.conftest import _TEST_USER

        app.dependency_overrides[get_optional_user] = lambda: _TEST_USER

    @pytest.mark.asyncio
    async def test_anonymous_upload_returns_session_id(
        self, client: AsyncClient, synthetic_csv_bytes: bytes, _anon_user: None
    ) -> None:
        """Anonymous upload (no auth) succeeds and returns a session_id."""
        response = await client.post(
            "/api/sessions/upload",
            files=[("files", ("anon_session.csv", synthetic_csv_bytes, "text/csv"))],
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["session_ids"]) == 1
        assert data["session_ids"][0]

    @pytest.mark.asyncio
    async def test_anonymous_upload_tags_session_as_anonymous(
        self, client: AsyncClient, synthetic_csv_bytes: bytes, _anon_user: None
    ) -> None:
        """Anonymous upload tags the stored session with is_anonymous=True."""
        response = await client.post(
            "/api/sessions/upload",
            files=[("files", ("anon_tag.csv", synthetic_csv_bytes, "text/csv"))],
        )
        assert response.status_code == 200
        sid = response.json()["session_ids"][0]

        sd = session_store.get_session(sid)
        assert sd is not None
        assert sd.is_anonymous is True

    @pytest.mark.asyncio
    async def test_anonymous_upload_does_not_set_user_id(
        self, client: AsyncClient, synthetic_csv_bytes: bytes, _anon_user: None
    ) -> None:
        """Anonymous sessions have no user_id set."""
        response = await client.post(
            "/api/sessions/upload",
            files=[("files", ("anon_noid.csv", synthetic_csv_bytes, "text/csv"))],
        )
        assert response.status_code == 200
        sid = response.json()["session_ids"][0]

        sd = session_store.get_session(sid)
        assert sd is not None
        assert sd.user_id is None

    @pytest.mark.asyncio
    async def test_anonymous_upload_rate_limited_returns_429(
        self, client: AsyncClient, synthetic_csv_bytes: bytes, _anon_user: None
    ) -> None:
        """When the IP rate limit is exceeded, upload returns 429."""
        # Patch check_and_record_anon_upload so it always rejects, regardless of
        # what IP the ASGI test transport presents to the endpoint.
        with patch(
            "backend.api.routers.sessions.check_and_record_anon_upload",
            return_value=(False, "Anonymous session limit reached (3 per day). Sign in."),
        ):
            response = await client.post(
                "/api/sessions/upload",
                files=[("files", ("rate_limited.csv", synthetic_csv_bytes, "text/csv"))],
            )
        assert response.status_code == 429

    @pytest.mark.asyncio
    async def test_anonymous_upload_429_detail_is_informative(
        self, client: AsyncClient, synthetic_csv_bytes: bytes, _anon_user: None
    ) -> None:
        """The 429 response body contains the reason message."""
        reason = "Anonymous session limit reached (3 per day). Sign in to analyze more."
        with patch(
            "backend.api.routers.sessions.check_and_record_anon_upload",
            return_value=(False, reason),
        ):
            response = await client.post(
                "/api/sessions/upload",
                files=[("files", ("rate_limited2.csv", synthetic_csv_bytes, "text/csv"))],
            )
        assert response.status_code == 429
        assert "sign in" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_global_cap_returns_429(
        self, client: AsyncClient, synthetic_csv_bytes: bytes, _anon_user: None
    ) -> None:
        """When the global daily cap is hit, upload returns 429 with capacity message."""
        reason = "We're at capacity for anonymous sessions. Sign in for guaranteed access."
        with patch(
            "backend.api.routers.sessions.check_and_record_anon_upload",
            return_value=(False, reason),
        ):
            response = await client.post(
                "/api/sessions/upload",
                files=[("files", ("global_cap.csv", synthetic_csv_bytes, "text/csv"))],
            )
        assert response.status_code == 429
        assert "capacity" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_authenticated_upload_bypasses_anon_rate_limit(
        self, client: AsyncClient, synthetic_csv_bytes: bytes
    ) -> None:
        """Authenticated users are never checked against anonymous rate limits.

        The conftest _mock_auth fixture has already set get_optional_user to return
        _TEST_USER, so no _anon_user override is needed here.
        """
        # Even if check_and_record_anon_upload would block, authenticated
        # uploads never call it. We verify by ensuring no call is made.
        with patch("backend.api.routers.sessions.check_and_record_anon_upload") as mock_rl:
            response = await client.post(
                "/api/sessions/upload",
                files=[("files", ("auth_ok.csv", synthetic_csv_bytes, "text/csv"))],
            )

        assert response.status_code == 200
        mock_rl.assert_not_called()

    @pytest.mark.asyncio
    async def test_authenticated_upload_sets_user_id(
        self, client: AsyncClient, synthetic_csv_bytes: bytes
    ) -> None:
        """Authenticated uploads store the user_id on the session."""
        response = await client.post(
            "/api/sessions/upload",
            files=[("files", ("auth_user.csv", synthetic_csv_bytes, "text/csv"))],
        )
        assert response.status_code == 200
        sid = response.json()["session_ids"][0]

        sd = session_store.get_session(sid)
        assert sd is not None
        assert sd.user_id == "test-user-123"  # from conftest _TEST_USER

    @pytest.mark.asyncio
    async def test_authenticated_upload_not_tagged_anonymous(
        self, client: AsyncClient, synthetic_csv_bytes: bytes
    ) -> None:
        """Authenticated uploads are never tagged as anonymous."""
        response = await client.post(
            "/api/sessions/upload",
            files=[("files", ("auth_notanon.csv", synthetic_csv_bytes, "text/csv"))],
        )
        assert response.status_code == 200
        sid = response.json()["session_ids"][0]

        sd = session_store.get_session(sid)
        assert sd is not None
        assert sd.is_anonymous is False

    @pytest.mark.asyncio
    async def test_anonymous_upload_records_rate_limit(
        self, client: AsyncClient, synthetic_csv_bytes: bytes, _anon_user: None
    ) -> None:
        """A successful anonymous upload calls check_and_record_anon_upload."""
        with patch(
            "backend.api.routers.sessions.check_and_record_anon_upload",
            return_value=(True, ""),
        ) as mock_rl:
            response = await client.post(
                "/api/sessions/upload",
                files=[("files", ("anon_record.csv", synthetic_csv_bytes, "text/csv"))],
            )
        assert response.status_code == 200
        mock_rl.assert_called_once()

    @pytest.mark.asyncio
    async def test_anonymous_session_is_retrievable_by_id(
        self, client: AsyncClient, synthetic_csv_bytes: bytes, _anon_user: None
    ) -> None:
        """An anonymous session can be retrieved from the store by session_id."""
        response = await client.post(
            "/api/sessions/upload",
            files=[("files", ("anon_access.csv", synthetic_csv_bytes, "text/csv"))],
        )
        assert response.status_code == 200
        sid = response.json()["session_ids"][0]

        sd = session_store.get_session(sid)
        assert sd is not None
        assert sd.session_id == sid


# ---------------------------------------------------------------------------
# Integration tests: claim endpoint
# ---------------------------------------------------------------------------


class TestClaimEndpoint:
    """Integration tests for POST /api/sessions/claim."""

    @pytest.fixture(autouse=True)
    def _patch_db_store(self) -> Generator[None, None, None]:
        """Patch store_session_db to a no-op for claim endpoint tests.

        Claim tests use mocked SessionData which cannot be serialised to SQLite.
        The DB persistence behaviour is covered by test_claim_persists_session_to_db
        which uses a real pipeline-processed session instead.
        """
        with patch(
            "backend.api.routers.sessions.store_session_db",
            new_callable=AsyncMock,
        ):
            yield

    @pytest.mark.asyncio
    async def test_claim_anonymous_session_returns_200(self, client: AsyncClient) -> None:
        """POST /api/sessions/claim with a valid anonymous session returns 200."""
        sd = _make_session_data("claim-sess-001", is_anonymous=True)
        store_session("claim-sess-001", sd)

        response = await client.post(
            "/api/sessions/claim",
            json={"session_id": "claim-sess-001"},
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_claim_response_includes_session_id(self, client: AsyncClient) -> None:
        """The claim success response body references the claimed session_id."""
        sd = _make_session_data("claim-sess-msg", is_anonymous=True)
        store_session("claim-sess-msg", sd)

        response = await client.post(
            "/api/sessions/claim",
            json={"session_id": "claim-sess-msg"},
        )
        assert response.status_code == 200
        assert "claim-sess-msg" in response.json()["message"]

    @pytest.mark.asyncio
    async def test_claim_removes_anonymous_flag(self, client: AsyncClient) -> None:
        """After a successful claim, is_anonymous is False on the session."""
        sd = _make_session_data("claim-sess-002", is_anonymous=True)
        store_session("claim-sess-002", sd)

        await client.post("/api/sessions/claim", json={"session_id": "claim-sess-002"})

        updated = session_store.get_session("claim-sess-002")
        assert updated is not None
        assert updated.is_anonymous is False

    @pytest.mark.asyncio
    async def test_claim_sets_owner_user_id(self, client: AsyncClient) -> None:
        """After claiming, the session's user_id matches the authenticated user."""
        sd = _make_session_data("claim-sess-003", is_anonymous=True)
        store_session("claim-sess-003", sd)

        await client.post("/api/sessions/claim", json={"session_id": "claim-sess-003"})

        updated = session_store.get_session("claim-sess-003")
        assert updated is not None
        assert updated.user_id == "test-user-123"  # from conftest _TEST_USER

    @pytest.mark.asyncio
    async def test_claim_nonexistent_session_returns_404(self, client: AsyncClient) -> None:
        """POST /api/sessions/claim with a non-existent session_id returns 404."""
        response = await client.post(
            "/api/sessions/claim",
            json={"session_id": "does-not-exist"},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_claim_nonexistent_detail_is_informative(self, client: AsyncClient) -> None:
        """The 404 detail for a missing session mentions 'not found' or 'expired'."""
        response = await client.post(
            "/api/sessions/claim",
            json={"session_id": "ghost-session"},
        )
        assert response.status_code == 404
        detail = response.json()["detail"].lower()
        assert "not found" in detail or "expired" in detail

    @pytest.mark.asyncio
    async def test_claim_already_owned_session_returns_400(self, client: AsyncClient) -> None:
        """Claiming a session that is already owned (not anonymous) returns 400."""
        sd = _make_session_data("claim-owned", user_id="user-original", is_anonymous=False)
        store_session("claim-owned", sd)

        response = await client.post(
            "/api/sessions/claim",
            json={"session_id": "claim-owned"},
        )
        assert response.status_code == 400
        assert "claimed" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_claim_requires_authentication(self, client: AsyncClient) -> None:
        """POST /api/sessions/claim with no auth returns 401 or 503."""
        app.dependency_overrides.pop(get_current_user, None)
        try:
            sd = _make_session_data("claim-noauth", is_anonymous=True)
            store_session("claim-noauth", sd)

            response = await client.post(
                "/api/sessions/claim",
                json={"session_id": "claim-noauth"},
            )
            # 401 if no token, 503 if auth backend not configured
            assert response.status_code in (401, 503)
        finally:
            from backend.tests.conftest import _TEST_USER

            app.dependency_overrides[get_current_user] = lambda: _TEST_USER

    @pytest.mark.asyncio
    async def test_double_claim_returns_400(self, client: AsyncClient) -> None:
        """Attempting to claim the same session twice returns 400 on second call."""
        sd = _make_session_data("claim-double", is_anonymous=True)
        store_session("claim-double", sd)

        first = await client.post("/api/sessions/claim", json={"session_id": "claim-double"})
        assert first.status_code == 200

        second = await client.post("/api/sessions/claim", json={"session_id": "claim-double"})
        assert second.status_code == 400

    @pytest.mark.asyncio
    async def test_claim_missing_body_returns_422(self, client: AsyncClient) -> None:
        """POST /api/sessions/claim without session_id field returns 422."""
        response = await client.post("/api/sessions/claim", json={})
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_claim_persists_session_to_db(
        self, client: AsyncClient, synthetic_csv_bytes: bytes
    ) -> None:
        """A claimed session is persisted to the database under the claiming user.

        Uses a real pipeline-processed session to avoid SQLite datetime errors.
        This test does NOT use the _patch_db_store fixture (patching disabled for
        this one test only), so it overrides the class-level autouse patch.
        """
        from backend.api.services.db_session_store import list_sessions_for_user
        from backend.tests.conftest import _test_session_factory

        # Upload as authenticated first to get a real session in memory
        response = await client.post(
            "/api/sessions/upload",
            files=[("files", ("persist_test.csv", synthetic_csv_bytes, "text/csv"))],
        )
        assert response.status_code == 200
        sid = response.json()["session_ids"][0]

        # Manually mark the in-memory session as anonymous so claim can proceed
        sd = session_store.get_session(sid)
        assert sd is not None
        sd.is_anonymous = True
        sd.user_id = None

        # Use real store_session_db for this test by temporarily removing the patch
        with patch(
            "backend.api.routers.sessions.store_session_db",
            wraps=__import__(
                "backend.api.services.db_session_store",
                fromlist=["store_session_db"],
            ).store_session_db,
        ):
            claim_resp = await client.post("/api/sessions/claim", json={"session_id": sid})

        assert claim_resp.status_code == 200

        async with _test_session_factory() as db:
            db_rows = await list_sessions_for_user(db, "test-user-123")
        assert any(row.session_id == sid for row in db_rows)


# ---------------------------------------------------------------------------
# Unit tests: get_session_for_user with anonymous sessions
# ---------------------------------------------------------------------------


class TestAnonymousSessionAccess:
    """Tests for how get_session_for_user handles anonymous sessions."""

    def test_anonymous_session_accessible_to_any_user(self) -> None:
        """Anonymous sessions are accessible to any caller by session_id."""
        sd = _make_session_data("anon-open", is_anonymous=True)
        store_session("anon-open", sd)

        assert get_session_for_user("anon-open", "user-a") is not None
        assert get_session_for_user("anon-open", "user-b") is not None
        assert get_session_for_user("anon-open", "dev-user") is not None

    def test_claimed_session_blocks_other_users(self) -> None:
        """After claiming, only the owner can access the session."""
        sd = _make_session_data("anon-claimed", is_anonymous=True)
        store_session("anon-claimed", sd)
        claim_session("anon-claimed", "owner-user")

        assert get_session_for_user("anon-claimed", "owner-user") is not None
        assert get_session_for_user("anon-claimed", "other-user") is None

    def test_nonexistent_session_returns_none(self) -> None:
        """Accessing a non-existent session always returns None."""
        assert get_session_for_user("not-here", "anyone") is None

    def test_anonymous_session_returns_correct_data(self) -> None:
        """The returned SessionData for an anonymous session is the stored object."""
        sd = _make_session_data("anon-exact", is_anonymous=True)
        store_session("anon-exact", sd)

        result = get_session_for_user("anon-exact", "some-user")
        assert result is sd

    def test_dev_user_can_access_claimed_session(self) -> None:
        """Dev-user bypass still works for claimed (authenticated) sessions."""
        sd = _make_session_data("owned-sess", user_id="real-user", is_anonymous=False)
        store_session("owned-sess", sd)

        assert get_session_for_user("owned-sess", "dev-user") is not None
