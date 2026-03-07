"""Tests for achievement_engine service — covers lines 236-423.

Tests cover:
  - seed_achievements: inserts new definitions, syncs updated mutable fields, skips if _seeded
  - check_achievements: session_count, score_threshold, track_count, total_laps criteria
  - _check_criteria: all_grades_a, all_grades_b_plus, all_trail_grades_a, unknown type
  - _check_all_grades: no session_id, no report, no corner_grades, all passing, some failing
  - get_user_achievements: returns all definitions with unlocked status
  - get_recent_achievements: returns new achievements and marks them seen
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from backend.api.db.models import (
    AchievementDefinition,
)
from backend.api.db.models import (
    CoachingReport as CoachingReportModel,
)
from backend.api.db.models import (
    Session as SessionModel,
)
from backend.tests.conftest import _TEST_USER, _test_session_factory

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _seed_session(
    session_id: str,
    track_name: str = "barber",
    n_laps: int = 5,
    consistency_score: float | None = None,
    user_id: str = _TEST_USER.user_id,
) -> None:
    """Seed a Session row directly."""
    async with _test_session_factory() as db:
        existing = await db.get(SessionModel, session_id)
        if existing is None:
            db.add(
                SessionModel(
                    session_id=session_id,
                    user_id=user_id,
                    track_name=track_name,
                    session_date=datetime.now(UTC),
                    file_key=session_id,
                    n_laps=n_laps,
                    consistency_score=consistency_score,
                )
            )
            await db.commit()


async def _seed_coaching_report(session_id: str, corner_grades: list[dict]) -> None:
    """Seed a CoachingReport row directly."""
    async with _test_session_factory() as db:
        db.add(
            CoachingReportModel(
                session_id=session_id,
                skill_level="intermediate",
                report_json={"corner_grades": corner_grades},
            )
        )
        await db.commit()


def _reset_seeded() -> None:
    """Reset the _seeded global in achievement_engine to allow re-seeding."""
    import backend.api.services.achievement_engine as ae_module

    ae_module._seeded = False


# ---------------------------------------------------------------------------
# Tests for seed_achievements
# ---------------------------------------------------------------------------


class TestSeedAchievements:
    """Tests for seed_achievements function."""

    @pytest.mark.asyncio
    async def test_seed_achievements_inserts_definitions(self) -> None:
        """seed_achievements inserts achievement definitions into DB (line 233)."""
        _reset_seeded()
        from sqlalchemy import select

        from backend.api.services.achievement_engine import seed_achievements

        async with _test_session_factory() as db:
            await seed_achievements(db)
            result = await db.execute(select(AchievementDefinition))
            definitions = list(result.scalars().all())

        assert len(definitions) > 0
        ids = {d.id for d in definitions}
        assert "first_session" in ids
        assert "brake_master" in ids

    @pytest.mark.asyncio
    async def test_seed_achievements_skips_if_already_seeded(self) -> None:
        """seed_achievements is a no-op if _seeded is True (line 223)."""
        import backend.api.services.achievement_engine as ae_module
        from backend.api.services.achievement_engine import seed_achievements

        # First call: seed
        _reset_seeded()
        async with _test_session_factory() as db:
            await seed_achievements(db)
        assert ae_module._seeded is True

        # Second call: should skip DB operations
        async with _test_session_factory() as db:
            await seed_achievements(db)  # Should return immediately without DB writes

    @pytest.mark.asyncio
    async def test_seed_achievements_syncs_mutable_fields(self) -> None:
        """seed_achievements updates category/name on existing definitions (lines 236-238)."""
        _reset_seeded()
        from backend.api.services.achievement_engine import seed_achievements

        # First seed to populate the DB — must commit after flush so data is visible
        async with _test_session_factory() as db:
            await seed_achievements(db)
            await db.commit()

        # Manually mutate an existing definition in DB
        async with _test_session_factory() as db:
            existing = await db.get(AchievementDefinition, "first_session")
            assert existing is not None
            existing.name = "Old Name"
            await db.commit()

        # Re-seed should restore the correct name (sync mutable fields branch lines 236-238)
        _reset_seeded()
        async with _test_session_factory() as db:
            await seed_achievements(db)
            await db.commit()

        async with _test_session_factory() as db:
            restored = await db.get(AchievementDefinition, "first_session")
            assert restored is not None
            assert restored.name == "First Laps"  # The seed value should be restored


# ---------------------------------------------------------------------------
# Tests for check_achievements
# ---------------------------------------------------------------------------


class TestCheckAchievements:
    """Tests for check_achievements with different criteria types."""

    @pytest.mark.asyncio
    async def test_session_count_criteria_unlocks_first_session(self) -> None:
        """session_count criterion unlocks 'first_session' after 1 upload (lines 292-296)."""
        _reset_seeded()
        from backend.api.services.achievement_engine import check_achievements

        session_id = "ach-sess-count-001"
        await _seed_session(session_id)

        async with _test_session_factory() as db:
            unlocked = await check_achievements(db, _TEST_USER.user_id, session_id=session_id)
            await db.commit()

        assert "first_session" in unlocked

    @pytest.mark.asyncio
    async def test_score_threshold_criteria_unlocks_consistent_driver(self) -> None:
        """score_threshold criterion unlocks when consistency_score >= 70 (lines 299-303)."""
        _reset_seeded()
        from backend.api.services.achievement_engine import check_achievements

        session_id = "ach-score-001"
        await _seed_session(session_id, consistency_score=75.0)

        async with _test_session_factory() as db:
            unlocked = await check_achievements(db, _TEST_USER.user_id, session_id=session_id)
            await db.commit()

        assert "consistent_driver" in unlocked

    @pytest.mark.asyncio
    async def test_score_threshold_does_not_unlock_when_below(self) -> None:
        """score_threshold criterion does not unlock when score is too low."""
        _reset_seeded()
        from backend.api.services.achievement_engine import check_achievements

        session_id = "ach-score-low-001"
        await _seed_session(session_id, consistency_score=50.0)

        async with _test_session_factory() as db:
            unlocked = await check_achievements(db, _TEST_USER.user_id, session_id=session_id)
            await db.commit()

        assert "consistent_driver" not in unlocked
        assert "consistency_king" not in unlocked

    @pytest.mark.asyncio
    async def test_track_count_criteria_unlocks_track_explorer(self) -> None:
        """track_count criterion unlocks 'multi_track' after 3 distinct tracks (lines 306-310)."""
        _reset_seeded()
        from backend.api.services.achievement_engine import check_achievements

        # Seed 3 sessions on 3 different tracks
        for i, track in enumerate(["barber", "roebling", "vir"]):
            await _seed_session(f"ach-track-{i}", track_name=track)

        async with _test_session_factory() as db:
            unlocked = await check_achievements(db, _TEST_USER.user_id, session_id="ach-track-0")
            await db.commit()

        assert "multi_track" in unlocked

    @pytest.mark.asyncio
    async def test_total_laps_criteria_unlocks_century(self) -> None:
        """total_laps criterion unlocks when total laps >= 100 (lines 313-317)."""
        _reset_seeded()
        from backend.api.services.achievement_engine import check_achievements

        # Seed a session with 100 laps
        session_id = "ach-laps-100"
        await _seed_session(session_id, n_laps=100)

        async with _test_session_factory() as db:
            unlocked = await check_achievements(db, _TEST_USER.user_id, session_id=session_id)
            await db.commit()

        assert "century_laps" in unlocked

    @pytest.mark.asyncio
    async def test_already_unlocked_achievements_not_duplicated(self) -> None:
        """check_achievements skips already-unlocked achievements (lines 260-261)."""
        _reset_seeded()
        from backend.api.services.achievement_engine import check_achievements

        session_id = "ach-dedup-001"
        await _seed_session(session_id)

        # First call: unlock
        async with _test_session_factory() as db:
            first_unlocked = await check_achievements(db, _TEST_USER.user_id, session_id=session_id)
            await db.commit()

        # Second call: same session, same user — should not unlock again
        async with _test_session_factory() as db:
            second_unlocked = await check_achievements(
                db, _TEST_USER.user_id, session_id=session_id
            )
            await db.commit()

        # first_session should only appear once total
        assert "first_session" in first_unlocked
        assert "first_session" not in second_unlocked

    @pytest.mark.asyncio
    async def test_all_grades_a_unlocks_brake_master(self) -> None:
        """all_grades_a criterion unlocks 'brake_master' for all A braking grades (line 320)."""
        _reset_seeded()
        from backend.api.services.achievement_engine import check_achievements

        session_id = "ach-brakes-a-001"
        await _seed_session(session_id)
        await _seed_coaching_report(
            session_id,
            [
                {"braking": "A", "trail_braking": "B", "min_speed": "B", "throttle": "B"},
                {"braking": "A", "trail_braking": "B", "min_speed": "B", "throttle": "B"},
            ],
        )

        async with _test_session_factory() as db:
            unlocked = await check_achievements(db, _TEST_USER.user_id, session_id=session_id)
            await db.commit()

        assert "brake_master" in unlocked

    @pytest.mark.asyncio
    async def test_all_grades_a_does_not_unlock_with_b_grade(self) -> None:
        """all_grades_a does not unlock if any braking grade is B."""
        _reset_seeded()
        from backend.api.services.achievement_engine import check_achievements

        session_id = "ach-brakes-b-001"
        await _seed_session(session_id)
        await _seed_coaching_report(
            session_id,
            [
                {"braking": "A", "trail_braking": "A", "min_speed": "A", "throttle": "A"},
                {"braking": "B", "trail_braking": "B", "min_speed": "B", "throttle": "B"},
            ],
        )

        async with _test_session_factory() as db:
            unlocked = await check_achievements(db, _TEST_USER.user_id, session_id=session_id)
            await db.commit()

        assert "brake_master" not in unlocked

    @pytest.mark.asyncio
    async def test_all_grades_b_plus_unlocks_smooth_operator(self) -> None:
        """all_grades_b_plus criterion unlocks 'smooth_operator' (line 323)."""
        _reset_seeded()
        from backend.api.services.achievement_engine import check_achievements

        session_id = "ach-smooth-001"
        await _seed_session(session_id)
        await _seed_coaching_report(
            session_id,
            [
                {"braking": "B", "trail_braking": "A", "min_speed": "B", "throttle": "B"},
                {"braking": "B", "trail_braking": "B+", "min_speed": "B", "throttle": "B"},
            ],
        )

        async with _test_session_factory() as db:
            unlocked = await check_achievements(db, _TEST_USER.user_id, session_id=session_id)
            await db.commit()

        assert "smooth_operator" in unlocked

    @pytest.mark.asyncio
    async def test_all_trail_grades_a_unlocks_trail_wizard(self) -> None:
        """all_trail_grades_a criterion unlocks 'trail_wizard' (line 326)."""
        _reset_seeded()
        from backend.api.services.achievement_engine import check_achievements

        session_id = "ach-trail-a-001"
        await _seed_session(session_id)
        await _seed_coaching_report(
            session_id,
            [
                {"braking": "B", "trail_braking": "A", "min_speed": "B", "throttle": "B"},
                {"braking": "A", "trail_braking": "A", "min_speed": "A", "throttle": "A"},
            ],
        )

        async with _test_session_factory() as db:
            unlocked = await check_achievements(db, _TEST_USER.user_id, session_id=session_id)
            await db.commit()

        assert "trail_wizard" in unlocked


# ---------------------------------------------------------------------------
# Tests for _check_all_grades edge cases
# ---------------------------------------------------------------------------


class TestCheckAllGrades:
    """Tests for _check_all_grades helper."""

    @pytest.mark.asyncio
    async def test_returns_false_when_session_id_is_none(self) -> None:
        """_check_all_grades returns False when session_id is None (line 338-339)."""
        from backend.api.services.achievement_engine import _check_all_grades

        async with _test_session_factory() as db:
            result = await _check_all_grades(db, None, "braking", {"A"})
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_when_no_coaching_report(self) -> None:
        """_check_all_grades returns False when no coaching report exists (lines 347-349)."""
        from backend.api.services.achievement_engine import _check_all_grades

        session_id = "ach-no-report-001"
        await _seed_session(session_id)

        async with _test_session_factory() as db:
            result = await _check_all_grades(db, session_id, "braking", {"A"})
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_when_corner_grades_empty(self) -> None:
        """_check_all_grades returns False when corner_grades list is empty (lines 351-353)."""
        from backend.api.services.achievement_engine import _check_all_grades

        session_id = "ach-empty-grades-001"
        await _seed_session(session_id)
        await _seed_coaching_report(session_id, [])

        async with _test_session_factory() as db:
            result = await _check_all_grades(db, session_id, "braking", {"A"})
        assert result is False


# ---------------------------------------------------------------------------
# Tests for get_user_achievements
# ---------------------------------------------------------------------------


class TestGetUserAchievements:
    """Tests for get_user_achievements."""

    @pytest.mark.asyncio
    async def test_returns_all_definitions_with_unlocked_false(self) -> None:
        """get_user_achievements returns all definitions with unlocked=False when none earned."""
        _reset_seeded()
        from backend.api.services.achievement_engine import get_user_achievements

        async with _test_session_factory() as db:
            achievements = await get_user_achievements(db, _TEST_USER.user_id)

        assert len(achievements) > 0
        # Fresh user should have nothing unlocked
        for a in achievements:
            assert a["unlocked"] is False
            assert a["unlocked_at"] is None

    @pytest.mark.asyncio
    async def test_returns_unlocked_achievement_after_check(self) -> None:
        """get_user_achievements shows unlocked=True for earned achievements (lines 372-388)."""
        _reset_seeded()
        from backend.api.services.achievement_engine import (
            check_achievements,
            get_user_achievements,
        )

        session_id = "ach-get-001"
        await _seed_session(session_id)

        async with _test_session_factory() as db:
            await check_achievements(db, _TEST_USER.user_id, session_id=session_id)
            await db.commit()

        async with _test_session_factory() as db:
            achievements = await get_user_achievements(db, _TEST_USER.user_id)

        first_session_ach = next((a for a in achievements if a["id"] == "first_session"), None)
        assert first_session_ach is not None
        assert first_session_ach["unlocked"] is True
        assert first_session_ach["unlocked_at"] is not None

    @pytest.mark.asyncio
    async def test_achievement_schema_has_required_fields(self) -> None:
        """get_user_achievements returns all required schema fields."""
        _reset_seeded()
        from backend.api.services.achievement_engine import get_user_achievements

        async with _test_session_factory() as db:
            achievements = await get_user_achievements(db, _TEST_USER.user_id)

        required_keys = {
            "id",
            "name",
            "description",
            "criteria_type",
            "criteria_value",
            "tier",
            "icon",
            "category",
            "unlocked",
            "session_id",
            "unlocked_at",
        }
        for ach in achievements:
            assert required_keys.issubset(ach.keys())


# ---------------------------------------------------------------------------
# Tests for get_recent_achievements
# ---------------------------------------------------------------------------


class TestGetRecentAchievements:
    """Tests for get_recent_achievements — marks achievements as seen (lines 392-423)."""

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_new_achievements(self) -> None:
        """get_recent_achievements returns [] when no is_new achievements."""
        _reset_seeded()
        from backend.api.services.achievement_engine import get_recent_achievements

        async with _test_session_factory() as db:
            result = await get_recent_achievements(db, _TEST_USER.user_id)

        assert result == []

    @pytest.mark.asyncio
    async def test_returns_new_achievements_and_marks_seen(self) -> None:
        """get_recent_achievements returns new achievements and marks is_new=False (line 420)."""
        _reset_seeded()
        from backend.api.services.achievement_engine import (
            check_achievements,
            get_recent_achievements,
        )

        session_id = "ach-recent-001"
        await _seed_session(session_id)

        async with _test_session_factory() as db:
            await check_achievements(db, _TEST_USER.user_id, session_id=session_id)
            await db.commit()

        # First call: should return newly unlocked achievements
        async with _test_session_factory() as db:
            recent = await get_recent_achievements(db, _TEST_USER.user_id)
            await db.commit()

        assert len(recent) > 0
        assert any(r["id"] == "first_session" for r in recent)

        # Second call: should return empty (already marked as seen)
        async with _test_session_factory() as db:
            recent2 = await get_recent_achievements(db, _TEST_USER.user_id)
            await db.commit()

        assert recent2 == []

    @pytest.mark.asyncio
    async def test_recent_achievements_have_required_fields(self) -> None:
        """get_recent_achievements returns proper schema with all required fields."""
        _reset_seeded()
        from backend.api.services.achievement_engine import (
            check_achievements,
            get_recent_achievements,
        )

        session_id = "ach-schema-001"
        await _seed_session(session_id)

        async with _test_session_factory() as db:
            await check_achievements(db, _TEST_USER.user_id, session_id=session_id)
            await db.commit()

        async with _test_session_factory() as db:
            recent = await get_recent_achievements(db, _TEST_USER.user_id)
            await db.commit()

        if recent:
            required = {
                "id",
                "name",
                "description",
                "tier",
                "icon",
                "category",
                "unlocked",
                "session_id",
                "unlocked_at",
                "criteria_type",
                "criteria_value",
            }
            for r in recent:
                assert required.issubset(r.keys())
                assert r["unlocked"] is True
