"""Comprehensive tests for coaching_store service.

Tests cover:
- store_coaching_report: memory insert, eviction trigger, DB upsert
- get_coaching_report: memory hit, lazy DB load, cache population, DB error
- get_any_coaching_report: most recently stored report for any skill level
- _evict_oldest_reports: FIFO eviction at MAX_COACHING_CACHE boundary
- store_coaching_context / get_coaching_context: parallel structure to reports
- clear_coaching_data: memory removal + async DB delete
- clear_coaching_report: single skill level removal
- mark_generating / unmark_generating / is_generating: race-condition flags
- clear_all_coaching: full memory wipe
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, _patch, patch

import pytest
from cataclysm.coaching import CoachingContext
from sqlalchemy.exc import SQLAlchemyError

import backend.api.services.coaching_store as coaching_store_mod
from backend.api.schemas.coaching import CoachingReportResponse, CornerGradeSchema
from backend.api.services.coaching_store import (
    MAX_COACHING_CACHE,
    _evict_oldest_reports,
    clear_all_coaching,
    clear_coaching_data,
    clear_coaching_report,
    get_any_coaching_report,
    get_coaching_context,
    get_coaching_report,
    is_generating,
    mark_generating,
    store_coaching_context,
    store_coaching_report,
    unmark_generating,
)

# ---------------------------------------------------------------------------
# Data builders
# ---------------------------------------------------------------------------


def _make_report(
    session_id: str = "sess-1",
    status: str = "ready",
    summary: str = "Great session",
) -> CoachingReportResponse:
    """Build a minimal CoachingReportResponse."""
    return CoachingReportResponse(
        session_id=session_id,
        status=status,
        summary=summary,
        priority_corners=[],
        corner_grades=[
            CornerGradeSchema(
                corner=1,
                braking="A",
                trail_braking="B",
                min_speed="B",
                throttle="A",
                notes="Solid corner.",
            )
        ],
        patterns=["Consistent braking"],
        drills=["Brake marker drill"],
    )


def _make_context(messages: list[dict[str, str]] | None = None) -> CoachingContext:
    """Build a CoachingContext with optional messages."""
    return CoachingContext(messages=messages or [{"role": "user", "content": "Hello"}])


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_stores() -> Iterator[None]:
    """Wipe all module-level caches before and after every test."""
    clear_all_coaching()
    yield
    clear_all_coaching()


# ---------------------------------------------------------------------------
# Context-manager helpers
# ---------------------------------------------------------------------------


@contextmanager
def _patch_all_db_helpers(
    upsert_report_side_effect: object = None,
    upsert_context_side_effect: object = None,
    delete_side_effect: object = None,
) -> Iterator[dict[str, AsyncMock]]:
    """Patch async_session_factory + all DB helpers.

    Returns the mock objects so callers can inspect call args.
    Applies side_effect to each helper when provided.
    """
    db_session = AsyncMock()
    db_session.commit = AsyncMock()

    # Build a proper async context manager using a real async function
    async def _aenter(_: object) -> AsyncMock:
        return db_session

    async def _aexit(_: object, *args: object) -> bool:
        return False

    cm = MagicMock()
    cm.__aenter__ = _aenter
    cm.__aexit__ = _aexit
    factory = MagicMock(return_value=cm)

    upsert_report_mock = AsyncMock(side_effect=upsert_report_side_effect)
    upsert_context_mock = AsyncMock(side_effect=upsert_context_side_effect)
    delete_mock = AsyncMock(side_effect=delete_side_effect)
    delete_skill_mock = AsyncMock(side_effect=delete_side_effect)
    get_report_mock = AsyncMock(return_value=None)
    get_any_report_mock = AsyncMock(return_value=None)
    get_context_mock = AsyncMock(return_value=None)

    with (
        patch("backend.api.services.coaching_store.async_session_factory", factory),
        patch("backend.api.services.coaching_store.upsert_coaching_report_db", upsert_report_mock),
        patch(
            "backend.api.services.coaching_store.upsert_coaching_context_db", upsert_context_mock
        ),
        patch("backend.api.services.coaching_store.delete_coaching_data_db", delete_mock),
        patch(
            "backend.api.services.coaching_store.delete_coaching_report_for_skill_db",
            delete_skill_mock,
        ),
        patch("backend.api.services.coaching_store.get_coaching_report_db", get_report_mock),
        patch(
            "backend.api.services.coaching_store.get_any_coaching_report_db", get_any_report_mock
        ),
        patch("backend.api.services.coaching_store.get_coaching_context_db", get_context_mock),
    ):
        yield {
            "upsert_report": upsert_report_mock,
            "upsert_context": upsert_context_mock,
            "delete": delete_mock,
            "delete_skill": delete_skill_mock,
            "get_report": get_report_mock,
            "get_any_report": get_any_report_mock,
            "get_context": get_context_mock,
        }


def _make_lazy_db_factory(
    report_return: CoachingReportResponse | None = None,
    any_report_return: CoachingReportResponse | None = None,
    context_return: list[dict[str, str]] | None = None,
    report_side_effect: object = None,
    any_report_side_effect: object = None,
    context_side_effect: object = None,
) -> tuple[_patch[MagicMock], _patch[AsyncMock], _patch[AsyncMock], _patch[AsyncMock]]:
    """Patch async_session_factory + DB getters for lazy-load tests."""
    db_session = AsyncMock()
    db_session.commit = AsyncMock()

    async def _aenter(_: object) -> AsyncMock:
        return db_session

    async def _aexit(_: object, *args: object) -> bool:
        return False

    cm = MagicMock()
    cm.__aenter__ = _aenter
    cm.__aexit__ = _aexit
    factory = MagicMock(return_value=cm)

    get_report_mock = AsyncMock(return_value=report_return, side_effect=report_side_effect)
    get_any_report_mock = AsyncMock(
        return_value=any_report_return, side_effect=any_report_side_effect
    )
    get_context_mock = AsyncMock(return_value=context_return, side_effect=context_side_effect)

    return (
        patch("backend.api.services.coaching_store.async_session_factory", factory),
        patch("backend.api.services.coaching_store.get_coaching_report_db", get_report_mock),
        patch(
            "backend.api.services.coaching_store.get_any_coaching_report_db", get_any_report_mock
        ),
        patch("backend.api.services.coaching_store.get_coaching_context_db", get_context_mock),
    )


# ---------------------------------------------------------------------------
# mark_generating / unmark_generating / is_generating
# ---------------------------------------------------------------------------


def test_mark_generating_sets_flag() -> None:
    """mark_generating adds the (session_id, skill_level) to the generating set."""
    mark_generating("session-abc", "intermediate")
    assert is_generating("session-abc", "intermediate")


def test_unmark_generating_removes_flag() -> None:
    """unmark_generating removes the generating flag for a session+skill_level."""
    mark_generating("session-abc", "intermediate")
    unmark_generating("session-abc", "intermediate")
    assert not is_generating("session-abc", "intermediate")


def test_unmark_generating_unknown_session_is_noop() -> None:
    """unmark_generating on an unknown session_id does not raise."""
    unmark_generating("never-marked", "intermediate")
    assert not is_generating("never-marked", "intermediate")


def test_is_generating_returns_false_for_unknown() -> None:
    """is_generating returns False for a session that was never marked."""
    assert not is_generating("ghost-session", "intermediate")


def test_mark_generating_idempotent() -> None:
    """Marking the same session twice does not duplicate entries."""
    mark_generating("dup", "intermediate")
    mark_generating("dup", "intermediate")
    assert is_generating("dup", "intermediate")
    unmark_generating("dup", "intermediate")
    assert not is_generating("dup", "intermediate")


def test_multiple_sessions_generating_independently() -> None:
    """Generating flags are tracked independently per session."""
    mark_generating("s1", "intermediate")
    mark_generating("s2", "intermediate")
    assert is_generating("s1", "intermediate")
    assert is_generating("s2", "intermediate")
    unmark_generating("s1", "intermediate")
    assert not is_generating("s1", "intermediate")
    assert is_generating("s2", "intermediate")


def test_generating_tracks_skill_level_independently() -> None:
    """Different skill levels for the same session are tracked independently."""
    mark_generating("s1", "beginner")
    mark_generating("s1", "advanced")
    assert is_generating("s1", "beginner")
    assert is_generating("s1", "advanced")
    assert not is_generating("s1", "intermediate")
    unmark_generating("s1", "beginner")
    assert not is_generating("s1", "beginner")
    assert is_generating("s1", "advanced")


def test_mark_generating_default_skill_level() -> None:
    """mark_generating defaults to 'intermediate' skill level."""
    mark_generating("s1")
    assert is_generating("s1")
    assert is_generating("s1", "intermediate")
    assert not is_generating("s1", "advanced")


# ---------------------------------------------------------------------------
# _evict_oldest_reports
# ---------------------------------------------------------------------------


def test_evict_oldest_reports_noop_when_under_limit() -> None:
    """No eviction when cache size is at or below MAX_COACHING_CACHE."""
    for i in range(5):
        coaching_store_mod._reports[f"s{i}"] = {"intermediate": _make_report(session_id=f"s{i}")}

    _evict_oldest_reports()

    assert len(coaching_store_mod._reports) == 5


def test_evict_oldest_reports_removes_oldest_entry() -> None:
    """When cache exceeds MAX_COACHING_CACHE, the oldest entry is removed first."""
    for i in range(MAX_COACHING_CACHE + 1):
        coaching_store_mod._reports[f"s{i}"] = {"intermediate": _make_report(session_id=f"s{i}")}

    _evict_oldest_reports()

    assert len(coaching_store_mod._reports) == MAX_COACHING_CACHE
    # s0 was inserted first — it must have been evicted
    assert "s0" not in coaching_store_mod._reports
    # Most recently inserted entry must still be present
    assert f"s{MAX_COACHING_CACHE}" in coaching_store_mod._reports


def test_evict_oldest_reports_also_evicts_context() -> None:
    """Eviction removes the paired context entry when it exists."""
    for i in range(MAX_COACHING_CACHE + 1):
        coaching_store_mod._reports[f"s{i}"] = {"intermediate": _make_report(session_id=f"s{i}")}
        coaching_store_mod._contexts[f"s{i}"] = _make_context()

    _evict_oldest_reports()

    assert "s0" not in coaching_store_mod._contexts


def test_evict_oldest_reports_multiple_overflow() -> None:
    """Eviction removes all overflowing entries in a single call."""
    for i in range(MAX_COACHING_CACHE + 10):
        coaching_store_mod._reports[f"s{i}"] = {"intermediate": _make_report(session_id=f"s{i}")}

    _evict_oldest_reports()

    assert len(coaching_store_mod._reports) == MAX_COACHING_CACHE


def test_evict_oldest_reports_context_not_required() -> None:
    """Eviction does not fail if the context for the evicted session does not exist."""
    for i in range(MAX_COACHING_CACHE + 1):
        coaching_store_mod._reports[f"s{i}"] = {"intermediate": _make_report(session_id=f"s{i}")}
    # No contexts added — eviction should not raise

    _evict_oldest_reports()

    assert len(coaching_store_mod._reports) == MAX_COACHING_CACHE


def test_evict_oldest_reports_noop_when_exactly_at_limit() -> None:
    """No eviction when cache is exactly at MAX_COACHING_CACHE."""
    for i in range(MAX_COACHING_CACHE):
        coaching_store_mod._reports[f"s{i}"] = {"intermediate": _make_report(session_id=f"s{i}")}

    _evict_oldest_reports()

    assert len(coaching_store_mod._reports) == MAX_COACHING_CACHE
    assert "s0" in coaching_store_mod._reports


# ---------------------------------------------------------------------------
# store_coaching_report
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_store_coaching_report_adds_to_memory() -> None:
    """store_coaching_report puts the report in the nested _reports dict."""
    report = _make_report("s1")
    with _patch_all_db_helpers():
        await store_coaching_report("s1", report)
    assert coaching_store_mod._reports["s1"]["intermediate"] is report


@pytest.mark.asyncio
async def test_store_coaching_report_calls_db_upsert() -> None:
    """store_coaching_report invokes upsert_coaching_report_db with correct args."""
    report = _make_report("s1")
    with _patch_all_db_helpers() as mocks:
        await store_coaching_report("s1", report, skill_level="advanced")
    mocks["upsert_report"].assert_awaited_once()
    args = mocks["upsert_report"].call_args
    assert args.args[1] == "s1"
    assert args.args[2] is report
    assert args.args[3] == "advanced"


@pytest.mark.asyncio
async def test_store_coaching_report_default_skill_level() -> None:
    """store_coaching_report uses 'intermediate' as default skill_level."""
    report = _make_report("s1")
    with _patch_all_db_helpers() as mocks:
        await store_coaching_report("s1", report)
    args = mocks["upsert_report"].call_args
    assert args.args[3] == "intermediate"


@pytest.mark.asyncio
async def test_store_coaching_report_db_error_does_not_raise() -> None:
    """A SQLAlchemyError during DB persist is logged but does not propagate."""
    report = _make_report("s1")
    with _patch_all_db_helpers(upsert_report_side_effect=SQLAlchemyError("connection refused")):
        await store_coaching_report("s1", report)
    # Report is still in memory despite DB failure
    assert coaching_store_mod._reports["s1"]["intermediate"] is report


@pytest.mark.asyncio
async def test_store_coaching_report_triggers_eviction() -> None:
    """Storing one extra report when cache is full evicts the oldest entry."""
    for i in range(MAX_COACHING_CACHE):
        coaching_store_mod._reports[f"s{i}"] = {"intermediate": _make_report(session_id=f"s{i}")}

    new_report = _make_report("new-session")
    with _patch_all_db_helpers():
        await store_coaching_report("new-session", new_report)

    assert len(coaching_store_mod._reports) == MAX_COACHING_CACHE
    assert "new-session" in coaching_store_mod._reports
    assert "s0" not in coaching_store_mod._reports


@pytest.mark.asyncio
async def test_store_multiple_skill_levels() -> None:
    """Storing reports for different skill levels in the same session keeps both."""
    report_int = _make_report("s1", summary="Intermediate report")
    report_adv = _make_report("s1", summary="Advanced report")
    with _patch_all_db_helpers():
        await store_coaching_report("s1", report_int, "intermediate")
        await store_coaching_report("s1", report_adv, "advanced")
    assert coaching_store_mod._reports["s1"]["intermediate"].summary == "Intermediate report"
    assert coaching_store_mod._reports["s1"]["advanced"].summary == "Advanced report"


# ---------------------------------------------------------------------------
# get_coaching_report
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_coaching_report_returns_memory_hit() -> None:
    """get_coaching_report returns the in-memory report without touching the DB."""
    report = _make_report("s1")
    coaching_store_mod._reports["s1"] = {"intermediate": report}

    with patch(
        "backend.api.services.coaching_store.async_session_factory",
        side_effect=AssertionError("DB should not be called"),
    ):
        result = await get_coaching_report("s1", "intermediate")

    assert result is report


@pytest.mark.asyncio
async def test_get_coaching_report_lazy_loads_from_db() -> None:
    """Cache miss triggers DB load and populates in-memory cache."""
    db_report = _make_report("s1", status="ready")
    factory_patch, report_db_patch, _, _ = _make_lazy_db_factory(report_return=db_report)

    with factory_patch, report_db_patch:
        result = await get_coaching_report("s1", "intermediate")

    assert result is db_report
    assert coaching_store_mod._reports["s1"]["intermediate"] is db_report


@pytest.mark.asyncio
async def test_get_coaching_report_db_miss_returns_none() -> None:
    """Cache + DB miss returns None."""
    factory_patch, report_db_patch, _, _ = _make_lazy_db_factory(report_return=None)

    with factory_patch, report_db_patch:
        result = await get_coaching_report("missing", "intermediate")

    assert result is None
    assert "missing" not in coaching_store_mod._reports


@pytest.mark.asyncio
async def test_get_coaching_report_db_non_ready_report_not_cached() -> None:
    """A DB report with status != 'ready' is not stored in the memory cache."""
    db_report = _make_report("s1", status="error")
    factory_patch, report_db_patch, _, _ = _make_lazy_db_factory(report_return=db_report)

    with factory_patch, report_db_patch:
        result = await get_coaching_report("s1", "intermediate")

    assert result is None
    assert "s1" not in coaching_store_mod._reports


@pytest.mark.asyncio
async def test_get_coaching_report_db_error_returns_none() -> None:
    """SQLAlchemyError during DB lazy load is caught, returns None."""
    factory_patch, report_db_patch, _, _ = _make_lazy_db_factory(
        report_side_effect=SQLAlchemyError("timeout")
    )

    with factory_patch, report_db_patch:
        result = await get_coaching_report("s1", "intermediate")

    assert result is None


@pytest.mark.asyncio
async def test_get_coaching_report_different_skill_level_misses() -> None:
    """Requesting a different skill level than what's stored misses the cache."""
    report = _make_report("s1")
    coaching_store_mod._reports["s1"] = {"intermediate": report}

    factory_patch, report_db_patch, _, _ = _make_lazy_db_factory(report_return=None)
    with factory_patch, report_db_patch:
        result = await get_coaching_report("s1", "advanced")

    assert result is None


# ---------------------------------------------------------------------------
# get_any_coaching_report
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_any_coaching_report_returns_most_recent() -> None:
    """get_any_coaching_report returns the most recently stored report."""
    report_int = _make_report("s1", summary="Intermediate")
    report_adv = _make_report("s1", summary="Advanced")
    coaching_store_mod._reports["s1"] = {"intermediate": report_int, "advanced": report_adv}

    with patch(
        "backend.api.services.coaching_store.async_session_factory",
        side_effect=AssertionError("DB should not be called"),
    ):
        result = await get_any_coaching_report("s1")

    # Most recently added (last in dict) is "advanced"
    assert result is report_adv


@pytest.mark.asyncio
async def test_get_any_coaching_report_db_fallback() -> None:
    """get_any_coaching_report falls back to DB when no memory cache exists."""
    db_report = _make_report("s1", status="ready")
    db_report.skill_level = "advanced"
    factory_patch, _, any_report_db_patch, _ = _make_lazy_db_factory(any_report_return=db_report)

    with factory_patch, any_report_db_patch:
        result = await get_any_coaching_report("s1")

    assert result is db_report
    assert coaching_store_mod._reports["s1"]["advanced"] is db_report


@pytest.mark.asyncio
async def test_get_any_coaching_report_returns_none_when_empty() -> None:
    """get_any_coaching_report returns None when no reports exist."""
    factory_patch, _, any_report_db_patch, _ = _make_lazy_db_factory(any_report_return=None)

    with factory_patch, any_report_db_patch:
        result = await get_any_coaching_report("missing")

    assert result is None


# ---------------------------------------------------------------------------
# store_coaching_context / get_coaching_context
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_store_coaching_context_adds_to_memory() -> None:
    """store_coaching_context puts the context in the _contexts dict."""
    ctx = _make_context()
    with _patch_all_db_helpers():
        await store_coaching_context("s1", ctx)
    assert coaching_store_mod._contexts["s1"] is ctx


@pytest.mark.asyncio
async def test_store_coaching_context_calls_db_upsert() -> None:
    """store_coaching_context invokes upsert_coaching_context_db with messages."""
    ctx = _make_context([{"role": "user", "content": "Q1"}, {"role": "assistant", "content": "A1"}])
    with _patch_all_db_helpers() as mocks:
        await store_coaching_context("s1", ctx)
    mocks["upsert_context"].assert_awaited_once()
    args = mocks["upsert_context"].call_args
    assert args.args[1] == "s1"
    assert args.args[2] == ctx.messages


@pytest.mark.asyncio
async def test_store_coaching_context_db_error_does_not_raise() -> None:
    """A SQLAlchemyError during context persist is swallowed."""
    ctx = _make_context()
    with _patch_all_db_helpers(upsert_context_side_effect=SQLAlchemyError("write failed")):
        await store_coaching_context("s1", ctx)
    assert coaching_store_mod._contexts["s1"] is ctx


@pytest.mark.asyncio
async def test_get_coaching_context_returns_memory_hit() -> None:
    """get_coaching_context returns the in-memory context without touching the DB."""
    ctx = _make_context()
    coaching_store_mod._contexts["s1"] = ctx

    with patch(
        "backend.api.services.coaching_store.async_session_factory",
        side_effect=AssertionError("DB should not be called"),
    ):
        result = await get_coaching_context("s1")

    assert result is ctx


@pytest.mark.asyncio
async def test_get_coaching_context_lazy_loads_from_db() -> None:
    """Cache miss triggers DB load and populates in-memory context cache."""
    messages = [{"role": "user", "content": "test question"}]
    factory_patch, _, _, context_db_patch = _make_lazy_db_factory(context_return=messages)

    with factory_patch, context_db_patch:
        result = await get_coaching_context("s1")

    assert result is not None
    assert isinstance(result, CoachingContext)
    assert result.messages == messages
    assert coaching_store_mod._contexts["s1"].messages == messages


@pytest.mark.asyncio
async def test_get_coaching_context_db_miss_returns_none() -> None:
    """Cache + DB miss returns None for context."""
    factory_patch, _, _, context_db_patch = _make_lazy_db_factory(context_return=None)

    with factory_patch, context_db_patch:
        result = await get_coaching_context("missing")

    assert result is None
    assert "missing" not in coaching_store_mod._contexts


@pytest.mark.asyncio
async def test_get_coaching_context_db_error_returns_none() -> None:
    """SQLAlchemyError during context DB load is caught, returns None."""
    factory_patch, _, _, context_db_patch = _make_lazy_db_factory(
        context_side_effect=SQLAlchemyError("db unavailable")
    )

    with factory_patch, context_db_patch:
        result = await get_coaching_context("s1")

    assert result is None


# ---------------------------------------------------------------------------
# clear_coaching_data
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_clear_coaching_data_removes_from_memory() -> None:
    """clear_coaching_data deletes both report and context from memory."""
    coaching_store_mod._reports["s1"] = {"intermediate": _make_report("s1")}
    coaching_store_mod._contexts["s1"] = _make_context()
    with _patch_all_db_helpers():
        await clear_coaching_data("s1")
    assert "s1" not in coaching_store_mod._reports
    assert "s1" not in coaching_store_mod._contexts


@pytest.mark.asyncio
async def test_clear_coaching_data_calls_db_delete() -> None:
    """clear_coaching_data calls delete_coaching_data_db with the correct session_id."""
    coaching_store_mod._reports["s1"] = {"intermediate": _make_report("s1")}
    with _patch_all_db_helpers() as mocks:
        await clear_coaching_data("s1")
    mocks["delete"].assert_awaited_once()
    args = mocks["delete"].call_args
    assert args.args[1] == "s1"


@pytest.mark.asyncio
async def test_clear_coaching_data_unknown_session_is_noop() -> None:
    """clear_coaching_data for an unknown session_id does not raise."""
    with _patch_all_db_helpers():
        await clear_coaching_data("ghost")
    assert "ghost" not in coaching_store_mod._reports
    assert "ghost" not in coaching_store_mod._contexts


@pytest.mark.asyncio
async def test_clear_coaching_data_db_error_does_not_raise() -> None:
    """A SQLAlchemyError during DB delete is swallowed; memory is still cleared."""
    coaching_store_mod._reports["s1"] = {"intermediate": _make_report("s1")}
    coaching_store_mod._contexts["s1"] = _make_context()
    with _patch_all_db_helpers(delete_side_effect=SQLAlchemyError("delete failed")):
        await clear_coaching_data("s1")
    assert "s1" not in coaching_store_mod._reports
    assert "s1" not in coaching_store_mod._contexts


@pytest.mark.asyncio
async def test_clear_coaching_data_only_affects_target_session() -> None:
    """clear_coaching_data removes exactly the target session, not others."""
    coaching_store_mod._reports["s1"] = {"intermediate": _make_report("s1")}
    coaching_store_mod._reports["s2"] = {"intermediate": _make_report("s2")}
    coaching_store_mod._contexts["s1"] = _make_context()
    coaching_store_mod._contexts["s2"] = _make_context()
    with _patch_all_db_helpers():
        await clear_coaching_data("s1")
    assert "s1" not in coaching_store_mod._reports
    assert "s2" in coaching_store_mod._reports
    assert "s1" not in coaching_store_mod._contexts
    assert "s2" in coaching_store_mod._contexts


# ---------------------------------------------------------------------------
# clear_coaching_report (single skill level)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_clear_coaching_report_removes_single_skill() -> None:
    """clear_coaching_report removes only the specified skill level."""
    coaching_store_mod._reports["s1"] = {
        "intermediate": _make_report("s1", summary="Int"),
        "advanced": _make_report("s1", summary="Adv"),
    }
    with _patch_all_db_helpers() as mocks:
        await clear_coaching_report("s1", "intermediate")
    # Only intermediate removed; advanced stays
    assert "intermediate" not in coaching_store_mod._reports["s1"]
    assert "advanced" in coaching_store_mod._reports["s1"]
    mocks["delete_skill"].assert_awaited_once()


@pytest.mark.asyncio
async def test_clear_coaching_report_removes_session_when_last() -> None:
    """clear_coaching_report removes the session key when last skill level is removed."""
    coaching_store_mod._reports["s1"] = {"intermediate": _make_report("s1")}
    with _patch_all_db_helpers():
        await clear_coaching_report("s1", "intermediate")
    assert "s1" not in coaching_store_mod._reports


@pytest.mark.asyncio
async def test_clear_coaching_report_noop_for_missing() -> None:
    """clear_coaching_report does not raise for a nonexistent session/skill."""
    with _patch_all_db_helpers():
        await clear_coaching_report("ghost", "advanced")
    assert "ghost" not in coaching_store_mod._reports


# ---------------------------------------------------------------------------
# clear_all_coaching
# ---------------------------------------------------------------------------


def test_clear_all_coaching_empties_all_caches() -> None:
    """clear_all_coaching wipes reports, contexts, and generating flags."""
    coaching_store_mod._reports["s1"] = {"intermediate": _make_report("s1")}
    coaching_store_mod._contexts["s1"] = _make_context()
    coaching_store_mod._generating.add(("s1", "intermediate"))

    clear_all_coaching()

    assert len(coaching_store_mod._reports) == 0
    assert len(coaching_store_mod._contexts) == 0
    assert len(coaching_store_mod._generating) == 0


def test_clear_all_coaching_is_idempotent() -> None:
    """clear_all_coaching on an already-empty store does not raise."""
    clear_all_coaching()
    clear_all_coaching()
    assert len(coaching_store_mod._reports) == 0


# ---------------------------------------------------------------------------
# Integration: store then retrieve
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_store_then_get_coaching_report_roundtrip() -> None:
    """A stored report is returned by get_coaching_report without hitting DB."""
    report = _make_report("roundtrip-1")
    with _patch_all_db_helpers():
        await store_coaching_report("roundtrip-1", report)

    with patch(
        "backend.api.services.coaching_store.async_session_factory",
        side_effect=AssertionError("DB should not be called on memory hit"),
    ):
        result = await get_coaching_report("roundtrip-1", "intermediate")

    assert result is report


@pytest.mark.asyncio
async def test_store_then_get_coaching_context_roundtrip() -> None:
    """A stored context is returned by get_coaching_context without hitting DB."""
    ctx = _make_context([{"role": "user", "content": "How to brake later?"}])
    with _patch_all_db_helpers():
        await store_coaching_context("roundtrip-ctx", ctx)

    with patch(
        "backend.api.services.coaching_store.async_session_factory",
        side_effect=AssertionError("DB should not be called on memory hit"),
    ):
        result = await get_coaching_context("roundtrip-ctx")

    assert result is ctx


@pytest.mark.asyncio
async def test_report_overwrite_replaces_previous() -> None:
    """Storing a new report for the same session_id+skill replaces the old one."""
    report_v1 = _make_report("s1", summary="First version")
    report_v2 = _make_report("s1", summary="Second version")
    with _patch_all_db_helpers():
        await store_coaching_report("s1", report_v1)
        await store_coaching_report("s1", report_v2)
    assert coaching_store_mod._reports["s1"]["intermediate"].summary == "Second version"


@pytest.mark.asyncio
async def test_generating_flag_cleared_after_report_stored() -> None:
    """Typical generation flow: mark -> store -> unmark leaves no generating flag."""
    mark_generating("s1", "intermediate")
    assert is_generating("s1", "intermediate")

    report = _make_report("s1")
    with _patch_all_db_helpers():
        await store_coaching_report("s1", report)

    unmark_generating("s1", "intermediate")
    assert not is_generating("s1", "intermediate")
    assert coaching_store_mod._reports["s1"]["intermediate"] is report


@pytest.mark.asyncio
async def test_context_evicted_with_report() -> None:
    """When a report is evicted from cache, its paired context is also removed."""
    for i in range(MAX_COACHING_CACHE):
        coaching_store_mod._reports[f"s{i}"] = {"intermediate": _make_report(session_id=f"s{i}")}
        coaching_store_mod._contexts[f"s{i}"] = _make_context()

    # Adding one more report triggers eviction of s0
    new_report = _make_report("overflow-session")
    with _patch_all_db_helpers():
        await store_coaching_report("overflow-session", new_report)

    assert "s0" not in coaching_store_mod._reports
    assert "s0" not in coaching_store_mod._contexts
    assert "overflow-session" in coaching_store_mod._reports
