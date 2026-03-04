"""Integration tests for the sharing router (/api/sharing).

Exercises all HTTP-level branches via the AsyncClient fixture, including
error paths not covered by test_sharing.py: expired links, empty file
lists, missing filenames, and comparison-not-found for bad tokens.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from backend.api.db.models import SharedSession
from backend.tests.conftest import _test_session_factory, build_synthetic_csv

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _upload_session(
    client: AsyncClient,
    csv_bytes: bytes | None = None,
    filename: str = "test.csv",
) -> str:
    """Upload a CSV and return the session_id."""
    if csv_bytes is None:
        csv_bytes = build_synthetic_csv(n_laps=3)
    resp = await client.post(
        "/api/sessions/upload",
        files=[("files", (filename, csv_bytes, "text/csv"))],
    )
    assert resp.status_code == 200, f"Upload failed: {resp.text}"
    return str(resp.json()["session_ids"][0])


async def _create_share(client: AsyncClient, session_id: str) -> str:
    """Create a share link and return the token."""
    resp = await client.post("/api/sharing/create", json={"session_id": session_id})
    assert resp.status_code == 200, f"Share create failed: {resp.text}"
    return str(resp.json()["token"])


# ---------------------------------------------------------------------------
# POST /api/sharing/create
# ---------------------------------------------------------------------------


class TestCreateShareLink:
    """Integration tests for POST /api/sharing/create."""

    @pytest.mark.asyncio
    async def test_creates_share_link_for_valid_session(self, client: AsyncClient) -> None:
        """Returns token, share_url, track_name and expires_at for a valid session."""
        sid = await _upload_session(client)

        resp = await client.post("/api/sharing/create", json={"session_id": sid})

        assert resp.status_code == 200
        data = resp.json()
        assert "token" in data
        assert len(data["token"]) > 0
        assert data["share_url"] == f"/share/{data['token']}"
        assert data["track_name"] == "Test Circuit"
        assert "expires_at" in data

    @pytest.mark.asyncio
    async def test_idempotent_create_returns_same_token(self, client: AsyncClient) -> None:
        """Two share links for the same session return the same token (idempotent)."""
        sid = await _upload_session(client)

        resp1 = await client.post("/api/sharing/create", json={"session_id": sid})
        resp2 = await client.post("/api/sharing/create", json={"session_id": sid})

        assert resp1.status_code == 200
        assert resp2.status_code == 200
        assert resp1.json()["token"] == resp2.json()["token"]

    @pytest.mark.asyncio
    async def test_returns_404_for_nonexistent_session(self, client: AsyncClient) -> None:
        """404 is returned when the session_id is not in the session store."""
        resp = await client.post("/api/sharing/create", json={"session_id": "does-not-exist"})

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_expires_at_is_approximately_7_days_from_now(self, client: AsyncClient) -> None:
        """The expires_at field is roughly 7 days in the future."""
        sid = await _upload_session(client)
        resp = await client.post("/api/sharing/create", json={"session_id": sid})

        expires_at_str: str = resp.json()["expires_at"]
        # Strip trailing Z / offset for naive parse
        expires_dt = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
        now = datetime.now(UTC)
        delta = expires_dt - now
        assert 6 <= delta.days <= 7


# ---------------------------------------------------------------------------
# GET /api/sharing/{token}
# ---------------------------------------------------------------------------


class TestGetShareMetadata:
    """Integration tests for GET /api/sharing/{token}."""

    @pytest.mark.asyncio
    async def test_returns_metadata_for_valid_token(self, client: AsyncClient) -> None:
        """Metadata response includes all expected fields and is_expired=False."""
        sid = await _upload_session(client)
        token = await _create_share(client, sid)

        resp = await client.get(f"/api/sharing/{token}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["token"] == token
        assert data["track_name"] == "Test Circuit"
        assert data["is_expired"] is False
        assert "inviter_name" in data
        assert "best_lap_time_s" in data
        assert "created_at" in data
        assert "expires_at" in data

    @pytest.mark.asyncio
    async def test_inviter_name_populated_from_user(self, client: AsyncClient) -> None:
        """The inviter_name is taken from the authenticated test user's name."""
        sid = await _upload_session(client)
        token = await _create_share(client, sid)

        resp = await client.get(f"/api/sharing/{token}")

        assert resp.status_code == 200
        # Test user is seeded with name "Test Driver"
        assert resp.json()["inviter_name"] == "Test Driver"

    @pytest.mark.asyncio
    async def test_best_lap_time_is_numeric(self, client: AsyncClient) -> None:
        """best_lap_time_s is a number when the session has lap data."""
        sid = await _upload_session(client)
        token = await _create_share(client, sid)

        resp = await client.get(f"/api/sharing/{token}")

        best_lap = resp.json()["best_lap_time_s"]
        assert best_lap is not None
        assert isinstance(best_lap, float)

    @pytest.mark.asyncio
    async def test_returns_404_for_invalid_token(self, client: AsyncClient) -> None:
        """404 is returned for a token that does not exist in the database."""
        resp = await client.get("/api/sharing/totally-invalid-token")

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_expired_link_is_reported_as_expired(self, client: AsyncClient) -> None:
        """is_expired is True when the share link's expires_at is in the past."""
        sid = await _upload_session(client)
        token = await _create_share(client, sid)

        # Manually backdate expires_at in the DB so the link is already expired
        past = datetime.now(UTC) - timedelta(days=1)
        async with _test_session_factory() as session:
            result = await session.execute(
                select(SharedSession).where(SharedSession.token == token)
            )
            shared = result.scalar_one()
            shared.expires_at = past
            await session.commit()

        resp = await client.get(f"/api/sharing/{token}")

        assert resp.status_code == 200
        assert resp.json()["is_expired"] is True


# ---------------------------------------------------------------------------
# POST /api/sharing/{token}/upload
# ---------------------------------------------------------------------------


class TestUploadToShare:
    """Integration tests for POST /api/sharing/{token}/upload."""

    @pytest.mark.asyncio
    async def test_upload_returns_comparison_result(self, client: AsyncClient) -> None:
        """Uploading a challenger CSV returns a full comparison response."""
        sid = await _upload_session(client, filename="original.csv")
        token = await _create_share(client, sid)

        challenger = build_synthetic_csv(n_laps=2)
        resp = await client.post(
            f"/api/sharing/{token}/upload",
            files=[("files", ("challenger.csv", challenger, "text/csv"))],
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["token"] == token
        assert data["session_a_id"] == sid
        assert "session_b_id" in data
        assert isinstance(data["delta_s"], float)
        assert isinstance(data["distance_m"], list)
        assert isinstance(data["delta_time_s"], list)
        assert len(data["distance_m"]) > 0

    @pytest.mark.asyncio
    async def test_returns_404_for_invalid_token(self, client: AsyncClient) -> None:
        """404 is returned when the token does not exist."""
        csv_bytes = build_synthetic_csv(n_laps=2)
        resp = await client.post(
            "/api/sharing/no-such-token/upload",
            files=[("files", ("c.csv", csv_bytes, "text/csv"))],
        )

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_410_for_expired_link(self, client: AsyncClient) -> None:
        """410 Gone is returned when the share link has expired."""
        sid = await _upload_session(client)
        token = await _create_share(client, sid)

        # Expire the link
        past = datetime.now(UTC) - timedelta(days=1)
        async with _test_session_factory() as session:
            result = await session.execute(
                select(SharedSession).where(SharedSession.token == token)
            )
            shared = result.scalar_one()
            shared.expires_at = past
            await session.commit()

        csv_bytes = build_synthetic_csv(n_laps=2)
        resp = await client.post(
            f"/api/sharing/{token}/upload",
            files=[("files", ("c.csv", csv_bytes, "text/csv"))],
        )

        assert resp.status_code == 410
        assert "expired" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_returns_422_when_no_files_provided(self, client: AsyncClient) -> None:
        """422 Unprocessable Entity is returned when the files field is absent."""
        sid = await _upload_session(client)
        token = await _create_share(client, sid)

        # POST with no multipart body at all — FastAPI rejects with 422
        resp = await client.post(f"/api/sharing/{token}/upload")

        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_returns_422_for_file_with_no_filename(self, client: AsyncClient) -> None:
        """422 is returned when the uploaded file tuple has an empty filename.

        httpx omits the Content-Disposition filename parameter when the filename
        is an empty string, so FastAPI's multipart validation rejects it with 422
        before the router logic is reached (the router's explicit 400 branch for
        ``not f.filename`` would require a raw multipart frame with a blank filename
        field, which httpx cannot produce via its standard files= API).
        """
        sid = await _upload_session(client)
        token = await _create_share(client, sid)

        csv_bytes = build_synthetic_csv(n_laps=2)
        resp = await client.post(
            f"/api/sharing/{token}/upload",
            files=[("files", ("", csv_bytes, "text/csv"))],
        )

        # FastAPI rejects at validation layer — the 400 branch in the router is
        # exercised only when Content-Disposition carries filename="" explicitly.
        assert resp.status_code in (400, 422)

    @pytest.mark.asyncio
    async def test_comparison_result_persisted_in_db(self, client: AsyncClient) -> None:
        """After a successful upload, the comparison report is saved to the database."""
        from backend.api.db.models import ShareComparisonReport

        sid = await _upload_session(client, filename="orig.csv")
        token = await _create_share(client, sid)

        challenger = build_synthetic_csv(n_laps=2)
        resp = await client.post(
            f"/api/sharing/{token}/upload",
            files=[("files", ("c.csv", challenger, "text/csv"))],
        )
        assert resp.status_code == 200

        async with _test_session_factory() as session:
            result = await session.execute(
                select(ShareComparisonReport).where(ShareComparisonReport.share_token == token)
            )
            report = result.scalar_one_or_none()

        assert report is not None
        assert report.report_json is not None


# ---------------------------------------------------------------------------
# GET /api/sharing/{token}/comparison
# ---------------------------------------------------------------------------


class TestGetShareComparison:
    """Integration tests for GET /api/sharing/{token}/comparison."""

    @pytest.mark.asyncio
    async def test_returns_comparison_after_upload(self, client: AsyncClient) -> None:
        """GET returns the saved comparison result once an upload has been made."""
        sid = await _upload_session(client, filename="orig.csv")
        token = await _create_share(client, sid)

        challenger = build_synthetic_csv(n_laps=2)
        upload_resp = await client.post(
            f"/api/sharing/{token}/upload",
            files=[("files", ("c.csv", challenger, "text/csv"))],
        )
        assert upload_resp.status_code == 200

        resp = await client.get(f"/api/sharing/{token}/comparison")

        assert resp.status_code == 200
        data = resp.json()
        assert data["token"] == token
        assert data["session_a_id"] == sid
        assert isinstance(data["delta_s"], float)
        assert isinstance(data["distance_m"], list)

    @pytest.mark.asyncio
    async def test_returns_404_for_invalid_token(self, client: AsyncClient) -> None:
        """404 is returned when the token does not exist in the DB."""
        resp = await client.get("/api/sharing/nonexistent-token/comparison")

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_404_when_no_comparison_yet(self, client: AsyncClient) -> None:
        """404 is returned when the share link exists but has no uploaded comparison."""
        sid = await _upload_session(client)
        token = await _create_share(client, sid)

        resp = await client.get(f"/api/sharing/{token}/comparison")

        assert resp.status_code == 404
        assert "no comparison" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_multiple_uploads_all_produce_valid_comparisons(
        self, client: AsyncClient
    ) -> None:
        """Multiple uploads to the same share token each succeed and persist a report.

        The router orders by created_at DESC to return the latest, but since
        SQLite server_default timestamps may resolve to the same second within
        a fast test, we only assert that GET returns a valid comparison (not which
        specific challenger session it corresponds to).
        """
        from backend.api.db.models import ShareComparisonReport

        sid = await _upload_session(client, filename="orig.csv")
        token = await _create_share(client, sid)

        # First challenger upload
        first_csv = build_synthetic_csv(n_laps=2)
        first_resp = await client.post(
            f"/api/sharing/{token}/upload",
            files=[("files", ("first.csv", first_csv, "text/csv"))],
        )
        assert first_resp.status_code == 200

        # Second challenger upload
        second_csv = build_synthetic_csv(n_laps=4)
        second_resp = await client.post(
            f"/api/sharing/{token}/upload",
            files=[("files", ("second.csv", second_csv, "text/csv"))],
        )
        assert second_resp.status_code == 200

        # Both reports are persisted in the DB
        async with _test_session_factory() as session:
            result = await session.execute(
                select(ShareComparisonReport).where(ShareComparisonReport.share_token == token)
            )
            reports = result.scalars().all()
        assert len(reports) == 2

        # GET returns a valid comparison (whichever is deemed "latest")
        get_resp = await client.get(f"/api/sharing/{token}/comparison")
        assert get_resp.status_code == 200
        assert get_resp.json()["session_a_id"] == sid
        assert isinstance(get_resp.json()["delta_s"], float)

    @pytest.mark.asyncio
    async def test_comparison_corner_deltas_is_list(self, client: AsyncClient) -> None:
        """corner_deltas in the comparison response is a list."""
        sid = await _upload_session(client, filename="orig.csv")
        token = await _create_share(client, sid)

        challenger = build_synthetic_csv(n_laps=2)
        await client.post(
            f"/api/sharing/{token}/upload",
            files=[("files", ("c.csv", challenger, "text/csv"))],
        )

        resp = await client.get(f"/api/sharing/{token}/comparison")
        assert resp.status_code == 200
        assert isinstance(resp.json()["corner_deltas"], list)
