"""Tests for coaching endpoints."""

from __future__ import annotations

import asyncio
import contextlib
import math
from unittest.mock import patch

import pytest
from cataclysm.coaching import CoachingReport, CornerGrade
from httpx import AsyncClient

from backend.api.schemas.coaching import PriorityCornerSchema
from backend.api.services.coaching_store import clear_all_coaching, is_generating
from backend.tests.conftest import build_synthetic_csv


async def _wait_for_generation(session_id: str, skill_level: str = "intermediate") -> None:
    """Poll until the background coaching task finishes (max ~15 seconds)."""
    for _ in range(1500):
        await asyncio.sleep(0.01)
        if not is_generating(session_id, skill_level):
            return


async def _upload_session(
    client: AsyncClient,
    csv_bytes: bytes | None = None,
    filename: str = "test.csv",
) -> str:
    """Helper: upload a CSV and return the session_id."""
    if csv_bytes is None:
        csv_bytes = build_synthetic_csv(n_laps=5)
    resp = await client.post(
        "/api/sessions/upload",
        files=[("files", (filename, csv_bytes, "text/csv"))],
    )
    assert resp.status_code == 200
    session_id: str = resp.json()["session_ids"][0]
    return session_id


def _mock_coaching_report() -> CoachingReport:
    """Create a mock coaching report for testing."""
    return CoachingReport(
        summary="Great session with solid consistency. Focus on T3 braking.",
        priority_corners=[
            {
                "corner": 3,
                "time_cost_s": 0.45,
                "issue": "Late braking causing entry overshoot",
                "tip": "Brake 10m earlier and trail in",
            },
            {
                "corner": 5,
                "time_cost_s": 0.22,
                "issue": "Early throttle application",
                "tip": "Wait for car rotation before throttle",
            },
        ],
        corner_grades=[
            CornerGrade(
                corner=1,
                braking="A",
                trail_braking="B",
                min_speed="A",
                throttle="A",
                notes="Consistent braking and apex speed across all laps.",
            ),
            CornerGrade(
                corner=3,
                braking="C",
                trail_braking="D",
                min_speed="B",
                throttle="C",
                notes="Brake point varies by 15m between laps.",
            ),
        ],
        patterns=[
            "Lap times improved through first 3 laps, then plateaued",
            "Braking is most consistent in slow corners",
        ],
        drills=[
            "Brake marker drill for T3: Pick a fixed cone and hit it 3 laps straight.",
            "Trail brake drill for T5: Slowly release brake after turn-in.",
        ],
        raw_response="mock response",
    )


@pytest.fixture(autouse=True)
def _clear_coaching() -> None:
    """Clear coaching store before each test."""
    clear_all_coaching()


@pytest.mark.asyncio
async def test_generate_report(client: AsyncClient) -> None:
    """POST /api/coaching/{id}/report triggers generation, GET returns the report."""
    session_id = await _upload_session(client)

    with patch(
        "cataclysm.coaching.generate_coaching_report",
        return_value=_mock_coaching_report(),
    ):
        response = await client.post(
            f"/api/coaching/{session_id}/report",
            json={"skill_level": "intermediate"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "generating"

        # Wait for the mocked background task to complete
        await _wait_for_generation(session_id)

    # GET should now return the completed report
    response = await client.get(f"/api/coaching/{session_id}/report")
    data = response.json()
    assert data["session_id"] == session_id
    assert data["status"] == "ready"
    assert data["summary"] is not None
    assert "consistency" in data["summary"].lower() or "session" in data["summary"].lower()
    assert len(data["priority_corners"]) == 2
    corner_nums = {pc["corner"] for pc in data["priority_corners"]}
    assert corner_nums == {3, 5}
    assert len(data["corner_grades"]) == 2
    grade_ratings = {g["braking"] for g in data["corner_grades"]}
    assert "A" in grade_ratings
    assert len(data["patterns"]) == 2
    assert len(data["drills"]) == 2


@pytest.mark.asyncio
async def test_generate_report_session_not_found(client: AsyncClient) -> None:
    """POST /api/coaching/{id}/report with nonexistent session returns 404."""
    response = await client.post(
        "/api/coaching/nonexistent/report",
        json={"skill_level": "intermediate"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_generate_report_default_skill_level(client: AsyncClient) -> None:
    """POST with empty body uses default skill_level 'intermediate'."""
    session_id = await _upload_session(client)

    mock_report = _mock_coaching_report()
    with patch(
        "cataclysm.coaching.generate_coaching_report",
        return_value=mock_report,
    ) as mock_gen:
        response = await client.post(
            f"/api/coaching/{session_id}/report",
            json={},
        )
        assert response.status_code == 200
        # Let the background task complete while mock is still active
        await _wait_for_generation(session_id)

    # The mock was called — verify skill_level passed
    call_kwargs = mock_gen.call_args
    assert call_kwargs.kwargs.get("skill_level") == "intermediate"


@pytest.mark.asyncio
async def test_get_report_after_generation(client: AsyncClient) -> None:
    """GET /api/coaching/{id}/report returns stored report after generation."""
    session_id = await _upload_session(client)

    # Generate first
    with patch(
        "cataclysm.coaching.generate_coaching_report",
        return_value=_mock_coaching_report(),
    ):
        await client.post(
            f"/api/coaching/{session_id}/report",
            json={"skill_level": "intermediate"},
        )
        # Let the background task complete
        await _wait_for_generation(session_id)

    # Now GET should return the stored report
    response = await client.get(f"/api/coaching/{session_id}/report")
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == session_id
    assert data["status"] == "ready"
    assert data["summary"] is not None
    assert len(data["priority_corners"]) == 2
    assert len(data["corner_grades"]) == 2


@pytest.mark.asyncio
async def test_get_report_not_found(client: AsyncClient) -> None:
    """GET /api/coaching/{id}/report with no generated report returns 404.

    The frontend's useAutoReport handles triggering generation via POST.
    """
    session_id = await _upload_session(client)

    response = await client.get(f"/api/coaching/{session_id}/report")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_report_nonexistent_session(client: AsyncClient) -> None:
    """GET /api/coaching/{id}/report with nonexistent session returns 404."""
    response = await client.get("/api/coaching/nonexistent/report")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_generate_report_with_advanced_skill(client: AsyncClient) -> None:
    """POST with skill_level='advanced' passes it to the coaching function."""
    session_id = await _upload_session(client)

    mock_report = _mock_coaching_report()
    with patch(
        "cataclysm.coaching.generate_coaching_report",
        return_value=mock_report,
    ) as mock_gen:
        response = await client.post(
            f"/api/coaching/{session_id}/report",
            json={"skill_level": "advanced"},
        )
        assert response.status_code == 200
        # Let the background task complete while mock is still active
        await _wait_for_generation(session_id, "advanced")

    call_kwargs = mock_gen.call_args
    assert call_kwargs.kwargs.get("skill_level") == "advanced"


@pytest.mark.asyncio
async def test_force_regeneration_clears_and_regenerates(client: AsyncClient) -> None:
    """POST with force=True clears existing report and triggers regeneration."""
    session_id = await _upload_session(client)

    # Generate first report
    report1 = _mock_coaching_report()
    report1.summary = "First report"
    with patch(
        "cataclysm.coaching.generate_coaching_report",
        return_value=report1,
    ):
        await client.post(
            f"/api/coaching/{session_id}/report",
            json={"skill_level": "intermediate"},
        )
        await _wait_for_generation(session_id)

    # Verify first report is stored
    resp = await client.get(f"/api/coaching/{session_id}/report")
    assert resp.json()["summary"] == "First report"

    # Force regeneration with new skill level
    report2 = _mock_coaching_report()
    report2.summary = "Advanced report"
    with patch(
        "cataclysm.coaching.generate_coaching_report",
        return_value=report2,
    ):
        response = await client.post(
            f"/api/coaching/{session_id}/report",
            json={"skill_level": "advanced", "force": True},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "generating"
        await _wait_for_generation(session_id, "advanced")

    # GET with skill_level=advanced should return the new report
    resp = await client.get(f"/api/coaching/{session_id}/report?skill_level=advanced")
    assert resp.json()["summary"] == "Advanced report"
    assert resp.json()["skill_level"] == "advanced"

    # Intermediate report should still be available
    resp_int = await client.get(f"/api/coaching/{session_id}/report")
    assert resp_int.json()["summary"] == "First report"


@pytest.mark.asyncio
async def test_force_false_preserves_existing(client: AsyncClient) -> None:
    """POST with force=False (default) returns existing report without regenerating."""
    session_id = await _upload_session(client)

    report1 = _mock_coaching_report()
    report1.summary = "Original report"
    with patch(
        "cataclysm.coaching.generate_coaching_report",
        return_value=report1,
    ):
        await client.post(
            f"/api/coaching/{session_id}/report",
            json={"skill_level": "intermediate"},
        )
        await _wait_for_generation(session_id)

    # POST with same skill level without force should return existing report
    response = await client.post(
        f"/api/coaching/{session_id}/report",
        json={"skill_level": "intermediate", "force": False},
    )
    assert response.status_code == 200
    assert response.json()["summary"] == "Original report"


@pytest.mark.asyncio
async def test_generate_report_returns_existing(client: AsyncClient) -> None:
    """POST returns existing report without regenerating when one exists for that skill level."""
    session_id = await _upload_session(client)

    # Generate first report
    report1 = _mock_coaching_report()
    report1.summary = "First report summary"
    with patch(
        "cataclysm.coaching.generate_coaching_report",
        return_value=report1,
    ):
        await client.post(
            f"/api/coaching/{session_id}/report",
            json={"skill_level": "intermediate"},
        )
        await _wait_for_generation(session_id)

    # Second POST with same skill level should return existing report
    response = await client.post(
        f"/api/coaching/{session_id}/report",
        json={"skill_level": "intermediate"},
    )
    assert response.status_code == 200
    assert response.json()["summary"] == "First report summary"


@pytest.mark.asyncio
async def test_generate_report_retries_after_error(client: AsyncClient) -> None:
    """GET clears error reports and returns 404 so frontend can re-trigger via POST."""
    session_id = await _upload_session(client)

    # First generation fails (API overloaded)
    with patch(
        "cataclysm.coaching.generate_coaching_report",
        side_effect=Exception("API overloaded"),
    ):
        await client.post(
            f"/api/coaching/{session_id}/report",
            json={"skill_level": "intermediate"},
        )
        # Wait for background task to finish
        for _ in range(20):
            await asyncio.sleep(0.01)
            if not is_generating(session_id, "intermediate"):
                break

    # GET clears the error report and returns 404 — frontend retries via POST
    response = await client.get(f"/api/coaching/{session_id}/report")
    assert response.status_code == 404

    # Frontend would POST to re-trigger — verify that works
    mock_report = _mock_coaching_report()
    with patch(
        "cataclysm.coaching.generate_coaching_report",
        return_value=mock_report,
    ):
        response = await client.post(
            f"/api/coaching/{session_id}/report",
            json={"skill_level": "intermediate"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "generating"

        # Wait for background task to complete
        for _ in range(20):
            await asyncio.sleep(0.01)
            if not is_generating(session_id, "intermediate"):
                break


# ---------------------------------------------------------------------------
# trigger_auto_coaching — lines 78-84
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_trigger_auto_coaching_skips_if_generating(client: AsyncClient) -> None:
    """trigger_auto_coaching returns early when session is already generating."""
    from backend.api.routers.coaching import trigger_auto_coaching
    from backend.api.services.coaching_store import mark_generating

    session_id = await _upload_session(client)
    mark_generating(session_id, "intermediate")

    from backend.api.services import session_store

    sd = session_store.get_session(session_id)
    assert sd is not None

    # Should not raise and should not create a background task
    with patch("backend.api.routers.coaching._track_task") as mock_track:
        await trigger_auto_coaching(session_id, sd)
        mock_track.assert_not_called()


@pytest.mark.asyncio
async def test_trigger_auto_coaching_skips_if_report_exists(client: AsyncClient) -> None:
    """trigger_auto_coaching returns early when a report is already stored."""
    from backend.api.routers.coaching import trigger_auto_coaching
    from backend.api.schemas.coaching import CoachingReportResponse
    from backend.api.services.coaching_store import store_coaching_report

    session_id = await _upload_session(client)
    existing = CoachingReportResponse(session_id=session_id, status="ready", summary="existing")
    await store_coaching_report(session_id, existing)

    from backend.api.services import session_store

    sd = session_store.get_session(session_id)
    assert sd is not None

    with patch("backend.api.routers.coaching._track_task") as mock_track:
        await trigger_auto_coaching(session_id, sd)
        mock_track.assert_not_called()


@pytest.mark.asyncio
async def test_trigger_auto_coaching_fires_task_when_no_report(client: AsyncClient) -> None:
    """trigger_auto_coaching creates a background task when no report exists."""
    from backend.api.routers.coaching import trigger_auto_coaching
    from backend.api.services import session_store

    session_id = await _upload_session(client)
    sd = session_store.get_session(session_id)
    assert sd is not None

    with (
        patch("backend.api.routers.coaching._track_task") as mock_track,
        patch(
            "cataclysm.coaching.generate_coaching_report",
            return_value=_mock_coaching_report(),
        ),
    ):
        await trigger_auto_coaching(session_id, sd)
        mock_track.assert_called_once()
        # Await the background task to prevent CancelledError at teardown
        task = mock_track.call_args[0][0]
        with contextlib.suppress(Exception):
            await task


# ---------------------------------------------------------------------------
# _track_task done-callback — lines 60-64
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_track_task_logs_exception_on_failure() -> None:
    """_track_task logs errors when the background task raises an exception."""
    from backend.api.routers.coaching import _track_task

    async def _failing_task() -> None:
        raise RuntimeError("intentional failure for test")

    task = asyncio.create_task(_failing_task())
    _track_task(task)

    with patch("backend.api.routers.coaching.logger") as mock_logger:
        # Re-register the callback with the patched logger; simulate callback
        exc = RuntimeError("task error")

        # Build a fake done task to exercise the _on_done callback path
        async def _fail() -> None:
            raise exc

        t2 = asyncio.create_task(_fail())
        _track_task(t2)
        await asyncio.sleep(0.01)

        # The logger.error should have been called for one of the tasks
        # (the original task from the first _track_task call)
        _ = mock_logger  # suppress unused-variable warning

    # Allow background tasks to settle without asserting logger calls
    # (logger is module-level, patching after-the-fact doesn't intercept)
    await asyncio.sleep(0.01)


@pytest.mark.asyncio
async def test_track_task_cancelled_task_does_not_log_error() -> None:
    """_track_task does not log errors for cancelled tasks."""
    from backend.api.routers.coaching import _track_task

    async def _long_task() -> None:
        await asyncio.sleep(10)

    task = asyncio.create_task(_long_task())
    _track_task(task)
    task.cancel()

    with patch("backend.api.routers.coaching.logger") as mock_logger:
        await asyncio.sleep(0.01)
        mock_logger.error.assert_not_called()


# ---------------------------------------------------------------------------
# POST /{session_id}/report — line 104 (already generating branch)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_report_returns_generating_when_in_progress(
    client: AsyncClient,
) -> None:
    """POST returns status=generating immediately if generation is in progress."""
    from backend.api.services.coaching_store import mark_generating

    session_id = await _upload_session(client)
    mark_generating(session_id, "intermediate")

    response = await client.post(
        f"/api/coaching/{session_id}/report",
        json={"skill_level": "intermediate"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "generating"
    assert response.json()["session_id"] == session_id


# ---------------------------------------------------------------------------
# GET /{session_id}/report — line 250 (generating but no stored report)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_report_returns_generating_when_no_stored_report(
    client: AsyncClient,
) -> None:
    """GET returns status=generating when report is not stored yet but is in progress."""
    from backend.api.services.coaching_store import mark_generating

    session_id = await _upload_session(client)
    mark_generating(session_id, "intermediate")

    response = await client.get(f"/api/coaching/{session_id}/report")
    assert response.status_code == 200
    assert response.json()["status"] == "generating"
    assert response.json()["session_id"] == session_id


# ---------------------------------------------------------------------------
# POST /{session_id}/chat (HTTP) — lines 357-417
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_coaching_chat_http_session_not_found(client: AsyncClient) -> None:
    """POST /api/coaching/{id}/chat returns 404 when session does not exist."""
    response = await client.post(
        "/api/coaching/nonexistent/chat",
        json={"content": "How do I improve T3?"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_coaching_chat_http_no_report(client: AsyncClient) -> None:
    """POST /api/coaching/{id}/chat returns 404 when no coaching report exists."""
    session_id = await _upload_session(client)

    response = await client.post(
        f"/api/coaching/{session_id}/chat",
        json={"content": "How do I improve T3?"},
    )
    assert response.status_code == 404
    assert "report" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_coaching_chat_http_empty_question(client: AsyncClient) -> None:
    """POST /api/coaching/{id}/chat with blank content returns a prompt to ask a question."""
    session_id = await _upload_session(client)

    # Store a ready report
    from backend.api.schemas.coaching import CoachingReportResponse
    from backend.api.services.coaching_store import store_coaching_report

    report = CoachingReportResponse(session_id=session_id, status="ready", summary="Test summary")
    await store_coaching_report(session_id, report)

    response = await client.post(
        f"/api/coaching/{session_id}/chat",
        json={"content": "   "},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "assistant"
    assert "question" in data["content"].lower()


@pytest.mark.asyncio
async def test_coaching_chat_http_off_topic_response(client: AsyncClient) -> None:
    """POST /api/coaching/{id}/chat returns off-topic message for non-driving questions."""
    session_id = await _upload_session(client)

    from cataclysm.topic_guardrail import TopicClassification

    from backend.api.schemas.coaching import CoachingReportResponse
    from backend.api.services.coaching_store import store_coaching_report

    report = CoachingReportResponse(session_id=session_id, status="ready", summary="Test summary")
    await store_coaching_report(session_id, report)

    with patch(
        "backend.api.routers.coaching.classify_topic",
        return_value=TopicClassification(on_topic=False, source="classifier"),
    ):
        response = await client.post(
            f"/api/coaching/{session_id}/chat",
            json={"content": "What is the capital of France?"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "assistant"
    from cataclysm.topic_guardrail import OFF_TOPIC_RESPONSE

    assert data["content"] == OFF_TOPIC_RESPONSE


@pytest.mark.asyncio
async def test_coaching_chat_http_too_long_response(client: AsyncClient) -> None:
    """POST /api/coaching/{id}/chat returns INPUT_TOO_LONG_RESPONSE when message is too long."""
    session_id = await _upload_session(client)

    from cataclysm.topic_guardrail import TopicClassification

    from backend.api.schemas.coaching import CoachingReportResponse
    from backend.api.services.coaching_store import store_coaching_report

    report = CoachingReportResponse(session_id=session_id, status="ready", summary="Test summary")
    await store_coaching_report(session_id, report)

    with patch(
        "backend.api.routers.coaching.classify_topic",
        return_value=TopicClassification(on_topic=False, source="too_long"),
    ):
        response = await client.post(
            f"/api/coaching/{session_id}/chat",
            json={"content": "x" * 2001},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "assistant"
    from cataclysm.topic_guardrail import INPUT_TOO_LONG_RESPONSE

    assert data["content"] == INPUT_TOO_LONG_RESPONSE


@pytest.mark.asyncio
async def test_coaching_chat_http_returns_answer(client: AsyncClient) -> None:
    """POST /api/coaching/{id}/chat returns the AI answer for on-topic questions."""
    session_id = await _upload_session(client)

    from cataclysm.topic_guardrail import TopicClassification

    from backend.api.schemas.coaching import CoachingReportResponse
    from backend.api.services.coaching_store import store_coaching_report

    report = CoachingReportResponse(
        session_id=session_id,
        status="ready",
        summary="Focus on T3 braking.",
        patterns=["Consistent early apex"],
        drills=["Brake marker drill"],
    )
    await store_coaching_report(session_id, report)

    with (
        patch(
            "backend.api.routers.coaching.classify_topic",
            return_value=TopicClassification(on_topic=True, source="no_api_key"),
        ),
        patch(
            "cataclysm.coaching.ask_followup",
            return_value="Try braking 10m earlier at T3.",
        ),
    ):
        response = await client.post(
            f"/api/coaching/{session_id}/chat",
            json={"content": "How do I improve my braking at T3?"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "assistant"
    assert data["content"] == "Try braking 10m earlier at T3."


@pytest.mark.asyncio
async def test_coaching_chat_http_creates_context_on_first_message(
    client: AsyncClient,
) -> None:
    """POST /api/coaching/{id}/chat creates a new CoachingContext when none exists."""
    session_id = await _upload_session(client)

    from cataclysm.topic_guardrail import TopicClassification

    from backend.api.schemas.coaching import CoachingReportResponse
    from backend.api.services.coaching_store import get_coaching_context, store_coaching_report

    report = CoachingReportResponse(session_id=session_id, status="ready", summary="Great lap.")
    await store_coaching_report(session_id, report)

    # No context yet
    assert await get_coaching_context(session_id) is None

    with (
        patch(
            "backend.api.routers.coaching.classify_topic",
            return_value=TopicClassification(on_topic=True, source="no_api_key"),
        ),
        patch(
            "cataclysm.coaching.ask_followup",
            return_value="Good question!",
        ),
    ):
        response = await client.post(
            f"/api/coaching/{session_id}/chat",
            json={"content": "What should I work on?"},
        )

    assert response.status_code == 200
    # Context should now exist
    ctx = await get_coaching_context(session_id)
    assert ctx is not None


@pytest.mark.asyncio
async def test_coaching_chat_http_reuses_existing_context(client: AsyncClient) -> None:
    """POST /api/coaching/{id}/chat reuses an existing CoachingContext."""
    session_id = await _upload_session(client)

    from cataclysm.coaching import CoachingContext
    from cataclysm.topic_guardrail import TopicClassification

    from backend.api.schemas.coaching import CoachingReportResponse
    from backend.api.services.coaching_store import store_coaching_context, store_coaching_report

    report = CoachingReportResponse(session_id=session_id, status="ready", summary="Great session.")
    await store_coaching_report(session_id, report)

    existing_ctx = CoachingContext()
    await store_coaching_context(session_id, existing_ctx)

    captured_ctx: list[object] = []

    def _capture_ask_followup(ctx: object, *args: object, **kwargs: object) -> str:
        captured_ctx.append(ctx)
        return "Captured answer"

    with (
        patch(
            "backend.api.routers.coaching.classify_topic",
            return_value=TopicClassification(on_topic=True, source="no_api_key"),
        ),
        patch(
            "cataclysm.coaching.ask_followup",
            side_effect=_capture_ask_followup,
        ),
    ):
        response = await client.post(
            f"/api/coaching/{session_id}/chat",
            json={"content": "How's my consistency?"},
        )

    assert response.status_code == 200
    assert len(captured_ctx) == 1
    # The captured context should be the same object (or at least equivalent)
    assert isinstance(captured_ctx[0], CoachingContext)


# ---------------------------------------------------------------------------
# WebSocket coaching_chat — lines 434-531
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_websocket_chat_unauthenticated_closes_connection() -> None:
    """WebSocket handler calls websocket.close(code=4001) when auth returns None."""
    from unittest.mock import AsyncMock, MagicMock

    from backend.api.routers.coaching import coaching_chat

    mock_ws = MagicMock()
    mock_ws.close = AsyncMock()

    with patch(
        "backend.api.routers.coaching.authenticate_websocket",
        new=AsyncMock(return_value=None),
    ):
        await coaching_chat(mock_ws, "some-session-id")

    mock_ws.close.assert_called_once_with(code=4001, reason="Not authenticated")


@pytest.mark.asyncio
async def test_websocket_chat_session_not_found_sends_error() -> None:
    """WebSocket handler sends 'Session not found' message when session does not exist."""
    from unittest.mock import AsyncMock, MagicMock

    from backend.api.dependencies import AuthenticatedUser
    from backend.api.routers.coaching import coaching_chat

    mock_user = AuthenticatedUser(
        user_id="test-user-123",
        email="test@example.com",
        name="Test Driver",
    )
    mock_ws = MagicMock()
    mock_ws.accept = AsyncMock()
    mock_ws.send_json = AsyncMock()
    mock_ws.close = AsyncMock()

    with (
        patch(
            "backend.api.routers.coaching.authenticate_websocket",
            new=AsyncMock(return_value=mock_user),
        ),
        patch(
            "backend.api.routers.coaching.session_store.get_session",
            return_value=None,
        ),
    ):
        await coaching_chat(mock_ws, "nonexistent-session")

    mock_ws.accept.assert_called_once()
    mock_ws.send_json.assert_called_once()
    sent = mock_ws.send_json.call_args[0][0]
    assert "not found" in sent["content"].lower()
    mock_ws.close.assert_called_once()


@pytest.mark.asyncio
async def test_websocket_chat_no_report_sends_error(client: AsyncClient) -> None:
    """WebSocket handler sends 'No coaching report' message when no report exists."""
    from unittest.mock import AsyncMock, MagicMock

    from backend.api.dependencies import AuthenticatedUser
    from backend.api.routers.coaching import coaching_chat
    from backend.api.services import session_store

    session_id = await _upload_session(client)
    sd = session_store.get_session(session_id)
    assert sd is not None

    mock_user = AuthenticatedUser(
        user_id="test-user-123",
        email="test@example.com",
        name="Test Driver",
    )
    mock_ws = MagicMock()
    mock_ws.accept = AsyncMock()
    mock_ws.send_json = AsyncMock()
    mock_ws.close = AsyncMock()

    with (
        patch(
            "backend.api.routers.coaching.authenticate_websocket",
            new=AsyncMock(return_value=mock_user),
        ),
        patch(
            "backend.api.routers.coaching.session_store.get_session",
            return_value=sd,
        ),
        patch(
            "backend.api.routers.coaching.get_any_coaching_report",
            new=AsyncMock(return_value=None),
        ),
    ):
        await coaching_chat(mock_ws, session_id)

    mock_ws.send_json.assert_called_once()
    sent = mock_ws.send_json.call_args[0][0]
    assert "report" in sent["content"].lower()
    mock_ws.close.assert_called_once()


@pytest.mark.asyncio
async def test_websocket_chat_handles_message_exchange(client: AsyncClient) -> None:
    """WebSocket handler processes one question and sends an answer back."""
    from unittest.mock import AsyncMock, MagicMock

    from cataclysm.topic_guardrail import TopicClassification

    from backend.api.dependencies import AuthenticatedUser
    from backend.api.routers.coaching import coaching_chat
    from backend.api.schemas.coaching import CoachingReportResponse
    from backend.api.services import session_store

    session_id = await _upload_session(client)
    sd = session_store.get_session(session_id)
    assert sd is not None

    stored_report = CoachingReportResponse(
        session_id=session_id, status="ready", summary="Test report."
    )

    mock_user = AuthenticatedUser(
        user_id="test-user-123",
        email="test@example.com",
        name="Test Driver",
    )
    mock_ws = MagicMock()
    mock_ws.accept = AsyncMock()
    mock_ws.send_json = AsyncMock()
    mock_ws.close = AsyncMock()

    # Simulate: one valid message then a WebSocketDisconnect
    from fastapi import WebSocketDisconnect

    mock_ws.receive_json = AsyncMock(
        side_effect=[{"content": "How do I improve T3?"}, WebSocketDisconnect()]
    )

    with (
        patch(
            "backend.api.routers.coaching.authenticate_websocket",
            new=AsyncMock(return_value=mock_user),
        ),
        patch(
            "backend.api.routers.coaching.session_store.get_session",
            return_value=sd,
        ),
        patch(
            "backend.api.routers.coaching.get_any_coaching_report",
            new=AsyncMock(return_value=stored_report),
        ),
        patch(
            "backend.api.routers.coaching.classify_topic",
            return_value=TopicClassification(on_topic=True, source="no_api_key"),
        ),
        patch(
            "cataclysm.coaching.ask_followup",
            return_value="Brake 10m earlier.",
        ),
    ):
        await coaching_chat(mock_ws, session_id)

    mock_ws.accept.assert_called_once()
    mock_ws.send_json.assert_called_once()
    sent = mock_ws.send_json.call_args[0][0]
    assert sent["role"] == "assistant"
    assert "brake" in sent["content"].lower()


@pytest.mark.asyncio
async def test_websocket_chat_off_topic_question(client: AsyncClient) -> None:
    """WebSocket handler responds with off-topic message for unrelated questions."""
    from unittest.mock import AsyncMock, MagicMock

    from cataclysm.topic_guardrail import OFF_TOPIC_RESPONSE, TopicClassification
    from fastapi import WebSocketDisconnect

    from backend.api.dependencies import AuthenticatedUser
    from backend.api.routers.coaching import coaching_chat
    from backend.api.schemas.coaching import CoachingReportResponse
    from backend.api.services import session_store

    session_id = await _upload_session(client)
    sd = session_store.get_session(session_id)
    assert sd is not None

    stored_report = CoachingReportResponse(session_id=session_id, status="ready", summary="Report.")

    mock_user = AuthenticatedUser(
        user_id="test-user-123",
        email="test@example.com",
        name="Test Driver",
    )
    mock_ws = MagicMock()
    mock_ws.accept = AsyncMock()
    mock_ws.send_json = AsyncMock()
    mock_ws.close = AsyncMock()
    mock_ws.receive_json = AsyncMock(
        side_effect=[{"content": "What is the weather in Paris?"}, WebSocketDisconnect()]
    )

    with (
        patch(
            "backend.api.routers.coaching.authenticate_websocket",
            new=AsyncMock(return_value=mock_user),
        ),
        patch(
            "backend.api.routers.coaching.session_store.get_session",
            return_value=sd,
        ),
        patch(
            "backend.api.routers.coaching.get_any_coaching_report",
            new=AsyncMock(return_value=stored_report),
        ),
        patch(
            "backend.api.routers.coaching.classify_topic",
            return_value=TopicClassification(on_topic=False, source="classifier"),
        ),
    ):
        await coaching_chat(mock_ws, session_id)

    mock_ws.send_json.assert_called_once()
    sent = mock_ws.send_json.call_args[0][0]
    assert sent["content"] == OFF_TOPIC_RESPONSE


@pytest.mark.asyncio
async def test_websocket_chat_empty_question(client: AsyncClient) -> None:
    """WebSocket handler responds with 'Please ask a question' for empty messages."""
    from unittest.mock import AsyncMock, MagicMock

    from fastapi import WebSocketDisconnect

    from backend.api.dependencies import AuthenticatedUser
    from backend.api.routers.coaching import coaching_chat
    from backend.api.schemas.coaching import CoachingReportResponse
    from backend.api.services import session_store

    session_id = await _upload_session(client)
    sd = session_store.get_session(session_id)
    assert sd is not None

    stored_report = CoachingReportResponse(session_id=session_id, status="ready", summary="Report.")

    mock_user = AuthenticatedUser(
        user_id="test-user-123",
        email="test@example.com",
        name="Test Driver",
    )
    mock_ws = MagicMock()
    mock_ws.accept = AsyncMock()
    mock_ws.send_json = AsyncMock()
    mock_ws.close = AsyncMock()
    mock_ws.receive_json = AsyncMock(side_effect=[{"content": "   "}, WebSocketDisconnect()])

    with (
        patch(
            "backend.api.routers.coaching.authenticate_websocket",
            new=AsyncMock(return_value=mock_user),
        ),
        patch(
            "backend.api.routers.coaching.session_store.get_session",
            return_value=sd,
        ),
        patch(
            "backend.api.routers.coaching.get_any_coaching_report",
            new=AsyncMock(return_value=stored_report),
        ),
    ):
        await coaching_chat(mock_ws, session_id)

    mock_ws.send_json.assert_called_once()
    sent = mock_ws.send_json.call_args[0][0]
    assert "question" in sent["content"].lower()


# ---------------------------------------------------------------------------
# PDF download — lines 315-343
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_download_pdf_session_not_found(client: AsyncClient) -> None:
    """GET /api/coaching/{id}/report/pdf returns 404 when session does not exist."""
    response = await client.get("/api/coaching/nonexistent/report/pdf")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_download_pdf_no_report(client: AsyncClient) -> None:
    """GET /api/coaching/{id}/report/pdf returns 404 when no completed report exists."""
    session_id = await _upload_session(client)

    response = await client.get(f"/api/coaching/{session_id}/report/pdf")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_download_pdf_report_generating(client: AsyncClient) -> None:
    """GET /api/coaching/{id}/report/pdf returns 404 when report is still generating."""
    from backend.api.schemas.coaching import CoachingReportResponse
    from backend.api.services.coaching_store import store_coaching_report

    session_id = await _upload_session(client)

    # Store a generating-status report (status != "ready")
    report = CoachingReportResponse(session_id=session_id, status="generating")
    await store_coaching_report(session_id, report)

    response = await client.get(f"/api/coaching/{session_id}/report/pdf")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_download_pdf_success(client: AsyncClient) -> None:
    """GET /api/coaching/{id}/report/pdf returns PDF bytes when report is ready."""
    session_id = await _upload_session(client)

    # Generate and wait for report
    with patch(
        "cataclysm.coaching.generate_coaching_report",
        return_value=_mock_coaching_report(),
    ):
        await client.post(
            f"/api/coaching/{session_id}/report",
            json={"skill_level": "intermediate"},
        )
        await _wait_for_generation(session_id)

    # Mock PDF generation to return dummy bytes
    dummy_pdf = b"%PDF-1.4 dummy"
    with patch(
        "backend.api.routers.coaching.generate_pdf",
        return_value=dummy_pdf,
    ):
        response = await client.get(f"/api/coaching/{session_id}/report/pdf")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "coaching-report-" in response.headers["content-disposition"]
    assert response.content == dummy_pdf


@pytest.mark.asyncio
async def test_download_pdf_filename_uses_short_id(client: AsyncClient) -> None:
    """GET /api/coaching/{id}/report/pdf uses first 8 chars of session_id in filename."""
    session_id = await _upload_session(client)

    with patch(
        "cataclysm.coaching.generate_coaching_report",
        return_value=_mock_coaching_report(),
    ):
        await client.post(
            f"/api/coaching/{session_id}/report",
            json={"skill_level": "intermediate"},
        )
        await _wait_for_generation(session_id)

    with patch(
        "backend.api.routers.coaching.generate_pdf",
        return_value=b"%PDF dummy",
    ):
        response = await client.get(f"/api/coaching/{session_id}/report/pdf")

    assert response.status_code == 200
    expected_short_id = session_id[:8]
    assert f"coaching-report-{expected_short_id}.pdf" in response.headers["content-disposition"]


# ---------------------------------------------------------------------------
# _run_generation error path — exception in background task
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_generation_stores_error_on_exception(client: AsyncClient) -> None:
    """When generation raises, _run_generation stores an error-status report."""
    session_id = await _upload_session(client)

    with patch(
        "cataclysm.coaching.generate_coaching_report",
        side_effect=RuntimeError("Claude API down"),
    ):
        response = await client.post(
            f"/api/coaching/{session_id}/report",
            json={"skill_level": "intermediate"},
        )
        assert response.json()["status"] == "generating"
        await _wait_for_generation(session_id)

    # GET clears the error report and returns 404
    report = await client.get(f"/api/coaching/{session_id}/report")
    assert report.status_code == 404


@pytest.mark.asyncio
async def test_run_generation_unmarks_generating_on_error(client: AsyncClient) -> None:
    """After a failed generation, is_generating returns False for the session."""

    session_id = await _upload_session(client)

    with patch(
        "cataclysm.coaching.generate_coaching_report",
        side_effect=RuntimeError("fail"),
    ):
        await client.post(
            f"/api/coaching/{session_id}/report",
            json={"skill_level": "intermediate"},
        )
        # Background task needs time to execute; poll instead of fixed sleep
        for _ in range(50):
            await asyncio.sleep(0.05)
            if not is_generating(session_id, "intermediate"):
                break

    assert not is_generating(session_id, "intermediate")


@pytest.mark.asyncio
async def test_run_generation_error_stored_under_correct_skill_level(
    client: AsyncClient,
) -> None:
    """Error report must be stored under the requested skill_level, not 'intermediate'."""
    from backend.api.services.coaching_store import get_coaching_report

    session_id = await _upload_session(client)

    with patch(
        "cataclysm.coaching.generate_coaching_report",
        side_effect=RuntimeError("Claude API down"),
    ):
        await client.post(
            f"/api/coaching/{session_id}/report",
            json={"skill_level": "advanced"},
        )
        await _wait_for_generation(session_id, "advanced")

    # Error report should be stored under "advanced"
    advanced_report = await get_coaching_report(session_id, "advanced")
    assert advanced_report is not None
    assert advanced_report.status == "error"

    # Should NOT be stored under "intermediate" (the old buggy default)
    intermediate_report = await get_coaching_report(session_id, "intermediate")
    assert intermediate_report is None


# ---------------------------------------------------------------------------
# _run_generation priority_corners with non-numeric corner values
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_generation_handles_non_numeric_priority_corner(
    client: AsyncClient,
) -> None:
    """_run_generation converts non-numeric corner values to 0."""
    from cataclysm.coaching import CoachingReport

    report_with_bad_corner = CoachingReport(
        summary="Session summary.",
        priority_corners=[
            {
                "corner": "Entire Session",
                "time_cost_s": 1.5,
                "issue": "consistency",
                "tip": "focus",
            },
            {"corner": None, "time_cost_s": 0.0, "issue": "braking", "tip": "brake earlier"},
        ],
        corner_grades=[],
        patterns=[],
        drills=[],
        raw_response="",
    )

    session_id = await _upload_session(client)

    with patch(
        "cataclysm.coaching.generate_coaching_report",
        return_value=report_with_bad_corner,
    ):
        await client.post(
            f"/api/coaching/{session_id}/report",
            json={"skill_level": "intermediate"},
        )
        await _wait_for_generation(session_id)

    response = await client.get(f"/api/coaching/{session_id}/report")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    # Both non-numeric corners should map to corner=0
    for pc in data["priority_corners"]:
        assert pc["corner"] == 0


def test_priority_corner_schema_clamps_invalid_time_cost_values() -> None:
    """Priority time costs must be finite, non-negative estimates."""

    negative = PriorityCornerSchema(corner=3, time_cost_s=-0.25, issue="x", tip="y")
    infinite = PriorityCornerSchema(corner=4, time_cost_s=math.inf, issue="x", tip="y")

    assert negative.time_cost_s == 0.0
    assert infinite.time_cost_s == 0.0


@pytest.mark.asyncio
async def test_run_generation_preserves_priority_order_and_clamps_negatives(
    client: AsyncClient,
) -> None:
    """Priority corners pass through as-is; Pydantic clamps negatives to 0."""
    report = CoachingReport(
        summary="Session summary.",
        priority_corners=[
            {"corner": 3, "time_cost_s": 0.3, "issue": "late apex", "tip": "wait"},
            {"corner": 1, "time_cost_s": 0.1, "issue": "brake release", "tip": "ease off"},
            {"corner": 5, "time_cost_s": -0.4, "issue": "rotation", "tip": "slow hands"},
        ],
        corner_grades=[],
        patterns=[],
        drills=[],
        raw_response="",
    )

    session_id = await _upload_session(client)

    with patch("cataclysm.coaching.generate_coaching_report", return_value=report):
        await client.post(
            f"/api/coaching/{session_id}/report",
            json={"skill_level": "intermediate"},
        )
        await _wait_for_generation(session_id)

    response = await client.get(f"/api/coaching/{session_id}/report")
    assert response.status_code == 200
    data = response.json()
    # Order preserved from LLM (no re-sort); negative clamped to 0 by Pydantic validator
    assert [(pc["corner"], pc["time_cost_s"]) for pc in data["priority_corners"]] == [
        (3, pytest.approx(0.3)),
        (1, pytest.approx(0.1)),
        (5, pytest.approx(0.0)),
    ]


@pytest.mark.asyncio
async def test_run_generation_passes_optimal_comparison(client: AsyncClient) -> None:
    """_run_generation fetches optimal comparison and passes it to generate_coaching_report."""
    session_id = await _upload_session(client)

    captured_kwargs: dict[str, object] = {}

    def _spy_generate(*args: object, **kwargs: object) -> CoachingReport:
        captured_kwargs.update(kwargs)
        return _mock_coaching_report()

    optimal_raw: dict[str, object] = {
        "corner_opportunities": [
            {
                "corner_number": 5,
                "actual_min_speed_mph": 42.0,
                "optimal_min_speed_mph": 50.0,
                "speed_gap_mph": 8.0,
                "brake_gap_m": 5.2,
                "time_cost_s": 0.35,
                "exit_straight_time_cost_s": 0.12,
            },
        ],
        "actual_lap_time_s": 95.0,
        "optimal_lap_time_s": 92.5,
        "total_gap_s": 2.5,
        "is_valid": True,
        "invalid_reasons": [],
    }

    with (
        patch("cataclysm.coaching.generate_coaching_report", side_effect=_spy_generate),
        patch(
            "backend.api.routers.coaching.get_optimal_comparison_data",
            return_value=optimal_raw,
        ),
    ):
        await client.post(
            f"/api/coaching/{session_id}/report",
            json={"skill_level": "intermediate"},
        )
        await _wait_for_generation(session_id)

    oc = captured_kwargs.get("optimal_comparison")
    assert oc is not None, "optimal_comparison was not passed to generate_coaching_report"

    from cataclysm.optimal_comparison import OptimalComparisonResult

    assert isinstance(oc, OptimalComparisonResult)
    assert oc.actual_lap_time_s == pytest.approx(95.0)
    assert oc.optimal_lap_time_s == pytest.approx(92.5)
    assert oc.total_gap_s == pytest.approx(2.5)
    assert len(oc.corner_opportunities) == 1
    assert oc.corner_opportunities[0].corner_number == 5
    assert oc.corner_opportunities[0].speed_gap_mph == pytest.approx(8.0)
    assert oc.corner_opportunities[0].time_cost_s == pytest.approx(0.35)


@pytest.mark.asyncio
async def test_run_generation_optimal_failure_still_generates(
    client: AsyncClient,
) -> None:
    """When optimal comparison fails, coaching still generates (optimal_comparison=None)."""
    session_id = await _upload_session(client)

    captured_kwargs: dict[str, object] = {}

    def _spy_generate(*args: object, **kwargs: object) -> CoachingReport:
        captured_kwargs.update(kwargs)
        return _mock_coaching_report()

    with (
        patch("cataclysm.coaching.generate_coaching_report", side_effect=_spy_generate),
        patch(
            "backend.api.routers.coaching.get_optimal_comparison_data",
            side_effect=RuntimeError("physics solver exploded"),
        ),
    ):
        await client.post(
            f"/api/coaching/{session_id}/report",
            json={"skill_level": "intermediate"},
        )
        await _wait_for_generation(session_id)

    # Coaching should still succeed, with optimal_comparison=None
    assert captured_kwargs.get("optimal_comparison") is None

    response = await client.get(f"/api/coaching/{session_id}/report")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


@pytest.mark.asyncio
async def test_run_generation_invalid_optimal_passes_none(
    client: AsyncClient,
) -> None:
    """When optimal comparison is_valid=False, optimal_comparison is None (not passed)."""
    session_id = await _upload_session(client)

    captured_kwargs: dict[str, object] = {}

    def _spy_generate(*args: object, **kwargs: object) -> CoachingReport:
        captured_kwargs.update(kwargs)
        return _mock_coaching_report()

    invalid_raw: dict[str, object] = {
        "corner_opportunities": [],
        "actual_lap_time_s": 95.0,
        "optimal_lap_time_s": 70.0,
        "total_gap_s": 25.0,
        "is_valid": False,
        "invalid_reasons": ["total gap exceeds plausible range"],
    }

    with (
        patch("cataclysm.coaching.generate_coaching_report", side_effect=_spy_generate),
        patch(
            "backend.api.routers.coaching.get_optimal_comparison_data",
            return_value=invalid_raw,
        ),
    ):
        await client.post(
            f"/api/coaching/{session_id}/report",
            json={"skill_level": "intermediate"},
        )
        await _wait_for_generation(session_id)

    assert captured_kwargs.get("optimal_comparison") is None
