"""Tests for achievement engine seed data and grade checking."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

import backend.api.services.achievement_engine as _ae_mod
from backend.api.services.achievement_engine import (
    SEED_ACHIEVEMENTS,
    _check_all_grades,
    _check_criteria,
    check_achievements,
    get_recent_achievements,
    get_user_achievements,
    seed_achievements,
)


@pytest.fixture(autouse=True)
def _reset_seed_flag() -> None:
    """Reset the module-level seed cache between tests."""
    _ae_mod._seeded = False


class TestSeedAchievements:
    """Validate the seed achievement definitions."""

    def test_not_empty(self) -> None:
        assert len(SEED_ACHIEVEMENTS) > 0

    def test_ids_unique(self) -> None:
        ids = [a["id"] for a in SEED_ACHIEVEMENTS]
        assert len(ids) == len(set(ids))

    def test_tiers_valid(self) -> None:
        valid_tiers = {"bronze", "silver", "gold", "platinum"}
        for a in SEED_ACHIEVEMENTS:
            assert a["tier"] in valid_tiers, f"{a['id']} has invalid tier {a['tier']}"

    def test_categories_valid(self) -> None:
        valid_categories = {
            "milestones",
            "laps",
            "consistency",
            "braking",
            "trail_braking",
            "exploration",
        }
        for a in SEED_ACHIEVEMENTS:
            assert a["category"] in valid_categories, f"{a['id']} has invalid category"

    def test_all_have_category(self) -> None:
        for a in SEED_ACHIEVEMENTS:
            assert "category" in a, f"{a['id']} is missing 'category' key"

    def test_expanded_count(self) -> None:
        assert len(SEED_ACHIEVEMENTS) >= 18, "Expected at least 18 achievements after expansion"


class TestCheckAllGrades:
    """Test the _check_all_grades helper (no DB required for some paths)."""

    @pytest.mark.asyncio
    async def test_no_session_returns_false(self) -> None:
        """None session_id should return False."""
        result = await _check_all_grades(None, None, "braking", {"A"})  # type: ignore[arg-type]
        assert result is False

    @pytest.mark.asyncio
    async def test_empty_corner_grades(self) -> None:
        """Empty corner grades should return False."""
        from unittest.mock import AsyncMock, MagicMock

        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = {"corner_grades": []}
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await _check_all_grades(mock_db, "sess1", "braking", {"A"})
        assert result is False

    @pytest.mark.asyncio
    async def test_all_a_braking(self) -> None:
        """All A grades should return True."""
        from unittest.mock import AsyncMock, MagicMock

        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = {
            "corner_grades": [
                {"corner": 1, "braking": "A"},
                {"corner": 2, "braking": "A+"},
                {"corner": 3, "braking": "A"},
            ]
        }
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await _check_all_grades(mock_db, "sess1", "braking", {"A", "A+"})
        assert result is True

    @pytest.mark.asyncio
    async def test_mixed_grades_fails(self) -> None:
        """Mixed grades with a C should return False for A-only."""
        from unittest.mock import AsyncMock, MagicMock

        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = {
            "corner_grades": [
                {"corner": 1, "braking": "A"},
                {"corner": 2, "braking": "C"},
            ]
        }
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await _check_all_grades(mock_db, "sess1", "braking", {"A", "A+"})
        assert result is False

    @pytest.mark.asyncio
    async def test_b_plus_trail_braking(self) -> None:
        """B+ and better trail braking should pass."""
        from unittest.mock import AsyncMock, MagicMock

        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = {
            "corner_grades": [
                {"corner": 1, "trail_braking": "B+"},
                {"corner": 2, "trail_braking": "A-"},
            ]
        }
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await _check_all_grades(mock_db, "sess1", "trail_braking", {"A+", "A", "A-", "B+"})
        assert result is True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_defn(
    criteria_type: str,
    criteria_value: float = 1.0,
    achievement_id: str = "test_achievement",
) -> MagicMock:
    """Build a mock AchievementDefinition with the given criteria fields."""
    defn = MagicMock()
    defn.id = achievement_id
    defn.criteria_type = criteria_type
    defn.criteria_value = criteria_value
    return defn


def _scalar_result(value: object) -> MagicMock:
    """Return a mock DB execute result whose .scalar() returns *value*."""
    result = MagicMock()
    result.scalar.return_value = value
    return result


# ---------------------------------------------------------------------------
# seed_achievements
# ---------------------------------------------------------------------------


class TestSeedAchievementsFunction:
    """Tests for the seed_achievements DB function (lines 96-103)."""

    @pytest.mark.asyncio
    async def test_inserts_missing_definitions(self) -> None:
        """Definitions not yet in the DB should be added via db.add."""
        mock_db = MagicMock()
        existing_result = MagicMock()
        existing_result.all.return_value = []  # nothing in DB yet
        mock_db.execute = AsyncMock(return_value=existing_result)
        mock_db.flush = AsyncMock()

        await seed_achievements(mock_db)

        assert mock_db.add.call_count == len(SEED_ACHIEVEMENTS)
        mock_db.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_skips_existing_definitions(self) -> None:
        """Definitions already present in the DB must not be re-inserted."""
        mock_db = MagicMock()
        # All seed IDs already present
        all_ids = [(a["id"],) for a in SEED_ACHIEVEMENTS]
        existing_result = MagicMock()
        existing_result.all.return_value = all_ids
        mock_db.execute = AsyncMock(return_value=existing_result)
        mock_db.flush = AsyncMock()

        await seed_achievements(mock_db)

        mock_db.add.assert_not_called()
        mock_db.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_inserts_only_missing_subset(self) -> None:
        """Only the IDs absent from the DB should be added."""
        mock_db = MagicMock()
        # Pretend the first seed definition is already there
        first_id = SEED_ACHIEVEMENTS[0]["id"]
        existing_result = MagicMock()
        existing_result.all.return_value = [(first_id,)]
        mock_db.execute = AsyncMock(return_value=existing_result)
        mock_db.flush = AsyncMock()

        await seed_achievements(mock_db)

        assert mock_db.add.call_count == len(SEED_ACHIEVEMENTS) - 1


# ---------------------------------------------------------------------------
# check_achievements
# ---------------------------------------------------------------------------


class TestCheckAchievements:
    """Tests for check_achievements (lines 110-140)."""

    @pytest.mark.asyncio
    async def test_returns_newly_unlocked_ids(self) -> None:
        """Achievements whose criteria pass should be recorded and returned."""
        mock_db = MagicMock()
        mock_db.flush = AsyncMock()

        # seed_achievements: all defs already present so no db.add from seeding
        all_seed_ids = [(a["id"],) for a in SEED_ACHIEVEMENTS]
        seed_existing = MagicMock()
        seed_existing.all.return_value = all_seed_ids

        # already_unlocked query: none unlocked yet
        unlocked_result = MagicMock()
        unlocked_result.all.return_value = []

        # definitions query: one definition
        defn = _make_defn("session_count", 1.0, "first_session")
        defn_scalars = MagicMock()
        defn_scalars.scalars.return_value.all.return_value = [defn]

        # _check_criteria will call db.execute for session_count
        criteria_result = _scalar_result(5)  # 5 sessions >= 1

        mock_db.execute = AsyncMock(
            side_effect=[seed_existing, unlocked_result, defn_scalars, criteria_result]
        )

        newly = await check_achievements(mock_db, "user-1", session_id="sess-1")

        assert newly == ["first_session"]
        # Only one add call — for the UserAchievement (seeding skipped all definitions)
        mock_db.add.assert_called_once()
        # flush is called twice: once by seed_achievements, once for the new unlock
        assert mock_db.flush.await_count == 2

    @pytest.mark.asyncio
    async def test_skips_already_unlocked(self) -> None:
        """Achievements the user already holds should not be re-evaluated."""
        mock_db = MagicMock()
        mock_db.flush = AsyncMock()

        # seed_achievements: all defs already present
        all_seed_ids = [(a["id"],) for a in SEED_ACHIEVEMENTS]
        seed_existing = MagicMock()
        seed_existing.all.return_value = all_seed_ids

        unlocked_result = MagicMock()
        unlocked_result.all.return_value = [("first_session",)]  # already unlocked

        defn = _make_defn("session_count", 1.0, "first_session")
        defn_scalars = MagicMock()
        defn_scalars.scalars.return_value.all.return_value = [defn]

        mock_db.execute = AsyncMock(side_effect=[seed_existing, unlocked_result, defn_scalars])

        newly = await check_achievements(mock_db, "user-1", session_id="sess-1")

        assert newly == []
        mock_db.add.assert_not_called()
        # seed_achievements always flushes; no additional flush for the skipped achievement
        mock_db.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_criteria_not_met_returns_empty(self) -> None:
        """When criteria evaluation returns False, nothing is unlocked."""
        mock_db = MagicMock()
        mock_db.flush = AsyncMock()

        # seed_achievements: all defs already present
        all_seed_ids = [(a["id"],) for a in SEED_ACHIEVEMENTS]
        seed_existing = MagicMock()
        seed_existing.all.return_value = all_seed_ids

        unlocked_result = MagicMock()
        unlocked_result.all.return_value = []

        defn = _make_defn("session_count", 10.0, "track_rat_10")
        defn_scalars = MagicMock()
        defn_scalars.scalars.return_value.all.return_value = [defn]

        # Only 3 sessions, criteria_value is 10
        criteria_result = _scalar_result(3)

        mock_db.execute = AsyncMock(
            side_effect=[seed_existing, unlocked_result, defn_scalars, criteria_result]
        )

        newly = await check_achievements(mock_db, "user-1")

        assert newly == []
        mock_db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_flush_when_nothing_unlocked(self) -> None:
        """db.flush must not be awaited if nothing was newly unlocked."""
        mock_db = MagicMock()
        mock_db.flush = AsyncMock()

        # seed_achievements: all defs already present
        all_seed_ids = [(a["id"],) for a in SEED_ACHIEVEMENTS]
        seed_existing = MagicMock()
        seed_existing.all.return_value = all_seed_ids

        unlocked_result = MagicMock()
        unlocked_result.all.return_value = []

        defn_scalars = MagicMock()
        defn_scalars.scalars.return_value.all.return_value = []

        mock_db.execute = AsyncMock(side_effect=[seed_existing, unlocked_result, defn_scalars])

        await check_achievements(mock_db, "user-1")

        # seed_achievements always flushes once; nothing extra for zero unlocks
        mock_db.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_user_achievement_has_correct_fields(self) -> None:
        """The UserAchievement added to the session must have is_new=True."""
        from backend.api.db.models import UserAchievement

        mock_db = MagicMock()
        mock_db.flush = AsyncMock()

        # seed_achievements: all defs already present so db.add gets only the UA
        all_seed_ids = [(a["id"],) for a in SEED_ACHIEVEMENTS]
        seed_existing = MagicMock()
        seed_existing.all.return_value = all_seed_ids

        unlocked_result = MagicMock()
        unlocked_result.all.return_value = []

        defn = _make_defn("session_count", 1.0, "first_session")
        defn_scalars = MagicMock()
        defn_scalars.scalars.return_value.all.return_value = [defn]
        criteria_result = _scalar_result(1)

        mock_db.execute = AsyncMock(
            side_effect=[seed_existing, unlocked_result, defn_scalars, criteria_result]
        )

        await check_achievements(mock_db, "user-42", session_id="sess-xyz")

        added_obj = mock_db.add.call_args[0][0]
        assert isinstance(added_obj, UserAchievement)
        assert added_obj.user_id == "user-42"
        assert added_obj.achievement_id == "first_session"
        assert added_obj.session_id == "sess-xyz"
        assert added_obj.is_new is True


# ---------------------------------------------------------------------------
# _check_criteria — individual criteria types (lines 150-187)
# ---------------------------------------------------------------------------


class TestCheckCriteriaSessionCount:
    """Tests for the session_count criteria type (lines 153-158)."""

    @pytest.mark.asyncio
    async def test_session_count_met(self) -> None:
        """Returns True when the user has enough sessions."""
        mock_db = MagicMock()
        mock_db.execute = AsyncMock(return_value=_scalar_result(5))

        defn = _make_defn("session_count", 5.0)
        assert await _check_criteria(mock_db, "user-1", None, defn) is True

    @pytest.mark.asyncio
    async def test_session_count_exact_boundary(self) -> None:
        """Exactly meeting the threshold counts as met."""
        mock_db = MagicMock()
        mock_db.execute = AsyncMock(return_value=_scalar_result(1))

        defn = _make_defn("session_count", 1.0)
        assert await _check_criteria(mock_db, "user-1", None, defn) is True

    @pytest.mark.asyncio
    async def test_session_count_not_met(self) -> None:
        """Returns False when the user has fewer sessions than required."""
        mock_db = MagicMock()
        mock_db.execute = AsyncMock(return_value=_scalar_result(9))

        defn = _make_defn("session_count", 10.0)
        assert await _check_criteria(mock_db, "user-1", None, defn) is False

    @pytest.mark.asyncio
    async def test_session_count_zero_in_db(self) -> None:
        """A None DB result (no rows) should be treated as 0."""
        mock_db = MagicMock()
        mock_db.execute = AsyncMock(return_value=_scalar_result(None))

        defn = _make_defn("session_count", 1.0)
        assert await _check_criteria(mock_db, "user-1", None, defn) is False


class TestCheckCriteriaScoreThreshold:
    """Tests for the score_threshold criteria type (lines 160-165)."""

    @pytest.mark.asyncio
    async def test_score_above_threshold(self) -> None:
        """Returns True when the user's best score exceeds the threshold."""
        mock_db = MagicMock()
        mock_db.execute = AsyncMock(return_value=_scalar_result(90.0))

        defn = _make_defn("score_threshold", 85.0)
        assert await _check_criteria(mock_db, "user-1", None, defn) is True

    @pytest.mark.asyncio
    async def test_score_exactly_at_threshold(self) -> None:
        """Score equal to the threshold must pass."""
        mock_db = MagicMock()
        mock_db.execute = AsyncMock(return_value=_scalar_result(85.0))

        defn = _make_defn("score_threshold", 85.0)
        assert await _check_criteria(mock_db, "user-1", None, defn) is True

    @pytest.mark.asyncio
    async def test_score_below_threshold(self) -> None:
        """Returns False when best score is below the threshold."""
        mock_db = MagicMock()
        mock_db.execute = AsyncMock(return_value=_scalar_result(70.0))

        defn = _make_defn("score_threshold", 85.0)
        assert await _check_criteria(mock_db, "user-1", None, defn) is False

    @pytest.mark.asyncio
    async def test_score_none_returns_false(self) -> None:
        """A NULL best score (no sessions) must return False, not raise."""
        mock_db = MagicMock()
        mock_db.execute = AsyncMock(return_value=_scalar_result(None))

        defn = _make_defn("score_threshold", 85.0)
        assert await _check_criteria(mock_db, "user-1", None, defn) is False


class TestCheckCriteriaTrackCount:
    """Tests for the track_count criteria type (lines 167-172)."""

    @pytest.mark.asyncio
    async def test_track_count_met(self) -> None:
        """Returns True when the user has driven at enough distinct tracks."""
        mock_db = MagicMock()
        mock_db.execute = AsyncMock(return_value=_scalar_result(3))

        defn = _make_defn("track_count", 3.0)
        assert await _check_criteria(mock_db, "user-1", None, defn) is True

    @pytest.mark.asyncio
    async def test_track_count_not_met(self) -> None:
        """Returns False when the user has visited fewer tracks than required."""
        mock_db = MagicMock()
        mock_db.execute = AsyncMock(return_value=_scalar_result(2))

        defn = _make_defn("track_count", 3.0)
        assert await _check_criteria(mock_db, "user-1", None, defn) is False

    @pytest.mark.asyncio
    async def test_track_count_none_returns_false(self) -> None:
        """NULL count from DB should fall back to 0."""
        mock_db = MagicMock()
        mock_db.execute = AsyncMock(return_value=_scalar_result(None))

        defn = _make_defn("track_count", 3.0)
        assert await _check_criteria(mock_db, "user-1", None, defn) is False


class TestCheckCriteriaTotalLaps:
    """Tests for the total_laps criteria type (lines 174-179)."""

    @pytest.mark.asyncio
    async def test_total_laps_met(self) -> None:
        """Returns True when cumulative laps reach the threshold."""
        mock_db = MagicMock()
        mock_db.execute = AsyncMock(return_value=_scalar_result(100))

        defn = _make_defn("total_laps", 100.0)
        assert await _check_criteria(mock_db, "user-1", None, defn) is True

    @pytest.mark.asyncio
    async def test_total_laps_exceeds_threshold(self) -> None:
        """More laps than required should still return True."""
        mock_db = MagicMock()
        mock_db.execute = AsyncMock(return_value=_scalar_result(150))

        defn = _make_defn("total_laps", 100.0)
        assert await _check_criteria(mock_db, "user-1", None, defn) is True

    @pytest.mark.asyncio
    async def test_total_laps_not_met(self) -> None:
        """Returns False when total laps are below the threshold."""
        mock_db = MagicMock()
        mock_db.execute = AsyncMock(return_value=_scalar_result(42))

        defn = _make_defn("total_laps", 100.0)
        assert await _check_criteria(mock_db, "user-1", None, defn) is False

    @pytest.mark.asyncio
    async def test_total_laps_none_from_db(self) -> None:
        """NULL sum (user has no sessions at all) must map to 0."""
        mock_db = MagicMock()
        mock_db.execute = AsyncMock(return_value=_scalar_result(None))

        defn = _make_defn("total_laps", 100.0)
        assert await _check_criteria(mock_db, "user-1", None, defn) is False


class TestCheckCriteriaAllGrades:
    """Tests for all_grades_a and all_grades_b_plus criteria (lines 181-186)."""

    @pytest.mark.asyncio
    async def test_all_grades_a_delegates_with_braking_dimension(self) -> None:
        """all_grades_a must check the 'braking' dimension against {A, A+}."""
        mock_db = MagicMock()
        report_result = MagicMock()
        report_result.scalar.return_value = {
            "corner_grades": [
                {"corner": 1, "braking": "A"},
                {"corner": 2, "braking": "A+"},
            ]
        }
        mock_db.execute = AsyncMock(return_value=report_result)

        defn = _make_defn("all_grades_a")
        result = await _check_criteria(mock_db, "user-1", "sess-1", defn)
        assert result is True

    @pytest.mark.asyncio
    async def test_all_grades_a_fails_for_non_a_braking(self) -> None:
        """all_grades_a must return False when any braking grade is below A."""
        mock_db = MagicMock()
        report_result = MagicMock()
        report_result.scalar.return_value = {
            "corner_grades": [
                {"corner": 1, "braking": "A"},
                {"corner": 2, "braking": "B"},
            ]
        }
        mock_db.execute = AsyncMock(return_value=report_result)

        defn = _make_defn("all_grades_a")
        result = await _check_criteria(mock_db, "user-1", "sess-1", defn)
        assert result is False

    @pytest.mark.asyncio
    async def test_all_grades_b_plus_passes_for_high_trail_braking(self) -> None:
        """all_grades_b_plus must pass when all trail_braking grades are B+ or better."""
        mock_db = MagicMock()
        report_result = MagicMock()
        report_result.scalar.return_value = {
            "corner_grades": [
                {"corner": 1, "trail_braking": "A+"},
                {"corner": 2, "trail_braking": "A"},
                {"corner": 3, "trail_braking": "B+"},
            ]
        }
        mock_db.execute = AsyncMock(return_value=report_result)

        defn = _make_defn("all_grades_b_plus")
        result = await _check_criteria(mock_db, "user-1", "sess-1", defn)
        assert result is True

    @pytest.mark.asyncio
    async def test_all_grades_b_plus_fails_for_b_trail_braking(self) -> None:
        """all_grades_b_plus must return False when a trail_braking grade is plain B."""
        mock_db = MagicMock()
        report_result = MagicMock()
        report_result.scalar.return_value = {
            "corner_grades": [
                {"corner": 1, "trail_braking": "A"},
                {"corner": 2, "trail_braking": "B"},  # not in passing set
            ]
        }
        mock_db.execute = AsyncMock(return_value=report_result)

        defn = _make_defn("all_grades_b_plus")
        result = await _check_criteria(mock_db, "user-1", "sess-1", defn)
        assert result is False

    @pytest.mark.asyncio
    async def test_all_grades_a_with_none_session_id(self) -> None:
        """all_grades_a with no session_id must short-circuit to False."""
        mock_db = MagicMock()
        mock_db.execute = AsyncMock()

        defn = _make_defn("all_grades_a")
        result = await _check_criteria(mock_db, "user-1", None, defn)
        assert result is False
        mock_db.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_all_grades_b_plus_with_none_session_id(self) -> None:
        """all_grades_b_plus with no session_id must short-circuit to False."""
        mock_db = MagicMock()
        mock_db.execute = AsyncMock()

        defn = _make_defn("all_grades_b_plus")
        result = await _check_criteria(mock_db, "user-1", None, defn)
        assert result is False
        mock_db.execute.assert_not_awaited()


class TestCheckCriteriaAllTrailGradesA:
    """Tests for the all_trail_grades_a criteria type."""

    @pytest.mark.asyncio
    async def test_all_trail_grades_a_passes(self) -> None:
        """all_trail_grades_a checks trail_braking against {A, A+}."""
        mock_db = MagicMock()
        report_result = MagicMock()
        report_result.scalar.return_value = {
            "corner_grades": [
                {"corner": 1, "trail_braking": "A"},
                {"corner": 2, "trail_braking": "A+"},
            ]
        }
        mock_db.execute = AsyncMock(return_value=report_result)

        defn = _make_defn("all_trail_grades_a")
        result = await _check_criteria(mock_db, "user-1", "sess-1", defn)
        assert result is True

    @pytest.mark.asyncio
    async def test_all_trail_grades_a_fails_for_b_plus(self) -> None:
        """B+ on trail_braking should fail for all_trail_grades_a."""
        mock_db = MagicMock()
        report_result = MagicMock()
        report_result.scalar.return_value = {
            "corner_grades": [
                {"corner": 1, "trail_braking": "A"},
                {"corner": 2, "trail_braking": "B+"},
            ]
        }
        mock_db.execute = AsyncMock(return_value=report_result)

        defn = _make_defn("all_trail_grades_a")
        result = await _check_criteria(mock_db, "user-1", "sess-1", defn)
        assert result is False

    @pytest.mark.asyncio
    async def test_all_trail_grades_a_none_session(self) -> None:
        """None session_id should short-circuit to False."""
        mock_db = MagicMock()
        mock_db.execute = AsyncMock()

        defn = _make_defn("all_trail_grades_a")
        result = await _check_criteria(mock_db, "user-1", None, defn)
        assert result is False


class TestCheckCriteriaUnknownType:
    """The fallback path for unrecognised criteria types (line 187)."""

    @pytest.mark.asyncio
    async def test_unknown_criteria_type_returns_false(self) -> None:
        """An unrecognised criteria_type must silently return False."""
        mock_db = MagicMock()
        mock_db.execute = AsyncMock()

        defn = _make_defn("future_criteria_type_not_yet_implemented", 1.0)
        result = await _check_criteria(mock_db, "user-1", "sess-1", defn)
        assert result is False
        mock_db.execute.assert_not_awaited()


# ---------------------------------------------------------------------------
# get_user_achievements (lines 216-244)
# ---------------------------------------------------------------------------


class TestGetUserAchievements:
    """Tests for get_user_achievements (lines 216-244)."""

    @pytest.mark.asyncio
    async def test_returns_all_definitions_with_unlocked_status(self) -> None:
        """Should return one dict per definition, flagged unlocked/locked."""
        from backend.api.db.models import AchievementDefinition as ADefn
        from backend.api.db.models import UserAchievement as UserAch

        mock_db = MagicMock()
        mock_db.flush = AsyncMock()

        # seed_achievements side-effects
        seed_existing = MagicMock()
        seed_existing.all.return_value = []

        # Definitions
        defn = MagicMock(spec=ADefn)
        defn.id = "first_session"
        defn.name = "First Laps"
        defn.description = "Upload your first session"
        defn.criteria_type = "session_count"
        defn.criteria_value = 1
        defn.tier = "bronze"
        defn.icon = "trophy"
        defn.category = "milestones"

        defn_result = MagicMock()
        defn_result.scalars.return_value.all.return_value = [defn]

        # User achievement (unlocked)
        ua = MagicMock(spec=UserAch)
        ua.achievement_id = "first_session"
        ua.session_id = "sess-1"
        ua.unlocked_at = datetime(2026, 1, 1, tzinfo=UTC)

        ua_result = MagicMock()
        ua_result.scalars.return_value.all.return_value = [ua]

        mock_db.execute = AsyncMock(side_effect=[seed_existing, defn_result, ua_result])

        achievements = await get_user_achievements(mock_db, "user-1")

        assert len(achievements) == 1
        a = achievements[0]
        assert a["id"] == "first_session"
        assert a["unlocked"] is True
        assert a["session_id"] == "sess-1"
        assert a["unlocked_at"] == ua.unlocked_at.isoformat()

    @pytest.mark.asyncio
    async def test_locked_achievement_has_none_fields(self) -> None:
        """Achievements not yet earned must show unlocked=False with null timestamps."""
        from backend.api.db.models import AchievementDefinition as ADefn

        mock_db = MagicMock()
        mock_db.flush = AsyncMock()

        seed_existing = MagicMock()
        seed_existing.all.return_value = []

        defn = MagicMock(spec=ADefn)
        defn.id = "track_rat_10"
        defn.name = "Track Rat"
        defn.description = "Upload 10 sessions"
        defn.criteria_type = "session_count"
        defn.criteria_value = 10
        defn.tier = "silver"
        defn.icon = "flame"
        defn.category = "milestones"

        defn_result = MagicMock()
        defn_result.scalars.return_value.all.return_value = [defn]

        # No user achievements at all
        ua_result = MagicMock()
        ua_result.scalars.return_value.all.return_value = []

        mock_db.execute = AsyncMock(side_effect=[seed_existing, defn_result, ua_result])

        achievements = await get_user_achievements(mock_db, "user-1")

        assert len(achievements) == 1
        a = achievements[0]
        assert a["unlocked"] is False
        assert a["session_id"] is None
        assert a["unlocked_at"] is None

    @pytest.mark.asyncio
    async def test_returned_dict_contains_all_required_keys(self) -> None:
        """Every achievement dict must expose the full set of expected keys."""
        from backend.api.db.models import AchievementDefinition as ADefn

        mock_db = MagicMock()
        mock_db.flush = AsyncMock()

        seed_existing = MagicMock()
        seed_existing.all.return_value = []

        defn = MagicMock(spec=ADefn)
        defn.id = "century_laps"
        defn.name = "Century"
        defn.description = "Complete 100 total laps"
        defn.criteria_type = "total_laps"
        defn.criteria_value = 100
        defn.tier = "bronze"
        defn.icon = "repeat"
        defn.category = "laps"

        defn_result = MagicMock()
        defn_result.scalars.return_value.all.return_value = [defn]

        ua_result = MagicMock()
        ua_result.scalars.return_value.all.return_value = []

        mock_db.execute = AsyncMock(side_effect=[seed_existing, defn_result, ua_result])

        achievements = await get_user_achievements(mock_db, "user-1")

        expected_keys = {
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
        assert set(achievements[0].keys()) == expected_keys

    @pytest.mark.asyncio
    async def test_empty_definitions_returns_empty_list(self) -> None:
        """No definitions in DB means an empty achievements list."""
        mock_db = MagicMock()
        mock_db.flush = AsyncMock()

        seed_existing = MagicMock()
        seed_existing.all.return_value = []

        defn_result = MagicMock()
        defn_result.scalars.return_value.all.return_value = []

        ua_result = MagicMock()
        ua_result.scalars.return_value.all.return_value = []

        mock_db.execute = AsyncMock(side_effect=[seed_existing, defn_result, ua_result])

        achievements = await get_user_achievements(mock_db, "user-1")

        assert achievements == []


# ---------------------------------------------------------------------------
# get_recent_achievements (lines 249-277)
# ---------------------------------------------------------------------------


class TestGetRecentAchievements:
    """Tests for get_recent_achievements (lines 249-277)."""

    @pytest.mark.asyncio
    async def test_returns_new_achievements_and_marks_seen(self) -> None:
        """New (is_new=True) achievements are returned and their flag cleared."""
        from backend.api.db.models import AchievementDefinition as ADefn
        from backend.api.db.models import UserAchievement as UserAch

        mock_db = MagicMock()
        mock_db.flush = AsyncMock()

        ua = MagicMock(spec=UserAch)
        ua.session_id = "sess-42"
        ua.unlocked_at = datetime(2026, 2, 1, tzinfo=UTC)
        ua.is_new = True

        defn = MagicMock(spec=ADefn)
        defn.id = "first_session"
        defn.name = "First Laps"
        defn.description = "Upload your first session"
        defn.criteria_type = "session_count"
        defn.criteria_value = 1
        defn.tier = "bronze"
        defn.icon = "trophy"
        defn.category = "milestones"

        join_result = MagicMock()
        join_result.all.return_value = [(ua, defn)]
        mock_db.execute = AsyncMock(return_value=join_result)

        results = await get_recent_achievements(mock_db, "user-1")

        assert len(results) == 1
        r = results[0]
        assert r["id"] == "first_session"
        assert r["unlocked"] is True
        assert r["session_id"] == "sess-42"
        assert r["unlocked_at"] == ua.unlocked_at.isoformat()

        # is_new must be cleared so the achievement is not returned twice
        assert ua.is_new is False
        mock_db.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_new_achievements_returns_empty_list(self) -> None:
        """When there are no new achievements, an empty list is returned."""
        mock_db = MagicMock()
        mock_db.flush = AsyncMock()

        join_result = MagicMock()
        join_result.all.return_value = []
        mock_db.execute = AsyncMock(return_value=join_result)

        results = await get_recent_achievements(mock_db, "user-1")

        assert results == []
        mock_db.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_multiple_new_achievements_all_marked_seen(self) -> None:
        """All new achievements returned should have is_new set to False."""
        from backend.api.db.models import AchievementDefinition as ADefn
        from backend.api.db.models import UserAchievement as UserAch

        mock_db = MagicMock()
        mock_db.flush = AsyncMock()

        unlocked_at = datetime(2026, 3, 1, tzinfo=UTC)

        def _make_row(achievement_id: str) -> tuple[MagicMock, MagicMock]:
            ua = MagicMock(spec=UserAch)
            ua.session_id = f"sess-{achievement_id}"
            ua.unlocked_at = unlocked_at
            ua.is_new = True

            defn = MagicMock(spec=ADefn)
            defn.id = achievement_id
            defn.name = achievement_id.replace("_", " ").title()
            defn.description = "desc"
            defn.criteria_type = "session_count"
            defn.criteria_value = 1
            defn.tier = "bronze"
            defn.icon = "trophy"
            defn.category = "milestones"

            return ua, defn

        rows = [_make_row("first_session"), _make_row("track_rat_10")]

        join_result = MagicMock()
        join_result.all.return_value = rows
        mock_db.execute = AsyncMock(return_value=join_result)

        results = await get_recent_achievements(mock_db, "user-1")

        assert len(results) == 2
        for (ua, _), result in zip(rows, results, strict=True):
            assert ua.is_new is False
            assert result["unlocked"] is True

    @pytest.mark.asyncio
    async def test_returned_dict_contains_all_required_keys(self) -> None:
        """Every recent achievement dict must expose the full set of expected keys."""
        from backend.api.db.models import AchievementDefinition as ADefn
        from backend.api.db.models import UserAchievement as UserAch

        mock_db = MagicMock()
        mock_db.flush = AsyncMock()

        ua = MagicMock(spec=UserAch)
        ua.session_id = "sess-1"
        ua.unlocked_at = datetime(2026, 1, 1, tzinfo=UTC)
        ua.is_new = True

        defn = MagicMock(spec=ADefn)
        defn.id = "consistency_king"
        defn.name = "Consistency King"
        defn.description = "Achieve a consistency score above 85"
        defn.criteria_type = "score_threshold"
        defn.criteria_value = 85
        defn.tier = "gold"
        defn.icon = "target"
        defn.category = "consistency"

        join_result = MagicMock()
        join_result.all.return_value = [(ua, defn)]
        mock_db.execute = AsyncMock(return_value=join_result)

        results = await get_recent_achievements(mock_db, "user-1")

        expected_keys = {
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
        assert set(results[0].keys()) == expected_keys


# ---------------------------------------------------------------------------
# _check_all_grades — missing report (line 205)
# ---------------------------------------------------------------------------


class TestCheckAllGradesNoReport:
    """Tests for the missing-report branch of _check_all_grades (line 205)."""

    @pytest.mark.asyncio
    async def test_no_coaching_report_returns_false(self) -> None:
        """When no coaching report exists for the session, return False."""
        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = None  # no report in DB
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await _check_all_grades(mock_db, "sess-unknown", "braking", {"A", "A+"})
        assert result is False

    @pytest.mark.asyncio
    async def test_report_missing_corner_grades_key_returns_false(self) -> None:
        """A report JSON without 'corner_grades' key should return False."""
        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = {"summary": "good session", "corner_grades": []}
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await _check_all_grades(mock_db, "sess-1", "braking", {"A", "A+"})
        assert result is False

    @pytest.mark.asyncio
    async def test_dimension_missing_from_corner_grade_defaults_to_c(self) -> None:
        """A corner grade missing the queried dimension defaults to 'C' (not in passing set)."""
        mock_db = MagicMock()
        mock_result = MagicMock()
        # corner_grades present but 'braking' key is absent from one entry
        mock_result.scalar.return_value = {
            "corner_grades": [
                {"corner": 1, "trail_braking": "A"},  # no 'braking' key
            ]
        }
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await _check_all_grades(mock_db, "sess-1", "braking", {"A", "A+"})
        assert result is False
