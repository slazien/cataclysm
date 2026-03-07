"""Extended tests for auto_flagging service — covers uncovered lines [124, 127, 137, 138].

Line 124: auto_flag_session — coaching report has praise-worthy corner grades
Line 127: auto_flag_session — coaching report has patterns with safety keywords → safety flag
Lines 137, 138: auto_flag_session — generates safety flag and breaks out of loop
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from backend.api.db.models import CoachingReport as CoachingReportModel
from backend.api.db.models import Session as SessionModel
from backend.tests.conftest import _TEST_USER, _test_session_factory


async def _seed_session(
    session_id: str,
    user_id: str = _TEST_USER.user_id,
    track_name: str = "Test Track",
    best_lap_time_s: float | None = 90.0,
    consistency_score: float | None = None,
) -> None:
    """Seed a session row into the test DB."""
    async with _test_session_factory() as db:
        db.add(
            SessionModel(
                session_id=session_id,
                user_id=user_id,
                track_name=track_name,
                session_date=datetime.now(UTC),
                file_key=session_id,
                n_laps=5,
                best_lap_time_s=best_lap_time_s,
                consistency_score=consistency_score,
            )
        )
        await db.commit()


async def _seed_coaching_report(
    session_id: str,
    report_json: dict,
) -> None:
    """Seed a CoachingReport row directly into the test DB."""
    async with _test_session_factory() as db:
        db.add(
            CoachingReportModel(
                session_id=session_id,
                skill_level="intermediate",
                report_json=report_json,
            )
        )
        await db.commit()


class TestAutoFlagSession:
    """Tests for auto_flagging.auto_flag_session."""

    @pytest.mark.asyncio
    async def test_returns_empty_when_session_not_found(self) -> None:
        """auto_flag_session returns [] when the session doesn't exist in DB."""
        from backend.api.services.auto_flagging import auto_flag_session

        async with _test_session_factory() as db:
            flags = await auto_flag_session(db, _TEST_USER.user_id, "nonexistent-session-abc")
        assert flags == []

    @pytest.mark.asyncio
    async def test_improvement_flag_for_first_session_pb(self) -> None:
        """auto_flag_session creates improvement flag for first session (new PB, line 90)."""
        from backend.api.services.auto_flagging import auto_flag_session

        session_id = "autoflag-improve-001"
        await _seed_session(session_id, best_lap_time_s=85.0)

        async with _test_session_factory() as db:
            flags = await auto_flag_session(db, _TEST_USER.user_id, session_id)

        assert "improvement" in flags

    @pytest.mark.asyncio
    async def test_attention_flag_for_low_consistency(self) -> None:
        """auto_flag_session creates attention flag for low consistency (line 58)."""
        from backend.api.services.auto_flagging import auto_flag_session

        session_id = "autoflag-attention-001"
        # consistency_score of 40 is below ATTENTION_CONSISTENCY_THRESHOLD (50)
        await _seed_session(session_id, best_lap_time_s=90.0, consistency_score=40.0)

        async with _test_session_factory() as db:
            flags = await auto_flag_session(db, _TEST_USER.user_id, session_id)

        assert "attention" in flags

    @pytest.mark.asyncio
    async def test_praise_flag_for_all_good_grades(self) -> None:
        """auto_flag_session creates praise flag when all corner grades pass (line 127)."""
        from backend.api.services.auto_flagging import auto_flag_session

        session_id = "autoflag-praise-001"
        await _seed_session(session_id, best_lap_time_s=90.0)
        # Seed a coaching report with all passing grades (A or B)
        await _seed_coaching_report(
            session_id,
            {
                "corner_grades": [
                    {
                        "corner": 1,
                        "braking": "A",
                        "trail_braking": "B",
                        "min_speed": "A",
                        "throttle": "A",
                        "notes": "",
                    },
                    {
                        "corner": 2,
                        "braking": "B",
                        "trail_braking": "A",
                        "min_speed": "B",
                        "throttle": "B",
                        "notes": "",
                    },
                ],
                "patterns": [],
            },
        )

        async with _test_session_factory() as db:
            flags = await auto_flag_session(db, _TEST_USER.user_id, session_id)

        assert "praise" in flags

    @pytest.mark.asyncio
    async def test_no_praise_flag_for_mixed_grades(self) -> None:
        """auto_flag_session does not create praise flag when some grades fail (line 124)."""
        from backend.api.services.auto_flagging import auto_flag_session

        session_id = "autoflag-nopraise-001"
        await _seed_session(session_id, best_lap_time_s=90.0)
        await _seed_coaching_report(
            session_id,
            {
                "corner_grades": [
                    {
                        "corner": 1,
                        "braking": "C",
                        "trail_braking": "D",
                        "min_speed": "C",
                        "throttle": "C",
                        "notes": "",
                    },
                ],
                "patterns": [],
            },
        )

        async with _test_session_factory() as db:
            flags = await auto_flag_session(db, _TEST_USER.user_id, session_id)

        assert "praise" not in flags

    @pytest.mark.asyncio
    async def test_safety_flag_for_spin_pattern(self) -> None:
        """auto_flag_session creates safety flag for 'spin' pattern (lines 137-138)."""
        from backend.api.services.auto_flagging import auto_flag_session

        session_id = "autoflag-safety-001"
        await _seed_session(session_id, best_lap_time_s=90.0)
        await _seed_coaching_report(
            session_id,
            {
                "corner_grades": [],
                "patterns": ["Driver had a spin at Turn 5 — overrotation on exit"],
            },
        )

        async with _test_session_factory() as db:
            flags = await auto_flag_session(db, _TEST_USER.user_id, session_id)

        assert "safety" in flags

    @pytest.mark.asyncio
    async def test_safety_flag_only_once_for_multiple_patterns(self) -> None:
        """auto_flag_session only adds one safety flag even with multiple triggering patterns."""
        from backend.api.services.auto_flagging import auto_flag_session

        session_id = "autoflag-once-001"
        await _seed_session(session_id, best_lap_time_s=90.0)
        await _seed_coaching_report(
            session_id,
            {
                "corner_grades": [],
                "patterns": ["spin at T1", "off-track at T3", "brake fade at T7"],
            },
        )

        async with _test_session_factory() as db:
            flags = await auto_flag_session(db, _TEST_USER.user_id, session_id)

        # Should break after first match — safety appears at most once
        assert flags.count("safety") <= 1

    @pytest.mark.asyncio
    async def test_no_safety_flag_for_benign_patterns(self) -> None:
        """auto_flag_session does not create safety flag for benign patterns."""
        from backend.api.services.auto_flagging import auto_flag_session

        session_id = "autoflag-benign-001"
        await _seed_session(session_id, best_lap_time_s=90.0)
        await _seed_coaching_report(
            session_id,
            {
                "corner_grades": [],
                "patterns": ["Good late apex entry", "Smooth throttle application"],
            },
        )

        async with _test_session_factory() as db:
            flags = await auto_flag_session(db, _TEST_USER.user_id, session_id)

        assert "safety" not in flags

    @pytest.mark.asyncio
    async def test_improvement_flag_with_delta_when_prev_pb_exists(self) -> None:
        """improvement flag description includes delta when beating an existing PB (lines 78-79)."""
        from sqlalchemy import select

        from backend.api.db.models import StudentFlag
        from backend.api.services.auto_flagging import auto_flag_session

        # Seed a previous session with a slower best lap (the old PB)
        prev_session_id = "autoflag-prevpb-001"
        new_session_id = "autoflag-newpb-001"
        await _seed_session(prev_session_id, best_lap_time_s=92.0)
        # New session beats the old PB
        await _seed_session(new_session_id, best_lap_time_s=89.5)

        async with _test_session_factory() as db:
            flags = await auto_flag_session(db, _TEST_USER.user_id, new_session_id)
            await db.commit()

        assert "improvement" in flags

        # Verify the flag description includes the delta (lines 78-79)
        async with _test_session_factory() as db:
            result = await db.execute(
                select(StudentFlag).where(
                    StudentFlag.session_id == new_session_id,
                    StudentFlag.flag_type == "improvement",
                )
            )
            flag = result.scalar_one_or_none()

        assert flag is not None
        # When prev_best is not None, description includes the delta in seconds
        assert "faster" in flag.description.lower() or "pb" in flag.description.lower()
