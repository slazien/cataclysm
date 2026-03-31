"""Coverage gap tests for small service modules.

Targets the following missing lines:
- achievement_engine.py line 328: _check_criteria returns False for unknown criteria_type
- coaching_store.py lines 176-177: clear_coaching_report SQLAlchemyError handler
- coaching_store.py line 226: record_generation_duration pops oldest when > 20 items
- comparison.py line 131: corner in A that is missing from B is skipped (continue)
- db_coaching_store.py lines 85-88: get_any_coaching_report_db row found, skill_level set
- db_coaching_store.py line 153: delete_coaching_report_for_skill_db flush
- db_session_store.py lines 160-161: store_session_db GPS centroid error path
- equipment_store.py lines 184-189: _vehicle_spec_from_dict with non-list year_range
- equipment_store.py line 412: load_equipment_profiles legacy flat format
- leaderboard_store.py line 141: get_corner_leaderboard dedup keeps only first row per user
- leaderboard_store.py line 157: get_corner_leaderboard king_row is not None
- leaderboard_store.py line 242: update_kings record is None -> continue
- session_store.py line 205: cleanup_expired_anonymous when no sessions expired (no log)
"""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.tests.conftest import _TEST_USER, _test_session_factory

# ===========================================================================
# achievement_engine.py line 328 — unknown criteria_type returns False
# ===========================================================================


class TestAchievementEngineUnknownCriteria:
    """_check_criteria returns False for an unknown criteria_type."""

    @pytest.mark.asyncio
    async def test_unknown_criteria_type_returns_false(self) -> None:
        """Line 328: the final 'return False' when criteria_type is unrecognised."""
        from backend.api.db.models import AchievementDefinition
        from backend.api.services.achievement_engine import _check_criteria

        defn = MagicMock(spec=AchievementDefinition)
        defn.criteria_type = "totally_unknown_type"
        defn.criteria_value = 1

        mock_db = AsyncMock()
        # db.execute should never be called for unknown types — but provide a safe return
        mock_db.execute = AsyncMock(return_value=MagicMock(scalar=MagicMock(return_value=0)))

        result = await _check_criteria(mock_db, "user-abc", "sess-123", defn)
        assert result is False


# ===========================================================================
# coaching_store.py lines 176-177 — SQLAlchemyError in clear_coaching_report
# ===========================================================================


class TestClearCoachingReportDBError:
    """clear_coaching_report handles SQLAlchemyError gracefully (lines 176-177)."""

    @pytest.mark.asyncio
    async def test_clear_coaching_report_sqlalchemy_error_swallowed(self) -> None:
        """SQLAlchemyError during DB delete is caught and logged, not re-raised."""
        from sqlalchemy.exc import SQLAlchemyError

        from backend.api.schemas.coaching import CoachingReportResponse
        from backend.api.services import coaching_store

        # Seed a report in memory so the in-memory pop path is also exercised
        report = MagicMock(spec=CoachingReportResponse)
        coaching_store._reports["err-sess"] = {"intermediate": report}  # noqa: SLF001

        with patch("backend.api.services.coaching_store.async_session_factory") as mock_factory:
            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=AsyncMock())
            mock_ctx.__aexit__ = AsyncMock(return_value=False)
            mock_factory.return_value = mock_ctx
            # Make delete_coaching_report_for_skill_db raise inside the context
            with patch(
                "backend.api.services.coaching_store.delete_coaching_report_for_skill_db",
                side_effect=SQLAlchemyError("db down"),
            ):
                # Should NOT raise
                await coaching_store.clear_coaching_report("err-sess", "intermediate")

        # In-memory report was still removed
        assert "err-sess" not in coaching_store._reports  # noqa: SLF001


# ===========================================================================
# coaching_store.py line 226 — record_generation_duration pops oldest when > 20
# ===========================================================================


class TestRecordGenerationDurationEviction:
    """record_generation_duration pops oldest entry when list exceeds 20."""

    def test_evicts_oldest_when_over_20_entries(self) -> None:
        """Line 226: _generation_durations.pop(0) when len > 20."""
        from backend.api.services import coaching_store

        coaching_store.clear_all_coaching()

        # Fill to exactly 20 first
        for _ in range(20):
            coaching_store.record_generation_duration(10.0)

        assert len(coaching_store._generation_durations) == 20  # noqa: SLF001

        # Adding one more triggers the eviction
        coaching_store.record_generation_duration(99.0)
        assert len(coaching_store._generation_durations) == 20  # noqa: SLF001
        # Most recent value is at the end
        assert coaching_store._generation_durations[-1] == 99.0  # noqa: SLF001

        coaching_store.clear_all_coaching()


# ===========================================================================
# comparison.py line 131 — corner in A missing from B is skipped
# ===========================================================================


class TestComparisonCornerMismatch:
    """Corner present in A but absent from B is skipped (line 131: continue)."""

    @pytest.mark.asyncio
    async def test_corner_missing_in_b_is_skipped(self) -> None:
        """When corners_b_by_num has no entry for a corner in A, it is skipped."""
        import numpy as np
        import pandas as pd

        from backend.api.services.comparison import compare_sessions

        track = "Barber Motorsports Park"

        def _make_corner(number: int) -> MagicMock:
            c = MagicMock()
            c.number = number
            c.min_speed_mps = 20.0
            c.entry_distance_m = float(number * 100)
            c.exit_distance_m = float(number * 100 + 50)
            return c

        def _make_sd(session_id: str, corners_list: list) -> MagicMock:
            sd = MagicMock()
            sd.session_id = session_id
            # validate_session_comparison needs these to be real strings
            sd.snapshot.metadata.track_name = track
            sd.weather = None

            n = 50
            dist = np.linspace(0, 2000, n)
            df = pd.DataFrame(
                {
                    "lap_distance_m": dist,
                    "speed_mps": np.full(n, 30.0),
                    "lat": np.full(n, 33.5),
                    "lon": np.full(n, -86.6),
                }
            )
            summary = MagicMock()
            summary.lap_number = 1
            summary.lap_time_s = 90.0
            summary.lap_distance_m = 2000.0
            sd.processed.best_lap = 1
            sd.processed.resampled_laps = {1: df}
            sd.processed.lap_summaries = [summary]
            sd.corners = corners_list
            sd.all_lap_corners = {1: corners_list}
            return sd

        # Session A has corners 1, 2, 3; Session B has only corners 2, 3
        # Corner 1 in A is missing in B — should be skipped (line 131: continue)
        corners_a_list = [_make_corner(1), _make_corner(2), _make_corner(3)]
        corners_b_list = [_make_corner(2), _make_corner(3)]

        sd_a = _make_sd("comp-a", corners_a_list)
        sd_b = _make_sd("comp-b", corners_b_list)

        delta_mock = MagicMock()
        delta_mock.distance_m = np.array([0.0, 100.0])
        delta_mock.delta_s = np.array([0.0, 0.1])

        with patch(
            "backend.api.services.comparison.compute_delta",
            return_value=delta_mock,
        ):
            result = await compare_sessions(sd_a, sd_b)

        # corner 1 was skipped, so only corners 2 and 3 appear in corner_deltas
        nums = [cd["corner_number"] for cd in result["corner_deltas"]]
        assert 1 not in nums
        assert 2 in nums
        assert 3 in nums


# ===========================================================================
# db_coaching_store.py lines 85-88 — get_any_coaching_report_db row found
# ===========================================================================


class TestGetAnyCoachingReportDb:
    """get_any_coaching_report_db returns report and copies skill_level (lines 85-88)."""

    @pytest.mark.asyncio
    async def test_returns_report_with_skill_level_from_row(self) -> None:
        """Lines 85-88: row found, report built, skill_level set from row."""
        from datetime import UTC, datetime

        from backend.api.db.models import Session as SessionModel
        from backend.api.schemas.coaching import CoachingReportResponse
        from backend.api.services.db_coaching_store import (
            get_any_coaching_report_db,
            upsert_coaching_report_db,
        )

        # coaching_reports has a FK to sessions — insert the session row first
        async with _test_session_factory() as db:
            db.add(
                SessionModel(
                    session_id="dbcr-sess",
                    user_id=_TEST_USER.user_id,
                    track_name="Test Track",
                    session_date=datetime(2026, 1, 1, tzinfo=UTC),
                    file_key="dbcr-sess.csv",
                    n_laps=2,
                    n_clean_laps=1,
                    best_lap_time_s=90.0,
                    consistency_score=85.0,
                )
            )
            await db.commit()

        report = CoachingReportResponse(
            session_id="dbcr-sess",
            status="ready",
            skill_level="expert",
        )

        async with _test_session_factory() as db:
            await upsert_coaching_report_db(db, "dbcr-sess", report, "expert")
            await db.commit()

        async with _test_session_factory() as db:
            result = await get_any_coaching_report_db(db, "dbcr-sess")

        assert result is not None
        assert result.skill_level == "expert"
        assert result.status == "ready"

    @pytest.mark.asyncio
    async def test_returns_none_for_missing_session(self) -> None:
        """Returns None when no coaching report exists for session_id."""
        from backend.api.services.db_coaching_store import get_any_coaching_report_db

        async with _test_session_factory() as db:
            result = await get_any_coaching_report_db(db, "no-such-session")

        assert result is None


# ===========================================================================
# db_coaching_store.py line 153 — delete_coaching_report_for_skill_db flushes
# ===========================================================================


class TestDeleteCoachingReportForSkillDb:
    """delete_coaching_report_for_skill_db deletes and flushes (line 153)."""

    @pytest.mark.asyncio
    async def test_delete_skill_specific_report(self) -> None:
        """After deletion, the report for that skill level is gone."""
        from datetime import UTC, datetime

        from backend.api.db.models import Session as SessionModel
        from backend.api.schemas.coaching import CoachingReportResponse
        from backend.api.services.db_coaching_store import (
            delete_coaching_report_for_skill_db,
            get_coaching_report_db,
            upsert_coaching_report_db,
        )

        # Insert required FK session row first
        async with _test_session_factory() as db:
            db.add(
                SessionModel(
                    session_id="del-skill-sess",
                    user_id=_TEST_USER.user_id,
                    track_name="Test Track",
                    session_date=datetime(2026, 1, 1, tzinfo=UTC),
                    file_key="del-skill-sess.csv",
                    n_laps=2,
                    n_clean_laps=1,
                    best_lap_time_s=90.0,
                    consistency_score=80.0,
                )
            )
            await db.commit()

        report = CoachingReportResponse(
            session_id="del-skill-sess",
            status="ready",
            skill_level="novice",
        )

        async with _test_session_factory() as db:
            await upsert_coaching_report_db(db, "del-skill-sess", report, "novice")
            await db.commit()

        async with _test_session_factory() as db:
            await delete_coaching_report_for_skill_db(db, "del-skill-sess", "novice")
            await db.commit()

        async with _test_session_factory() as db:
            result = await get_coaching_report_db(db, "del-skill-sess", "novice")

        assert result is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_report_is_no_op(self) -> None:
        """Deleting a report that does not exist is a no-op (line 153 still called)."""
        from backend.api.services.db_coaching_store import delete_coaching_report_for_skill_db

        async with _test_session_factory() as db:
            # Should not raise
            await delete_coaching_report_for_skill_db(db, "ghost-sess", "intermediate")
            await db.commit()


# ===========================================================================
# db_session_store.py lines 160-161 — GPS centroid error path
# ===========================================================================


class TestStoreSessionDbGpsCentroidError:
    """store_session_db swallows GPS centroid computation errors (lines 160-161)."""

    @pytest.mark.asyncio
    async def test_gps_centroid_error_swallowed(self) -> None:
        """ValueError from lat/lon computation is caught, not re-raised."""
        from backend.api.services.db_session_store import store_session_db

        # Build a session_data mock where parsed.data.empty raises
        sd = MagicMock()
        sd.session_id = "gps-err-sess"
        sd.snapshot.session_id = "gps-err-sess"
        sd.snapshot.metadata.track_name = "Test Track"
        sd.snapshot.metadata.session_date = "2026-01-01"
        sd.snapshot.n_laps = 2
        sd.snapshot.n_clean_laps = 1
        sd.snapshot.best_lap_time_s = 90.0
        sd.snapshot.top3_avg_time_s = 92.0
        sd.snapshot.avg_lap_time_s = 93.0
        sd.snapshot.consistency_score = 85.0
        sd.snapshot.session_date_parsed = MagicMock()
        sd.weather = None
        sd.gps_quality = None
        sd.timezone_name = None
        sd.session_date_local = None
        sd.session_date_iso = None

        # The except clause in store_session_db catches (ValueError, KeyError, AttributeError).
        # pandas raises TypeError for non-numeric mean, which is NOT caught.
        # Instead use a mock where df["lat"].mean() raises AttributeError.
        bad_df = MagicMock()
        bad_df.empty = False
        bad_df.columns = ["lat", "lon"]
        bad_df.__contains__ = MagicMock(side_effect=lambda key: key in ["lat", "lon"])
        mock_series = MagicMock()
        mock_series.mean = MagicMock(side_effect=AttributeError("no mean available"))
        bad_df.__getitem__ = MagicMock(return_value=mock_series)
        sd.parsed.data = bad_df

        async with _test_session_factory() as db:
            # Should not raise — the ValueError is swallowed
            await store_session_db(db, _TEST_USER.user_id, sd)
            await db.commit()


# ===========================================================================
# equipment_store.py lines 184-189 — _vehicle_spec_from_dict with non-list year_range
# ===========================================================================


class TestVehicleSpecFromDict:
    """_vehicle_spec_from_dict handles non-list year_range with default (lines 184-189)."""

    def test_list_year_range_extracts_values(self) -> None:
        """When year_range is a 2-element list, values are extracted (line 186)."""
        from backend.api.services.equipment_store import _vehicle_spec_from_dict  # noqa: PLC2701

        d: dict[str, object] = {
            "make": "BMW",
            "model": "M2",
            "generation": "G87",
            "year_range": [2023, 2026],  # valid list — hits line 186
            "weight_kg": 1620.0,
            "wheelbase_m": 2.695,
            "track_width_front_m": 1.635,
            "track_width_rear_m": 1.665,
            "cg_height_m": 0.47,
            "weight_dist_front_pct": 50.0,
            "drivetrain": "RWD",
            "hp": 453,
            "torque_nm": 550,
            "has_aero": False,
            "notes": None,
        }

        spec = _vehicle_spec_from_dict(d)
        assert spec.year_range == (2023, 2026)
        assert spec.make == "BMW"

    def test_non_list_year_range_uses_default(self) -> None:
        """When year_range is None or a scalar, the fallback (2000, 2025) is used."""
        from backend.api.services.equipment_store import _vehicle_spec_from_dict  # noqa: PLC2701

        d: dict[str, object] = {
            "make": "Toyota",
            "model": "GR86",
            "generation": "2022+",
            "year_range": None,  # non-list — triggers fallback
            "weight_kg": 1275.0,
            "wheelbase_m": 2.575,
            "track_width_front_m": 1.520,
            "track_width_rear_m": 1.525,
            "cg_height_m": 0.46,
            "weight_dist_front_pct": 53.0,
            "drivetrain": "RWD",
            "hp": 228,
            "torque_nm": 250,
            "has_aero": False,
            "notes": None,
        }

        spec = _vehicle_spec_from_dict(d)
        assert spec.year_range == (2000, 2025)
        assert spec.make == "Toyota"
        assert spec.model == "GR86"

    def test_scalar_year_range_uses_default(self) -> None:
        """A scalar year_range (wrong type) also falls back to default."""
        from backend.api.services.equipment_store import _vehicle_spec_from_dict  # noqa: PLC2701

        d: dict[str, object] = {
            "make": "Mazda",
            "model": "MX-5",
            "generation": "ND2",
            "year_range": 2018,  # scalar, not a list/tuple
            "weight_kg": 1011.0,
            "wheelbase_m": 2.310,
            "track_width_front_m": 1.495,
            "track_width_rear_m": 1.505,
            "cg_height_m": 0.44,
            "weight_dist_front_pct": 52.0,
            "drivetrain": "RWD",
            "hp": 181,
            "torque_nm": 205,
            "has_aero": False,
            "notes": None,
        }

        spec = _vehicle_spec_from_dict(d)
        assert spec.year_range == (2000, 2025)


# ===========================================================================
# equipment_store.py line 412 — load_equipment_profiles legacy flat format
# ===========================================================================


class TestLoadEquipmentProfilesLegacyFormat:
    """load_equipment_profiles handles bare (flat) profile dicts (line 415)."""

    def test_legacy_flat_format_loaded(self) -> None:
        """A JSON file with a bare profile dict (no 'profile' key) is loaded correctly."""
        import json
        import tempfile
        from pathlib import Path

        from backend.api.services import equipment_store

        # Build a legacy flat profile dict (uses valid enum values)
        legacy_profile = {
            "id": "legacy-flat-prof",
            "name": "Legacy Profile",
            "tires": {
                "model": "RE-71RS",
                "compound_category": "super_200tw",
                "size": "245/40ZR18",
                "treadwear_rating": 200,
                "estimated_mu": 1.12,
                "mu_source": "curated_table",
                "mu_confidence": "high",
                "pressure_psi": 34.0,
                "brand": "Bridgestone",
                "age_sessions": 0,
            },
            "brakes": None,
            "suspension": None,
            "notes": None,
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            profiles_dir = Path(tmpdir) / "profiles"
            profiles_dir.mkdir()
            profile_path = profiles_dir / "legacy.json"
            # Flat format: no envelope {"profile": ...}, just the raw dict
            profile_path.write_text(json.dumps(legacy_profile), encoding="utf-8")

            # Reinitialise the store with the temp directory
            equipment_store._equipment_dir = Path(tmpdir)  # noqa: SLF001
            equipment_store._profiles.clear()  # noqa: SLF001

            count = equipment_store.load_persisted_profiles()

        assert count == 1
        loaded = equipment_store.get_profile("legacy-flat-prof")
        assert loaded is not None
        assert loaded.name == "Legacy Profile"

        # Cleanup
        equipment_store._equipment_dir = None  # noqa: SLF001
        equipment_store._profiles.clear()  # noqa: SLF001


# ===========================================================================
# leaderboard_store.py lines 141, 157 — get_corner_leaderboard dedup + king
# ===========================================================================


class TestGetCornerLeaderboard:
    """Tests for get_corner_leaderboard dedup and king rows (lines 141, 157)."""

    @pytest.mark.asyncio
    async def test_dedup_keeps_first_best_row_per_user(self) -> None:
        """When a user has multiple records with same best metric, dedup keeps first (line 141)."""
        from datetime import UTC, datetime

        from backend.api.db.models import Session as SessionModel
        from backend.api.schemas.leaderboard import CornerRecordInput
        from backend.api.services.leaderboard_store import (
            get_corner_leaderboard,
            record_corner_times,
        )

        user_id = _TEST_USER.user_id
        track = "Barber Motorsports Park"

        async with _test_session_factory() as db:
            # Insert two Session rows (two sessions for the same user on same track)
            for i, sess_id in enumerate(["lb-sess-dedup-1", "lb-sess-dedup-2"]):
                db.add(
                    SessionModel(
                        session_id=sess_id,
                        user_id=user_id,
                        track_name=track,
                        session_date=datetime(2026, 1, i + 1, tzinfo=UTC),
                        file_key=f"{sess_id}.csv",
                        n_laps=3,
                        n_clean_laps=2,
                        best_lap_time_s=90.0,
                        consistency_score=80.0,
                    )
                )
            await db.flush()

            # Insert two records with the SAME sector_time_s so the join returns 2 rows
            # for the same user — triggering the dedup continue on line 141
            inputs1 = [
                CornerRecordInput(
                    corner_number=5,
                    min_speed_mps=25.0,
                    sector_time_s=3.3,  # best time, lap 1
                    lap_number=1,
                    brake_point_m=None,
                    consistency_cv=None,
                ),
            ]
            inputs2 = [
                CornerRecordInput(
                    corner_number=5,
                    min_speed_mps=26.0,
                    sector_time_s=3.3,  # same best time — triggers dedup
                    lap_number=2,
                    brake_point_m=None,
                    consistency_cv=None,
                ),
            ]
            await record_corner_times(db, user_id, "lb-sess-dedup-1", track, inputs1)
            await record_corner_times(db, user_id, "lb-sess-dedup-2", track, inputs2)
            await db.commit()

        async with _test_session_factory() as db:
            entries = await get_corner_leaderboard(db, track, 5, limit=10)

        # Should have exactly 1 entry (dedup by user — line 141: second row skipped)
        assert len(entries) == 1
        assert entries[0].sector_time_s == pytest.approx(3.3)

    @pytest.mark.asyncio
    async def test_king_row_found_sets_is_king_true(self) -> None:
        """When a CornerKing row exists, the matching entry has is_king=True (line 157)."""
        from datetime import UTC, datetime

        from backend.api.db.models import (
            CornerKing,
        )
        from backend.api.db.models import (
            Session as SessionModel,
        )
        from backend.api.schemas.leaderboard import CornerRecordInput
        from backend.api.services.leaderboard_store import (
            get_corner_leaderboard,
            record_corner_times,
        )

        user_id = _TEST_USER.user_id
        track = "Road Atlanta"
        corner = 3

        async with _test_session_factory() as db:
            db.add(
                SessionModel(
                    session_id="lb-sess-king",
                    user_id=user_id,
                    track_name=track,
                    session_date=datetime(2026, 1, 1, tzinfo=UTC),
                    file_key="lb-sess-king.csv",
                    n_laps=2,
                    n_clean_laps=1,
                    best_lap_time_s=88.0,
                    consistency_score=85.0,
                )
            )
            await db.flush()

            inputs = [
                CornerRecordInput(
                    corner_number=corner,
                    min_speed_mps=30.0,
                    sector_time_s=2.8,
                    lap_number=1,
                    brake_point_m=None,
                    consistency_cv=None,
                )
            ]
            await record_corner_times(db, user_id, "lb-sess-king", track, inputs)

            # Insert CornerKing row manually to trigger line 157
            db.add(
                CornerKing(
                    track_name=track,
                    corner_number=corner,
                    user_id=user_id,
                    best_time_s=2.8,
                    session_id="lb-sess-king",
                )
            )
            await db.commit()

        async with _test_session_factory() as db:
            entries = await get_corner_leaderboard(db, track, corner, limit=10)

        assert len(entries) == 1
        assert entries[0].is_king is True


# ===========================================================================
# leaderboard_store.py line 242 — update_kings record is None -> continue
# ===========================================================================


class TestUpdateKings:
    """update_kings skips when corner record is not found (line 242: continue)."""

    @pytest.mark.asyncio
    async def test_update_kings_no_records_returns_zero(self) -> None:
        """update_kings returns 0 updated when no corner records exist for the track."""
        from backend.api.services.leaderboard_store import update_kings

        async with _test_session_factory() as db:
            count = await update_kings(db, "Phantom Raceway")
            await db.commit()

        assert count == 0

    @pytest.mark.asyncio
    async def test_update_kings_record_none_skips_corner(self) -> None:
        """Line 242: when record lookup returns None (race condition), corner is skipped."""

        # Patch db.execute to simulate best_rows returning data, but the follow-up
        # record lookup returning None — exercises the `if record is None: continue`.
        class _FakeResult:
            def all(self) -> list:
                return [(5, 2.8)]  # (corner_num, best_time) — 1 row

            def scalar_one_or_none(self) -> None:
                return None  # record not found (race condition)

        mock_db = AsyncMock()
        call_count = 0

        async def _execute_side_effect(stmt: object) -> _FakeResult:
            nonlocal call_count
            call_count += 1
            return _FakeResult()

        mock_db.execute = AsyncMock(side_effect=_execute_side_effect)

        from backend.api.services import leaderboard_store

        count = await leaderboard_store.update_kings(mock_db, "Phantom Track 2")
        assert count == 0  # Skipped because record was None

    @pytest.mark.asyncio
    async def test_update_kings_with_records_sets_king(self) -> None:
        """update_kings sets king correctly when records exist."""
        from datetime import UTC, datetime

        from backend.api.db.models import Session as SessionModel
        from backend.api.schemas.leaderboard import CornerRecordInput
        from backend.api.services.leaderboard_store import record_corner_times, update_kings

        user_id = _TEST_USER.user_id
        track = "VIR"

        async with _test_session_factory() as db:
            db.add(
                SessionModel(
                    session_id="king-sess-vir",
                    user_id=user_id,
                    track_name=track,
                    session_date=datetime(2026, 1, 1, tzinfo=UTC),
                    file_key="king-sess-vir.csv",
                    n_laps=2,
                    n_clean_laps=1,
                    best_lap_time_s=120.0,
                    consistency_score=75.0,
                )
            )
            await db.flush()

            inputs = [
                CornerRecordInput(
                    corner_number=7,
                    min_speed_mps=22.0,
                    sector_time_s=4.1,
                    lap_number=1,
                    brake_point_m=None,
                    consistency_cv=None,
                )
            ]
            await record_corner_times(db, user_id, "king-sess-vir", track, inputs)
            await db.commit()

        async with _test_session_factory() as db:
            count = await update_kings(db, track)
            await db.commit()

        assert count >= 1


# ===========================================================================
# session_store.py line 205 — cleanup_expired_anonymous with no expired sessions
# ===========================================================================


class TestCleanupExpiredAnonymous:
    """cleanup_expired_anonymous returns 0 without logging when nothing expired."""

    def test_get_anonymous_sessions_by_ip_returns_matching(self) -> None:
        """get_anonymous_sessions_by_ip returns sessions matching the IP (line 205)."""
        from backend.api.services import session_store

        session_store.clear_all()

        sd1 = MagicMock()
        sd1.is_anonymous = True
        sd1.client_ip = "192.168.1.1"
        sd2 = MagicMock()
        sd2.is_anonymous = True
        sd2.client_ip = "10.0.0.1"
        session_store._store["ip-anon-1"] = sd1  # noqa: SLF001
        session_store._store["ip-anon-2"] = sd2  # noqa: SLF001

        result = session_store.get_anonymous_sessions_by_ip("192.168.1.1")
        assert len(result) == 1
        assert result[0] is sd1

        session_store.clear_all()

    def test_no_expired_sessions_returns_zero_no_log(self) -> None:
        """Line 205: no sessions expired means no info log (branch not taken)."""
        from backend.api.services import session_store

        session_store.clear_all()

        # Add a fresh anonymous session (not expired)
        sd = MagicMock()
        sd.is_anonymous = True
        sd.created_at = time.time()  # just now
        sd.client_ip = "127.0.0.1"
        session_store._store["fresh-anon"] = sd  # noqa: SLF001

        count = session_store.cleanup_expired_anonymous()

        assert count == 0
        # Session should still be in the store
        assert session_store.get_session("fresh-anon") is not None

        session_store.clear_all()

    def test_expired_sessions_are_removed(self) -> None:
        """Expired anonymous sessions are removed and count is returned."""
        from backend.api.services import session_store

        session_store.clear_all()

        sd_old = MagicMock()
        sd_old.is_anonymous = True
        sd_old.created_at = 0.0  # epoch — definitely expired
        sd_old.client_ip = "10.0.0.1"
        session_store._store["expired-anon"] = sd_old  # noqa: SLF001

        count = session_store.cleanup_expired_anonymous()
        assert count == 1
        assert session_store.get_session("expired-anon") is None

        session_store.clear_all()
