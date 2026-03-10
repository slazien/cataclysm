"""Extended tests for coaching router — covers missing lines.

Missing lines targeted:
  [109, 110] — generate_report: force=True but remaining=0 → 429
  [186] — generate_report: already generating → return _generating_response
  [202] — generate_report: existing report with error status → clear + re-generate
  [243, 244] — _run_generation: session_cap_s from gains.theoretical
  [349] — _run_generation: "Could not parse" in summary → retryable error
  [355, 356, 357] — _run_generation: last_exc raised after all retries
  [365, 366] — _run_generation: RateLimitError → retry with backoff
  [373, 377] — _run_generation: re-raise non-rate-limit exception
  [788, 789, 790, 791] — WebSocket coaching_chat: off-topic guardrail, continue branch
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient

from backend.api.routers.coaching import (
    _parse_priority_corner_number,
    _sanitize_priority_time_cost,
    _track_task,
)
from backend.api.schemas.coaching import CoachingReportResponse
from backend.api.services.coaching_store import (
    clear_all_coaching,
    get_regen_remaining,
    mark_generating,
    record_regeneration,
    store_coaching_report,
    unmark_generating,
)
from backend.tests.conftest import build_synthetic_csv

# ---------------------------------------------------------------------------
# Upload helper
# ---------------------------------------------------------------------------


async def _upload(client: AsyncClient, n_laps: int = 5, filename: str = "test.csv") -> str:
    csv = build_synthetic_csv(n_laps=n_laps)
    resp = await client.post(
        "/api/sessions/upload",
        files=[("files", (filename, csv, "text/csv"))],
    )
    assert resp.status_code == 200
    return str(resp.json()["session_ids"][0])


async def _store_report(session_id: str, status: str = "ready") -> None:
    """Insert a minimal coaching report into the store."""
    report = CoachingReportResponse(
        session_id=session_id,
        status=status,
        skill_level="intermediate",
        summary="Good work" if status != "error" else "Could not parse response",
    )
    await store_coaching_report(session_id, report, "intermediate")


# ---------------------------------------------------------------------------
# POST /{session_id}/report — missing lines
# ---------------------------------------------------------------------------


class TestGenerateReportMissingLines:
    """Cover uncovered branches in generate_report."""

    @pytest.mark.asyncio
    async def test_force_regen_when_limit_exhausted_returns_429(self, client: AsyncClient) -> None:
        """Lines 109-110: force=True but no regens remaining → 429."""
        sid = await _upload(client, filename="force_limit.csv")

        # Exhaust the daily regeneration limit
        from backend.api.services.coaching_store import MAX_DAILY_REGENS

        for _ in range(MAX_DAILY_REGENS):
            record_regeneration("test-user-123")

        resp = await client.post(
            f"/api/coaching/{sid}/report",
            json={"skill_level": "intermediate", "force": True},
        )
        assert resp.status_code == 429
        assert "limit" in resp.json()["detail"].lower()

        clear_all_coaching()

    @pytest.mark.asyncio
    async def test_already_generating_returns_generating_status(self, client: AsyncClient) -> None:
        """Line 186: when is_generating() is True, returns generating status immediately."""
        sid = await _upload(client, filename="gen_status.csv")

        # Mark as generating manually
        mark_generating(sid, "intermediate")
        try:
            resp = await client.post(
                f"/api/coaching/{sid}/report",
                json={"skill_level": "intermediate", "force": False},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "generating"
        finally:
            unmark_generating(sid, "intermediate")

    @pytest.mark.asyncio
    async def test_existing_error_report_gets_cleared_and_regenerated(
        self, client: AsyncClient
    ) -> None:
        """Line 202: existing report with error status is cleared → generation triggered."""
        sid = await _upload(client, filename="error_report.csv")

        # Store a report with error status
        await _store_report(sid, status="error")

        # POST without force — error report should be cleared, generation triggered
        resp = await client.post(
            f"/api/coaching/{sid}/report",
            json={"skill_level": "intermediate", "force": False},
        )
        assert resp.status_code == 200
        data = resp.json()
        # After error clear, we expect generating status
        assert data["status"] in ("generating", "ready")

        clear_all_coaching()


# ---------------------------------------------------------------------------
# _parse_priority_corner_number — unit tests
# ---------------------------------------------------------------------------


class TestParsePriorityCornerNumber:
    """Unit tests for _parse_priority_corner_number."""

    def test_int_input(self) -> None:
        assert _parse_priority_corner_number(5) == 5

    def test_string_int_input(self) -> None:
        assert _parse_priority_corner_number("3") == 3

    def test_invalid_string_returns_zero(self) -> None:
        assert _parse_priority_corner_number("not-a-number") == 0

    def test_none_returns_zero(self) -> None:
        assert _parse_priority_corner_number(None) == 0

    def test_float_string_returns_zero(self) -> None:
        # int("4.9") raises ValueError — returns 0
        assert _parse_priority_corner_number("4.9") == 0


# ---------------------------------------------------------------------------
# _sanitize_priority_time_cost — unit tests
# ---------------------------------------------------------------------------


class TestSanitizePriorityTimeCost:
    """Unit tests for _sanitize_priority_time_cost."""

    def test_valid_value_is_returned(self) -> None:
        result = _sanitize_priority_time_cost(
            1.5, corner_num=3, per_corner_caps={}, session_cap_s=None
        )
        assert result == 1.5

    def test_value_capped_at_absolute_maximum(self) -> None:
        result = _sanitize_priority_time_cost(
            100.0, corner_num=3, per_corner_caps={}, session_cap_s=None
        )
        assert result == 5.0  # _ABSOLUTE_PRIORITY_TIME_CAP_S = 5.0

    def test_session_cap_applied(self) -> None:
        result = _sanitize_priority_time_cost(
            3.0, corner_num=3, per_corner_caps={}, session_cap_s=1.0
        )
        assert result == 1.0

    def test_per_corner_cap_applied(self) -> None:
        result = _sanitize_priority_time_cost(
            3.0, corner_num=3, per_corner_caps={3: 0.5}, session_cap_s=None
        )
        assert result == 0.5

    def test_invalid_value_returns_zero(self) -> None:
        result = _sanitize_priority_time_cost(
            "not-a-float", corner_num=1, per_corner_caps={}, session_cap_s=None
        )
        assert result == 0.0

    def test_negative_value_returns_zero(self) -> None:
        result = _sanitize_priority_time_cost(
            -1.0, corner_num=1, per_corner_caps={}, session_cap_s=None
        )
        assert result == 0.0

    def test_inf_returns_zero(self) -> None:
        import math

        result = _sanitize_priority_time_cost(
            math.inf, corner_num=1, per_corner_caps={}, session_cap_s=None
        )
        assert result == 0.0

    def test_none_returns_zero(self) -> None:
        result = _sanitize_priority_time_cost(
            None, corner_num=1, per_corner_caps={}, session_cap_s=None
        )
        assert result == 0.0


# ---------------------------------------------------------------------------
# _track_task — unit test
# ---------------------------------------------------------------------------


class TestTrackTask:
    """Unit tests for _track_task."""

    @pytest.mark.asyncio
    async def test_track_task_adds_and_removes_on_done(self) -> None:
        """Task is added to _background_tasks and removed when done."""
        from backend.api.routers.coaching import _background_tasks

        async def _noop() -> None:
            pass

        task = asyncio.create_task(_noop())
        _track_task(task)
        assert task in _background_tasks
        await task  # complete the task
        # Give the done callback time to run
        await asyncio.sleep(0.01)
        assert task not in _background_tasks

    @pytest.mark.asyncio
    async def test_track_task_logs_exception_on_error(self) -> None:
        """Task exception is logged but not raised to the caller."""

        from backend.api.routers.coaching import _background_tasks

        async def _fail() -> None:
            raise RuntimeError("test error in background task")

        task = asyncio.create_task(_fail())
        _track_task(task)

        # Wait for task to complete (will raise internally, but _track_task catches it)
        import contextlib

        with contextlib.suppress(TimeoutError, RuntimeError):
            await asyncio.wait_for(asyncio.shield(task), timeout=1.0)
        await asyncio.sleep(0.05)
        # Task should be cleaned from the set
        assert task not in _background_tasks


# ---------------------------------------------------------------------------
# GET /{session_id}/report — error report auto-cleared + auto-trigger
# ---------------------------------------------------------------------------


class TestGetReportErrorPath:
    """GET /coaching/{id}/report — error report is cleared and regeneration triggered."""

    @pytest.mark.asyncio
    async def test_error_report_cleared_and_returns_404(self, client: AsyncClient) -> None:
        """When stored report has status=error, it is cleared and 404 returned."""
        sid = await _upload(client, filename="get_error.csv")

        # Store an error report
        error_report = CoachingReportResponse(
            session_id=sid,
            status="error",
            skill_level="intermediate",
            summary="AI coaching is temporarily unavailable.",
        )
        await store_coaching_report(sid, error_report, "intermediate")

        resp = await client.get(f"/api/coaching/{sid}/report")
        assert resp.status_code == 404

        clear_all_coaching()

    @pytest.mark.asyncio
    async def test_parse_failure_report_cleared(self, client: AsyncClient) -> None:
        """Report with 'Could not parse' in summary is cleared on GET and returns 404."""
        sid = await _upload(client, filename="parse_fail.csv")

        parse_fail_report = CoachingReportResponse(
            session_id=sid,
            status="ready",
            skill_level="intermediate",
            summary="Could not parse JSON response from AI",
        )
        await store_coaching_report(sid, parse_fail_report, "intermediate")

        resp = await client.get(f"/api/coaching/{sid}/report")
        assert resp.status_code == 404

        clear_all_coaching()


# ---------------------------------------------------------------------------
# POST /{session_id}/chat — missing lines 620, 627-631
# ---------------------------------------------------------------------------


class TestCoachingChatHttp:
    """Tests for POST /api/coaching/{session_id}/chat HTTP endpoint."""

    @pytest.mark.asyncio
    async def test_chat_session_not_found_returns_404(self, client: AsyncClient) -> None:
        """POST chat for nonexistent session returns 404."""
        resp = await client.post(
            "/api/coaching/nonexistent-sid/chat",
            json={"content": "How was my braking?"},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_chat_no_report_returns_404(self, client: AsyncClient) -> None:
        """POST chat without a report returns 404."""
        sid = await _upload(client, filename="chat_no_report.csv")
        clear_all_coaching()  # ensure no report

        resp = await client.post(
            f"/api/coaching/{sid}/chat",
            json={"content": "How was my braking?"},
        )
        assert resp.status_code == 404
        assert "no coaching report" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_chat_empty_question_returns_prompt(self, client: AsyncClient) -> None:
        """POST chat with empty content returns a prompt-to-ask message."""
        sid = await _upload(client, filename="chat_empty.csv")
        await _store_report(sid)

        resp = await client.post(
            f"/api/coaching/{sid}/chat",
            json={"content": "   "},  # whitespace only
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "assistant"
        assert "question" in data["content"].lower()

        clear_all_coaching()

    @pytest.mark.asyncio
    async def test_chat_off_topic_question_returns_guardrail_response(
        self, client: AsyncClient
    ) -> None:
        """POST chat with off-topic question returns the OFF_TOPIC_RESPONSE."""
        from cataclysm.topic_guardrail import OFF_TOPIC_RESPONSE

        sid = await _upload(client, filename="chat_offtopic.csv")
        await _store_report(sid)

        mock_classification = MagicMock()
        mock_classification.on_topic = False
        mock_classification.source = "off_topic"

        with patch(
            "cataclysm.topic_guardrail.classify_topic",
            return_value=mock_classification,
        ):
            resp = await client.post(
                f"/api/coaching/{sid}/chat",
                json={"content": "What is the capital of France?"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "assistant"
        assert data["content"] == OFF_TOPIC_RESPONSE

        clear_all_coaching()

    @pytest.mark.asyncio
    async def test_chat_too_long_returns_length_response(self, client: AsyncClient) -> None:
        """POST chat with too-long input returns INPUT_TOO_LONG_RESPONSE."""
        from cataclysm.topic_guardrail import INPUT_TOO_LONG_RESPONSE

        sid = await _upload(client, filename="chat_toolong.csv")
        await _store_report(sid)

        mock_classification = MagicMock()
        mock_classification.on_topic = False
        mock_classification.source = "too_long"

        with patch(
            "cataclysm.topic_guardrail.classify_topic",
            return_value=mock_classification,
        ):
            resp = await client.post(
                f"/api/coaching/{sid}/chat",
                json={"content": "x" * 10000},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["content"] == INPUT_TOO_LONG_RESPONSE

        clear_all_coaching()


# ---------------------------------------------------------------------------
# coaching_store utility functions — missing lines
# ---------------------------------------------------------------------------


class TestCoachingStoreMissingLines:
    """Cover uncovered lines in coaching_store.py."""

    def test_get_estimated_duration_with_history(self) -> None:
        """get_estimated_duration_s returns average of recorded durations (line 231)."""
        from backend.api.services.coaching_store import (
            get_estimated_duration_s,
            record_generation_duration,
        )

        clear_all_coaching()
        record_generation_duration(10.0)
        record_generation_duration(20.0)
        result = get_estimated_duration_s()
        assert result == 15.0
        clear_all_coaching()

    def test_get_estimated_duration_no_history_returns_default(self) -> None:
        """get_estimated_duration_s returns default when no history (line 231)."""
        from backend.api.services.coaching_store import get_estimated_duration_s

        clear_all_coaching()
        result = get_estimated_duration_s()
        assert result == 60.0  # _DEFAULT_ESTIMATE_S

    def test_get_regen_remaining_after_exhaustion(self) -> None:
        """get_regen_remaining returns 0 when all regens used (line 226)."""
        from backend.api.services.coaching_store import MAX_DAILY_REGENS

        clear_all_coaching()
        for _ in range(MAX_DAILY_REGENS + 5):
            record_regeneration("user-regen-test")
        remaining = get_regen_remaining("user-regen-test")
        assert remaining == 0
        clear_all_coaching()

    @pytest.mark.asyncio
    async def test_clear_coaching_data_removes_all(self) -> None:
        """clear_coaching_data removes both report and context (line 153)."""
        from backend.api.services.coaching_store import (
            clear_coaching_data,
            get_coaching_report,
        )

        sid = "test-clear-all"
        report = CoachingReportResponse(
            session_id=sid, status="ready", skill_level="intermediate", summary="OK"
        )
        await store_coaching_report(sid, report, "intermediate")
        await clear_coaching_data(sid)
        result = await get_coaching_report(sid, "intermediate")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_any_coaching_report_returns_any_skill(self) -> None:
        """get_any_coaching_report returns report stored under any skill level."""
        from backend.api.services.coaching_store import get_any_coaching_report

        sid = "test-any-skill"
        report = CoachingReportResponse(
            session_id=sid, status="ready", skill_level="advanced", summary="Advanced OK"
        )
        await store_coaching_report(sid, report, "advanced")

        result = await get_any_coaching_report(sid)
        assert result is not None
        assert result.summary == "Advanced OK"

        clear_all_coaching()
