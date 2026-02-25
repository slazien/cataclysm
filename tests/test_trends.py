"""Tests for cataclysm.trends: snapshots, milestones, and trend analysis."""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pytest

from cataclysm.consistency import CornerConsistencyEntry, LapConsistency
from cataclysm.corners import Corner
from cataclysm.engine import LapSummary
from cataclysm.parser import SessionMetadata
from cataclysm.trends import (
    SessionSnapshot,
    TrendAnalysis,
    _compute_session_id,
    _find_common_corners,
    _parse_session_date,
    build_session_snapshot,
    compute_trend_analysis,
)
from tests.conftest import SnapshotFactory

# ---------------------------------------------------------------------------
# TestSessionSnapshot
# ---------------------------------------------------------------------------


class TestSessionSnapshot:
    """SessionSnapshot dataclass construction and field population."""

    def test_basic_construction(self, session_snapshot_factory: SnapshotFactory) -> None:
        snap = session_snapshot_factory()
        assert isinstance(snap, SessionSnapshot)
        assert snap.n_laps == 5
        assert snap.n_clean_laps == 4

    def test_optimal_lap_time_property(self, session_snapshot_factory: SnapshotFactory) -> None:
        snap = session_snapshot_factory()
        # composite_best_s = best - 0.3, theoretical_best_s = best - 0.5
        assert snap.optimal_lap_time_s == snap.theoretical_best_s
        assert snap.optimal_lap_time_s == min(snap.theoretical_best_s, snap.composite_best_s)

    def test_optimal_prefers_composite_when_lower(
        self, session_snapshot_factory: SnapshotFactory
    ) -> None:
        snap = session_snapshot_factory()
        # Override to make composite lower than theoretical
        # Default: theoretical = best - 0.5, composite = best - 0.3
        # So theoretical is always lower in default fixture.
        # We need a custom snapshot to test the other branch.
        from cataclysm.trends import SessionSnapshot

        # Create a snapshot where composite < theoretical
        custom = SessionSnapshot(
            session_id=snap.session_id,
            metadata=snap.metadata,
            session_date_parsed=snap.session_date_parsed,
            n_laps=snap.n_laps,
            n_clean_laps=snap.n_clean_laps,
            best_lap_time_s=snap.best_lap_time_s,
            top3_avg_time_s=snap.top3_avg_time_s,
            avg_lap_time_s=snap.avg_lap_time_s,
            consistency_score=snap.consistency_score,
            std_dev_s=snap.std_dev_s,
            theoretical_best_s=90.0,
            composite_best_s=89.0,
            lap_times_s=snap.lap_times_s,
            corner_metrics=snap.corner_metrics,
            lap_consistency=snap.lap_consistency,
            corner_consistency=snap.corner_consistency,
        )
        assert custom.optimal_lap_time_s == 89.0

    def test_fields_populated(self, session_snapshot_factory: SnapshotFactory) -> None:
        snap = session_snapshot_factory(best_lap_time_s=90.0, consistency_score=85.0)
        assert snap.best_lap_time_s == 90.0
        assert snap.consistency_score == 85.0
        assert len(snap.lap_times_s) == 4
        assert len(snap.corner_metrics) == 2

    def test_session_id_format(self, session_snapshot_factory: SnapshotFactory) -> None:
        snap = session_snapshot_factory()
        # Format: {track_slug}_{YYYYMMDD}_{hash8}
        parts = snap.session_id.split("_")
        assert len(parts) >= 3
        # Last part is 8-char hex hash
        assert len(parts[-1]) == 8


# ---------------------------------------------------------------------------
# TestBuildSessionSnapshot
# ---------------------------------------------------------------------------


class TestBuildSessionSnapshot:
    """build_session_snapshot() integration with real domain objects."""

    @staticmethod
    def _make_metadata(
        track_name: str = "Test Circuit",
        session_date: str = "22/02/2026 10:00",
    ) -> SessionMetadata:
        return SessionMetadata(
            track_name=track_name,
            session_date=session_date,
            racechrono_version="9.1.3",
        )

    @staticmethod
    def _make_summaries(n: int = 5, base_time: float = 92.0) -> list[LapSummary]:
        return [
            LapSummary(
                lap_number=i + 1,
                lap_time_s=base_time + i * 0.5,
                lap_distance_m=3800.0,
                max_speed_mps=45.0,
            )
            for i in range(n)
        ]

    @staticmethod
    def _make_lap_consistency(score: float = 75.0) -> LapConsistency:
        return LapConsistency(
            std_dev_s=1.2,
            spread_s=2.0,
            mean_abs_consecutive_delta_s=0.5,
            max_consecutive_delta_s=1.0,
            consistency_score=score,
            lap_numbers=[1, 2, 3, 4, 5],
            lap_times_s=[92.0, 92.5, 93.0, 93.5, 94.0],
            consecutive_deltas_s=[0.5, 0.5, 0.5, 0.5],
        )

    @staticmethod
    def _make_corner_consistency() -> list[CornerConsistencyEntry]:
        return [
            CornerConsistencyEntry(
                corner_number=1,
                min_speed_std_mph=1.5,
                min_speed_range_mph=3.0,
                brake_point_std_m=2.0,
                throttle_commit_std_m=1.5,
                consistency_score=80.0,
                lap_numbers=[1, 2, 3],
                min_speeds_mph=[55.0, 56.0, 54.5],
            ),
            CornerConsistencyEntry(
                corner_number=2,
                min_speed_std_mph=2.0,
                min_speed_range_mph=4.0,
                brake_point_std_m=3.0,
                throttle_commit_std_m=2.0,
                consistency_score=70.0,
                lap_numbers=[1, 2, 3],
                min_speeds_mph=[45.0, 46.0, 44.0],
            ),
        ]

    @staticmethod
    def _make_corners(n_laps: int = 3) -> dict[int, list[Corner]]:
        all_corners: dict[int, list[Corner]] = {}
        for lap in range(1, n_laps + 1):
            all_corners[lap] = [
                Corner(
                    number=1,
                    entry_distance_m=500.0,
                    exit_distance_m=700.0,
                    apex_distance_m=600.0,
                    min_speed_mps=24.0 + lap * 0.1,
                    brake_point_m=450.0,
                    peak_brake_g=-0.8,
                    throttle_commit_m=650.0,
                    apex_type="mid",
                ),
                Corner(
                    number=2,
                    entry_distance_m=1200.0,
                    exit_distance_m=1500.0,
                    apex_distance_m=1350.0,
                    min_speed_mps=20.0 + lap * 0.2,
                    brake_point_m=1100.0,
                    peak_brake_g=-0.9,
                    throttle_commit_m=1400.0,
                    apex_type="late",
                ),
            ]
        return all_corners

    def test_basic_fields(self) -> None:
        metadata = self._make_metadata()
        summaries = self._make_summaries(5)
        snap = build_session_snapshot(
            metadata=metadata,
            summaries=summaries,
            lap_consistency=self._make_lap_consistency(),
            corner_consistency=self._make_corner_consistency(),
            gains=None,
            all_lap_corners=self._make_corners(),
            anomalous_laps=set(),
            file_key="test.csv",
        )
        assert snap.n_laps == 5
        assert snap.n_clean_laps == 5
        assert snap.best_lap_time_s == 92.0
        assert snap.metadata.track_name == "Test Circuit"

    def test_top3_avg_with_fewer_than_3_laps(self) -> None:
        metadata = self._make_metadata()
        summaries = self._make_summaries(2)
        snap = build_session_snapshot(
            metadata=metadata,
            summaries=summaries,
            lap_consistency=self._make_lap_consistency(),
            corner_consistency=self._make_corner_consistency(),
            gains=None,
            all_lap_corners=self._make_corners(2),
            anomalous_laps=set(),
            file_key="test.csv",
        )
        # With 2 laps, top3 avg should use all 2
        assert snap.top3_avg_time_s == round(float(np.mean([92.0, 92.5])), 3)

    def test_corner_metrics_populated(self) -> None:
        metadata = self._make_metadata()
        summaries = self._make_summaries(3)
        snap = build_session_snapshot(
            metadata=metadata,
            summaries=summaries,
            lap_consistency=self._make_lap_consistency(),
            corner_consistency=self._make_corner_consistency(),
            gains=None,
            all_lap_corners=self._make_corners(3),
            anomalous_laps=set(),
            file_key="test.csv",
        )
        assert len(snap.corner_metrics) == 2
        assert snap.corner_metrics[0].corner_number == 1
        assert snap.corner_metrics[1].corner_number == 2
        # min_speed_mean_mph should be non-zero (converted from mps)
        assert snap.corner_metrics[0].min_speed_mean_mph > 0

    def test_none_gains(self) -> None:
        metadata = self._make_metadata()
        summaries = self._make_summaries(3)
        snap = build_session_snapshot(
            metadata=metadata,
            summaries=summaries,
            lap_consistency=self._make_lap_consistency(),
            corner_consistency=self._make_corner_consistency(),
            gains=None,
            all_lap_corners=self._make_corners(3),
            anomalous_laps=set(),
            file_key="test.csv",
        )
        # When gains is None, theoretical_best_s and composite_best_s fall back to best_time
        assert snap.theoretical_best_s == snap.best_lap_time_s
        assert snap.composite_best_s == snap.best_lap_time_s

    def test_anomalous_laps_excluded(self) -> None:
        metadata = self._make_metadata()
        summaries = self._make_summaries(5)
        # Mark laps 4 and 5 as anomalous
        snap = build_session_snapshot(
            metadata=metadata,
            summaries=summaries,
            lap_consistency=self._make_lap_consistency(),
            corner_consistency=self._make_corner_consistency(),
            gains=None,
            all_lap_corners=self._make_corners(5),
            anomalous_laps={4, 5},
            file_key="test.csv",
        )
        assert snap.n_laps == 5  # total includes anomalous
        assert snap.n_clean_laps == 3  # only clean laps
        assert len(snap.lap_times_s) == 3


# ---------------------------------------------------------------------------
# TestParseSessionDate
# ---------------------------------------------------------------------------


class TestParseSessionDate:
    """_parse_session_date() format handling."""

    def test_eu_format(self) -> None:
        dt = _parse_session_date("22/02/2026 10:00")
        assert dt == datetime(2026, 2, 22, 10, 0)  # noqa: DTZ001

    def test_eu_comma_format(self) -> None:
        dt = _parse_session_date("22/02/2026,10:00")
        assert dt == datetime(2026, 2, 22, 10, 0)  # noqa: DTZ001

    def test_iso_format(self) -> None:
        dt = _parse_session_date("2026-02-22 10:00:00")
        assert dt == datetime(2026, 2, 22, 10, 0, 0)  # noqa: DTZ001

    def test_iso_short_format(self) -> None:
        dt = _parse_session_date("2026-02-22 10:00")
        assert dt == datetime(2026, 2, 22, 10, 0)  # noqa: DTZ001

    def test_iso8601_format(self) -> None:
        dt = _parse_session_date("2026-02-22T10:00:00")
        assert dt == datetime(2026, 2, 22, 10, 0, 0)  # noqa: DTZ001

    def test_date_only_eu(self) -> None:
        dt = _parse_session_date("22/02/2026")
        assert dt.year == 2026
        assert dt.month == 2
        assert dt.day == 22

    def test_date_only_iso(self) -> None:
        dt = _parse_session_date("2026-02-22")
        assert dt == datetime(2026, 2, 22)  # noqa: DTZ001

    def test_fallback_unparseable(self) -> None:
        dt = _parse_session_date("not-a-date")
        assert dt == datetime.min  # noqa: DTZ001

    def test_whitespace_trimmed(self) -> None:
        dt = _parse_session_date("  2026-02-22 10:00  ")
        assert dt == datetime(2026, 2, 22, 10, 0)  # noqa: DTZ001


# ---------------------------------------------------------------------------
# TestComputeSessionId
# ---------------------------------------------------------------------------


class TestComputeSessionId:
    """_compute_session_id() uniqueness and format."""

    def test_format(self) -> None:
        sid = _compute_session_id("file.csv", "Test Circuit", "22/02/2026 10:00")
        # format: {track_slug}_{YYYYMMDD}_{hash8}
        parts = sid.split("_")
        assert len(parts) >= 3
        assert parts[-1].isalnum()
        assert len(parts[-1]) == 8

    def test_deterministic(self) -> None:
        sid1 = _compute_session_id("file.csv", "Test Circuit", "22/02/2026 10:00")
        sid2 = _compute_session_id("file.csv", "Test Circuit", "22/02/2026 10:00")
        assert sid1 == sid2

    def test_uniqueness_different_files(self) -> None:
        sid1 = _compute_session_id("file_a.csv", "Test Circuit", "22/02/2026 10:00")
        sid2 = _compute_session_id("file_b.csv", "Test Circuit", "22/02/2026 10:00")
        assert sid1 != sid2

    def test_uniqueness_different_dates(self) -> None:
        sid1 = _compute_session_id("file.csv", "Test Circuit", "22/02/2026 10:00")
        sid2 = _compute_session_id("file.csv", "Test Circuit", "23/02/2026 10:00")
        assert sid1 != sid2

    def test_unknown_date_in_id(self) -> None:
        sid = _compute_session_id("file.csv", "Test Circuit", "garbage-date")
        assert "unknown" in sid

    def test_track_slug_lowercase(self) -> None:
        sid = _compute_session_id("f.csv", "Barber Motorsports Park", "2026-01-01")
        assert sid.startswith("barber_motorsports_")


# ---------------------------------------------------------------------------
# TestComputeTrendAnalysis
# ---------------------------------------------------------------------------


class TestComputeTrendAnalysis:
    """compute_trend_analysis() trend computation and sorting."""

    def test_fewer_than_2_sessions_raises(
        self,
        session_snapshot_factory: SnapshotFactory,
    ) -> None:
        snap = session_snapshot_factory()
        with pytest.raises(ValueError, match="At least 2 sessions"):
            compute_trend_analysis([snap])

    def test_two_sessions_works(
        self,
        session_snapshot_factory: SnapshotFactory,
    ) -> None:
        s1 = session_snapshot_factory(
            session_date="01/01/2026 10:00",
            best_lap_time_s=95.0,
            file_key="a.csv",
        )
        s2 = session_snapshot_factory(
            session_date="15/01/2026 10:00",
            best_lap_time_s=93.0,
            file_key="b.csv",
        )
        result = compute_trend_analysis([s1, s2])
        assert isinstance(result, TrendAnalysis)
        assert result.n_sessions == 2
        assert len(result.best_lap_trend) == 2

    def test_chronological_sorting(self, three_session_snapshots: list[SessionSnapshot]) -> None:
        # Pass in reverse order -- should still sort chronologically
        reversed_snaps = list(reversed(three_session_snapshots))
        result = compute_trend_analysis(reversed_snaps)
        dates = [s.session_date_parsed for s in result.sessions]
        assert dates == sorted(dates)

    def test_improving_driver_trends(self, three_session_snapshots: list[SessionSnapshot]) -> None:
        result = compute_trend_analysis(three_session_snapshots)
        # Best lap times should decrease (improving)
        assert result.best_lap_trend == [95.0, 93.0, 91.0]
        # Consistency should increase (improving)
        assert result.consistency_trend == [60.0, 70.0, 82.0]

    def test_common_corners_in_trends(
        self,
        session_snapshot_factory: SnapshotFactory,
    ) -> None:
        # Both sessions have corners 1 and 2 by default
        s1 = session_snapshot_factory(
            session_date="01/01/2026 10:00",
            file_key="a.csv",
        )
        s2 = session_snapshot_factory(
            session_date="15/01/2026 10:00",
            file_key="b.csv",
        )
        result = compute_trend_analysis([s1, s2])
        assert 1 in result.corner_min_speed_trends
        assert 2 in result.corner_min_speed_trends
        assert len(result.corner_min_speed_trends[1]) == 2

    def test_no_common_corners_gives_empty_trends(
        self,
        session_snapshot_factory: SnapshotFactory,
    ) -> None:
        # Session 1 has corners [1,2], session 2 has corners [3,4]
        s1 = session_snapshot_factory(
            session_date="01/01/2026 10:00",
            file_key="a.csv",
            corner_numbers=[1, 2],
        )
        s2 = session_snapshot_factory(
            session_date="15/01/2026 10:00",
            file_key="b.csv",
            corner_numbers=[3, 4],
        )
        result = compute_trend_analysis([s1, s2])
        assert result.corner_min_speed_trends == {}

    def test_track_name_from_first_session(
        self, three_session_snapshots: list[SessionSnapshot]
    ) -> None:
        result = compute_trend_analysis(three_session_snapshots)
        assert result.track_name == "Test Circuit"

    def test_theoretical_trend(self, three_session_snapshots: list[SessionSnapshot]) -> None:
        result = compute_trend_analysis(three_session_snapshots)
        assert len(result.theoretical_trend) == 3
        # Theoretical best is best_lap - 0.5 by fixture design
        assert result.theoretical_trend[0] == pytest.approx(94.5)


# ---------------------------------------------------------------------------
# TestMilestones
# ---------------------------------------------------------------------------


class TestMilestones:
    """Milestone detection in compute_trend_analysis()."""

    def test_pb_detection(self, three_session_snapshots: list[SessionSnapshot]) -> None:
        result = compute_trend_analysis(three_session_snapshots)
        pb_milestones = [m for m in result.milestones if m.category == "pb"]
        # Sessions improve from 95 -> 93 -> 91, so two PBs (session 2 and 3)
        assert len(pb_milestones) == 2
        assert pb_milestones[0].value == 93.0
        assert pb_milestones[1].value == 91.0

    def test_consistency_breakthrough(
        self,
        session_snapshot_factory: SnapshotFactory,
    ) -> None:
        s1 = session_snapshot_factory(
            session_date="01/01/2026 10:00",
            consistency_score=60.0,
            file_key="a.csv",
        )
        s2 = session_snapshot_factory(
            session_date="15/01/2026 10:00",
            consistency_score=75.0,  # +15 points = breakthrough
            file_key="b.csv",
        )
        result = compute_trend_analysis([s1, s2])
        consistency_ms = [m for m in result.milestones if m.category == "consistency"]
        assert len(consistency_ms) == 1
        assert consistency_ms[0].value == 75.0

    def test_sub_threshold(
        self,
        session_snapshot_factory: SnapshotFactory,
    ) -> None:
        # Best time of 94s should trigger sub-1:35 (95s) milestone
        s1 = session_snapshot_factory(
            session_date="01/01/2026 10:00",
            best_lap_time_s=96.0,
            file_key="a.csv",
        )
        s2 = session_snapshot_factory(
            session_date="15/01/2026 10:00",
            best_lap_time_s=94.0,
            file_key="b.csv",
        )
        result = compute_trend_analysis([s1, s2])
        sub_ms = [m for m in result.milestones if m.category == "sub_threshold"]
        # 94s is below 95s barrier and within 5s of it
        assert len(sub_ms) >= 1
        assert any(m.value == 94.0 for m in sub_ms)

    def test_no_milestones_on_regression(
        self,
        session_snapshot_factory: SnapshotFactory,
    ) -> None:
        s1 = session_snapshot_factory(
            session_date="01/01/2026 10:00",
            best_lap_time_s=91.0,
            consistency_score=80.0,
            file_key="a.csv",
        )
        s2 = session_snapshot_factory(
            session_date="15/01/2026 10:00",
            best_lap_time_s=93.0,  # worse
            consistency_score=70.0,  # worse
            file_key="b.csv",
        )
        result = compute_trend_analysis([s1, s2])
        pb_ms = [m for m in result.milestones if m.category == "pb"]
        consistency_ms = [m for m in result.milestones if m.category == "consistency"]
        assert len(pb_ms) == 0
        assert len(consistency_ms) == 0


# ---------------------------------------------------------------------------
# TestFindCommonCorners
# ---------------------------------------------------------------------------


class TestFindCommonCorners:
    """_find_common_corners() set-intersection logic."""

    def test_full_overlap(
        self,
        session_snapshot_factory: SnapshotFactory,
    ) -> None:
        s1 = session_snapshot_factory(corner_numbers=[1, 2, 3], file_key="a.csv")
        s2 = session_snapshot_factory(corner_numbers=[1, 2, 3], file_key="b.csv")
        common = _find_common_corners([s1, s2])
        assert common == [1, 2, 3]

    def test_partial_overlap(
        self,
        session_snapshot_factory: SnapshotFactory,
    ) -> None:
        s1 = session_snapshot_factory(corner_numbers=[1, 2, 3], file_key="a.csv")
        s2 = session_snapshot_factory(corner_numbers=[2, 3, 4], file_key="b.csv")
        common = _find_common_corners([s1, s2])
        assert common == [2, 3]

    def test_no_overlap(
        self,
        session_snapshot_factory: SnapshotFactory,
    ) -> None:
        s1 = session_snapshot_factory(corner_numbers=[1, 2], file_key="a.csv")
        s2 = session_snapshot_factory(corner_numbers=[3, 4], file_key="b.csv")
        common = _find_common_corners([s1, s2])
        assert common == []

    def test_empty_input(self) -> None:
        common = _find_common_corners([])
        assert common == []

    def test_single_session(
        self,
        session_snapshot_factory: SnapshotFactory,
    ) -> None:
        s1 = session_snapshot_factory(corner_numbers=[1, 2, 3], file_key="a.csv")
        common = _find_common_corners([s1])
        assert common == [1, 2, 3]

    def test_three_sessions_intersection(
        self,
        session_snapshot_factory: SnapshotFactory,
    ) -> None:
        s1 = session_snapshot_factory(corner_numbers=[1, 2, 3, 4], file_key="a.csv")
        s2 = session_snapshot_factory(corner_numbers=[2, 3, 4, 5], file_key="b.csv")
        s3 = session_snapshot_factory(corner_numbers=[3, 4, 5, 6], file_key="c.csv")
        common = _find_common_corners([s1, s2, s3])
        assert common == [3, 4]
