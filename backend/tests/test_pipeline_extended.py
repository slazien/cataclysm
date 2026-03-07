"""Extended tests for backend.api.services.pipeline.

Targets missing coverage lines:
- 197-200: line analysis exception -> gps_traces=[], reference_centerline=None
- 216: all_lap_corners with best_lap == lap_num (direct assignment path)
- 238-239: corner line analysis exception path
- 252-253: consistency exception path (already covered by test_pipeline.py
            but we hit it via a different code path to ensure 252 vs 253)
- 266-267: gains exception path
- 442: _has_meaningful_grip — session has no equipment
- 457: _try_lidar_elevation — lat/lon missing from best_lap_df
- 471-475: _try_lidar_elevation — TimeoutError / general exception paths
- 484-494: _track_lidar_task — done callback with exception / cancellation
- 499-501: _lidar_prefetch_impl — result is not None path
- 514: trigger_lidar_prefetch
- 534: invalidate_physics_cache when keys_to_remove is empty (no log)
- 543: invalidate_profile_cache when keys_to_remove is empty (no log)
- 554: _get_physics_cached — cache miss
- 561: _set_physics_cached — LRU eviction path
- 592-597: _resolve_curvature_and_elevation — canonical reference with/without elevation
- 596-597: fallback curvature path
- 670: get_optimal_profile_data — altitude_m fallback from GPS column
- 724-859: get_optimal_comparison_data — full function body
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from backend.api.services import equipment_store
from backend.api.services import pipeline as pipeline_module
from backend.api.services.pipeline import (
    _collect_independent_calibration_telemetry,
    _get_physics_cached,
    _has_meaningful_grip,
    _resolve_curvature_and_elevation,
    _set_physics_cached,
    _track_lidar_task,
    _try_lidar_elevation,
    get_ideal_lap_data,
    get_optimal_comparison_data,
    get_optimal_profile_data,
    invalidate_physics_cache,
    invalidate_profile_cache,
)
from backend.api.services.session_store import SessionData

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_lap_df(
    *,
    has_lat_lon: bool = True,
    has_altitude: bool = False,
    has_g_cols: bool = True,
) -> MagicMock:
    import pandas as pd

    df = MagicMock(spec=pd.DataFrame)
    if has_lat_lon:
        df.columns = ["lat", "lon", "lap_distance_m", "lateral_g", "longitudinal_g"]
    else:
        df.columns = ["lap_distance_m"]
    if has_altitude:
        df.columns = list(df.columns) + ["altitude_m"]

    df.__contains__ = lambda self, key: key in self.columns
    df.__getitem__ = MagicMock(return_value=MagicMock())
    df.iloc = MagicMock()

    # Simulate to_numpy() returning a short float array
    mock_series = MagicMock()
    mock_series.to_numpy = MagicMock(return_value=np.array([33.5, 33.51, 33.52]))
    df.__getitem__.return_value = mock_series
    return df


def _make_processed(best_lap: int = 1, n_laps: int = 3) -> MagicMock:
    processed = MagicMock()
    processed.best_lap = best_lap
    processed.resampled_laps = {i: _make_mock_lap_df() for i in range(1, n_laps + 1)}
    processed.lap_summaries = [MagicMock() for _ in range(n_laps)]
    return processed


def _make_parsed(*, n_coaching_laps: int = 3) -> MagicMock:
    import pandas as pd

    parsed = MagicMock()
    parsed.metadata.track_name = "Test Circuit"
    parsed.metadata.session_date = "22/02/2026"
    parsed.data = pd.DataFrame({"lat": [33.53], "lon": [-86.62], "speed": [30.0]})
    parsed.raw_data = None
    return parsed


def _make_snapshot(session_id: str = "ps-sess-1") -> MagicMock:
    snap = MagicMock()
    snap.session_id = session_id
    snap.metadata.track_name = "Test Circuit"
    snap.metadata.session_date = "22/02/2026"
    snap.n_laps = 3
    snap.n_clean_laps = 2
    snap.best_lap_time_s = 90.5
    return snap


def _make_session_data(session_id: str = "ps-sess-1", n_laps: int = 3) -> MagicMock:
    sd = MagicMock()
    sd.session_id = session_id
    sd.snapshot = _make_snapshot(session_id)
    sd.processed = _make_processed(n_laps=n_laps)
    sd.corners = []
    sd.all_lap_corners = {}
    sd.coaching_laps = list(range(1, n_laps + 1))
    sd.layout = None
    sd.gps_traces = []
    sd.reference_centerline = None
    sd.corner_line_profiles = []
    sd.gps_quality = None
    return sd


# Core patches always applied in _run_pipeline_sync tests
_BASE_PATCHES = [
    "backend.api.services.pipeline.parse_racechrono_csv",
    "backend.api.services.pipeline.process_session",
    "backend.api.services.pipeline.find_anomalous_laps",
    "backend.api.services.pipeline.detect_track_or_lookup",
    "backend.api.services.pipeline.locate_official_corners",
    "backend.api.services.pipeline.extract_corner_kpis_for_lap",
    "backend.api.services.pipeline.detect_corners",
    "backend.api.services.pipeline.compute_corner_elevation",
    "backend.api.services.pipeline.enrich_corners_with_elevation",
    "backend.api.services.pipeline.assess_gps_quality",
    "backend.api.services.pipeline.compute_session_consistency",
    "backend.api.services.pipeline.estimate_gains",
    "backend.api.services.pipeline.estimate_grip_limit",
    "backend.api.services.pipeline.build_session_snapshot",
    "backend.api.services.pipeline._fallback_lap_consistency",
    "backend.api.services.pipeline.should_enable_line_analysis",
    "backend.api.services.pipeline.build_gps_trace",
    "backend.api.services.pipeline.compute_reference_centerline",
    "backend.api.services.pipeline.analyze_corner_lines",
    "backend.api.services.pipeline.maybe_update_track_reference",
]


def _apply_base_mocks(mocks: dict[str, MagicMock]) -> None:
    parsed = _make_parsed()
    processed = _make_processed(n_laps=3)
    snap = _make_snapshot()
    mocks["parse_racechrono_csv"].return_value = parsed
    mocks["process_session"].return_value = processed
    mocks["find_anomalous_laps"].return_value = set()
    mocks["detect_track_or_lookup"].return_value = None
    mocks["detect_corners"].return_value = [MagicMock()]
    mocks["extract_corner_kpis_for_lap"].return_value = []
    mocks["compute_corner_elevation"].return_value = {}
    mocks["assess_gps_quality"].return_value = MagicMock(overall_score=95.0, grade="A")
    mocks["compute_session_consistency"].return_value = MagicMock(
        lap_consistency=MagicMock(), corner_consistency=[]
    )
    mocks["estimate_gains"].return_value = MagicMock()
    mocks["estimate_grip_limit"].return_value = MagicMock()
    mocks["build_session_snapshot"].return_value = snap
    mocks["_fallback_lap_consistency"].return_value = MagicMock()
    mocks["should_enable_line_analysis"].return_value = True
    mocks["build_gps_trace"].return_value = MagicMock()
    mocks["compute_reference_centerline"].return_value = MagicMock()
    mocks["analyze_corner_lines"].return_value = []
    mocks["maybe_update_track_reference"].return_value = None
    return parsed, processed, snap


# ===========================================================================
# _run_pipeline_sync — GPS line analysis exception path (lines 197-200)
# ===========================================================================


class TestLineAnalysisExceptionPath:
    """GPS line analysis error path coverage (lines 197-200)."""

    def _run_with_line_analysis_error(self) -> SessionData:
        with (
            patch("backend.api.services.pipeline.parse_racechrono_csv") as m_parse,
            patch("backend.api.services.pipeline.process_session") as m_process,
            patch("backend.api.services.pipeline.find_anomalous_laps") as m_anom,
            patch("backend.api.services.pipeline.detect_track_or_lookup") as m_track,
            patch("backend.api.services.pipeline.locate_official_corners"),
            patch("backend.api.services.pipeline.extract_corner_kpis_for_lap") as m_extract,
            patch("backend.api.services.pipeline.detect_corners") as m_detect,
            patch("backend.api.services.pipeline.compute_corner_elevation") as m_elev,
            patch("backend.api.services.pipeline.enrich_corners_with_elevation"),
            patch("backend.api.services.pipeline.assess_gps_quality") as m_gps,
            patch("backend.api.services.pipeline.compute_session_consistency") as m_consist,
            patch("backend.api.services.pipeline.estimate_gains") as m_gains,
            patch("backend.api.services.pipeline.estimate_grip_limit") as m_grip,
            patch("backend.api.services.pipeline.build_session_snapshot") as m_snap,
            patch("backend.api.services.pipeline._fallback_lap_consistency") as m_fallback,
            patch("backend.api.services.pipeline.should_enable_line_analysis") as m_line_ok,
            patch("backend.api.services.pipeline.build_gps_trace") as m_trace,
            patch("backend.api.services.pipeline.compute_reference_centerline"),
            patch("backend.api.services.pipeline.analyze_corner_lines") as m_corner_lines,
            patch("backend.api.services.pipeline.maybe_update_track_reference"),
        ):
            parsed = _make_parsed()
            processed = _make_processed(n_laps=4)
            snap = _make_snapshot()
            m_parse.return_value = parsed
            m_process.return_value = processed
            m_anom.return_value = set()
            m_track.return_value = None
            m_detect.return_value = [MagicMock()]
            m_extract.return_value = []
            m_elev.return_value = {}
            m_gps.return_value = MagicMock(overall_score=95.0, grade="A")
            m_consist.return_value = MagicMock(lap_consistency=MagicMock(), corner_consistency=[])
            m_gains.return_value = MagicMock()
            m_grip.return_value = MagicMock()
            m_snap.return_value = snap
            m_fallback.return_value = MagicMock()
            m_line_ok.return_value = True  # line analysis enabled
            # Make build_gps_trace raise to trigger the except block (lines 197-200)
            m_trace.side_effect = ValueError("trace build failure")
            m_corner_lines.return_value = []

            return pipeline_module._run_pipeline_sync(b"fake_csv", "test.csv")  # noqa: SLF001

    def test_line_analysis_exception_clears_traces(self) -> None:
        """When build_gps_trace raises, gps_traces and reference_centerline are reset to empty."""
        result = self._run_with_line_analysis_error()
        assert result.gps_traces == []
        assert result.reference_centerline is None


# ===========================================================================
# _run_pipeline_sync — best_lap == lap_num path (line 216)
# ===========================================================================


class TestAllLapCornersDirectAssignment:
    """all_lap_corners direct assignment when lap_num == best_lap (line 216)."""

    def test_best_lap_uses_already_detected_corners(self) -> None:
        """When lap_num == best_lap the corners list is reused directly."""
        with (
            patch("backend.api.services.pipeline.parse_racechrono_csv") as m_parse,
            patch("backend.api.services.pipeline.process_session") as m_process,
            patch("backend.api.services.pipeline.find_anomalous_laps") as m_anom,
            patch("backend.api.services.pipeline.detect_track_or_lookup") as m_track,
            patch("backend.api.services.pipeline.locate_official_corners"),
            patch("backend.api.services.pipeline.extract_corner_kpis_for_lap") as m_extract,
            patch("backend.api.services.pipeline.detect_corners") as m_detect,
            patch("backend.api.services.pipeline.compute_corner_elevation") as m_elev,
            patch("backend.api.services.pipeline.enrich_corners_with_elevation"),
            patch("backend.api.services.pipeline.assess_gps_quality") as m_gps,
            patch("backend.api.services.pipeline.compute_session_consistency") as m_consist,
            patch("backend.api.services.pipeline.estimate_gains") as m_gains,
            patch("backend.api.services.pipeline.estimate_grip_limit") as m_grip,
            patch("backend.api.services.pipeline.build_session_snapshot") as m_snap,
            patch("backend.api.services.pipeline._fallback_lap_consistency") as m_fallback,
            patch("backend.api.services.pipeline.should_enable_line_analysis") as m_line_ok,
            patch("backend.api.services.pipeline.analyze_corner_lines") as m_corner_lines,
            patch("backend.api.services.pipeline.maybe_update_track_reference"),
        ):
            parsed = _make_parsed()
            # best_lap = 2, coaching_laps includes 2
            processed = _make_processed(best_lap=2, n_laps=3)
            snap = _make_snapshot()
            corners_sentinel = [MagicMock(name="corner_sentinel")]
            m_parse.return_value = parsed
            m_process.return_value = processed
            m_anom.return_value = set()
            m_track.return_value = None
            m_detect.return_value = corners_sentinel  # this is assigned for best_lap
            m_extract.return_value = []
            m_elev.return_value = {}
            m_gps.return_value = MagicMock(overall_score=95.0, grade="A")
            m_consist.return_value = MagicMock(lap_consistency=MagicMock(), corner_consistency=[])
            m_gains.return_value = MagicMock()
            m_grip.return_value = MagicMock()
            m_snap.return_value = snap
            m_fallback.return_value = MagicMock()
            m_line_ok.return_value = False
            m_corner_lines.return_value = []

            result = pipeline_module._run_pipeline_sync(b"fake_csv", "test.csv")  # noqa: SLF001

        # all_lap_corners[best_lap] should be the same object returned by detect_corners
        assert result.all_lap_corners.get(2) is corners_sentinel


# ===========================================================================
# _run_pipeline_sync — corner line analysis exception (lines 238-239)
# ===========================================================================


class TestCornerLineAnalysisExceptionPath:
    """analyze_corner_lines exception -> graceful recovery (lines 238-239)."""

    def test_corner_line_analysis_exception_swallowed(self) -> None:
        with (
            patch("backend.api.services.pipeline.parse_racechrono_csv") as m_parse,
            patch("backend.api.services.pipeline.process_session") as m_process,
            patch("backend.api.services.pipeline.find_anomalous_laps") as m_anom,
            patch("backend.api.services.pipeline.detect_track_or_lookup") as m_track,
            patch("backend.api.services.pipeline.locate_official_corners"),
            patch("backend.api.services.pipeline.extract_corner_kpis_for_lap") as m_extract,
            patch("backend.api.services.pipeline.detect_corners") as m_detect,
            patch("backend.api.services.pipeline.compute_corner_elevation") as m_elev,
            patch("backend.api.services.pipeline.enrich_corners_with_elevation"),
            patch("backend.api.services.pipeline.assess_gps_quality") as m_gps,
            patch("backend.api.services.pipeline.compute_session_consistency") as m_consist,
            patch("backend.api.services.pipeline.estimate_gains") as m_gains,
            patch("backend.api.services.pipeline.estimate_grip_limit") as m_grip,
            patch("backend.api.services.pipeline.build_session_snapshot") as m_snap,
            patch("backend.api.services.pipeline._fallback_lap_consistency") as m_fallback,
            patch("backend.api.services.pipeline.should_enable_line_analysis") as m_line_ok,
            patch("backend.api.services.pipeline.build_gps_trace") as m_trace,
            patch("backend.api.services.pipeline.compute_reference_centerline"),
            patch("backend.api.services.pipeline.analyze_corner_lines") as m_corner_lines,
            patch("backend.api.services.pipeline.maybe_update_track_reference"),
        ):
            parsed = _make_parsed()
            processed = _make_processed(n_laps=4)
            snap = _make_snapshot()
            m_parse.return_value = parsed
            m_process.return_value = processed
            m_anom.return_value = set()
            m_track.return_value = None
            m_detect.return_value = [MagicMock()]  # non-empty corners needed
            m_extract.return_value = []
            m_elev.return_value = {}
            m_gps.return_value = MagicMock(overall_score=95.0, grade="A")
            m_consist.return_value = MagicMock(lap_consistency=MagicMock(), corner_consistency=[])
            m_gains.return_value = MagicMock()
            m_grip.return_value = MagicMock()
            m_snap.return_value = snap
            m_fallback.return_value = MagicMock()
            m_line_ok.return_value = True
            m_trace.return_value = MagicMock()  # traces built OK
            # analyze_corner_lines raises
            m_corner_lines.side_effect = ValueError("line analysis failure")

            result = pipeline_module._run_pipeline_sync(b"fake_csv", "test.csv")  # noqa: SLF001

        # Pipeline must succeed, corner_line_profiles stays empty
        assert result is not None
        assert result.corner_line_profiles == []


# ===========================================================================
# Physics cache functions
# ===========================================================================


class TestPhysicsCacheFunctions:
    """Tests for cache get/set/invalidate paths."""

    def setup_method(self) -> None:
        # Clear cache before each test
        pipeline_module._physics_cache.clear()  # noqa: SLF001

    def test_get_physics_cached_miss_returns_none(self) -> None:
        """Cache miss returns None (line 554)."""
        result = _get_physics_cached("no-session", "profile", None)
        assert result is None

    def test_set_physics_cached_stores_entry(self) -> None:
        """_set_physics_cached stores a result and it can be retrieved."""
        data = {"distance_m": [0.0, 100.0]}
        _set_physics_cached("sess-cache", "profile", data, "prof-1")
        retrieved = _get_physics_cached("sess-cache", "profile", "prof-1")
        assert retrieved == data

    def test_get_physics_cached_expired_entry_returns_none(self) -> None:
        """An expired cache entry is treated as a miss."""
        data = {"distance_m": [0.0]}
        cache_key = ("sess-expired:profile", "prof-2")
        # Insert entry with a timestamp in the past
        pipeline_module._physics_cache[cache_key] = (data, time.time() - 99999)  # noqa: SLF001
        result = _get_physics_cached("sess-expired", "profile", "prof-2")
        assert result is None

    def test_set_physics_cached_lru_eviction(self) -> None:
        """When cache exceeds PHYSICS_CACHE_MAX_ENTRIES, oldest entry is evicted (line 561)."""
        max_entries = pipeline_module.PHYSICS_CACHE_MAX_ENTRIES
        # Fill cache to exactly max_entries using direct dict manipulation
        for i in range(max_entries):
            cache_key = (f"sess-lru-{i}:profile", None)
            pipeline_module._physics_cache[cache_key] = ({"x": i}, time.time() - (max_entries - i))  # noqa: SLF001

        # Insert one more via _set_physics_cached — triggers eviction
        _set_physics_cached("sess-lru-overflow", "profile", {"overflow": True}, None)

        # Cache should not exceed max_entries + 1 before eviction, and now at max
        assert len(pipeline_module._physics_cache) <= max_entries  # noqa: SLF001

    def test_invalidate_physics_cache_removes_entries(self) -> None:
        """invalidate_physics_cache removes all keys for the given session."""
        _set_physics_cached("sess-inv", "profile", {"a": 1}, "p1")
        _set_physics_cached("sess-inv", "comparison", {"b": 2}, "p1")
        _set_physics_cached("sess-other", "profile", {"c": 3}, "p1")

        invalidate_physics_cache("sess-inv")

        assert _get_physics_cached("sess-inv", "profile", "p1") is None
        assert _get_physics_cached("sess-inv", "comparison", "p1") is None
        # Other session untouched
        assert _get_physics_cached("sess-other", "profile", "p1") is not None

    def test_invalidate_physics_cache_empty_does_not_log(self) -> None:
        """invalidate_physics_cache with no matching keys does not raise (line 534 — no-op)."""
        pipeline_module._physics_cache.clear()  # noqa: SLF001
        # Should complete without error and without logging
        invalidate_physics_cache("nonexistent-session")

    def test_invalidate_profile_cache_removes_entries(self) -> None:
        """invalidate_profile_cache removes all cache entries for a profile."""
        _set_physics_cached("sess-pc", "profile", {"d": 4}, "prof-target")
        _set_physics_cached("sess-pc2", "comparison", {"e": 5}, "prof-target")
        _set_physics_cached("sess-pc3", "profile", {"f": 6}, "prof-other")

        invalidate_profile_cache("prof-target")

        assert _get_physics_cached("sess-pc", "profile", "prof-target") is None
        assert _get_physics_cached("sess-pc2", "comparison", "prof-target") is None
        # Different profile untouched
        assert _get_physics_cached("sess-pc3", "profile", "prof-other") is not None

    def test_invalidate_profile_cache_empty_does_not_raise(self) -> None:
        """invalidate_profile_cache with no matching keys does not raise (line 543)."""
        pipeline_module._physics_cache.clear()  # noqa: SLF001
        invalidate_profile_cache("no-such-profile")


# ===========================================================================
# _has_meaningful_grip (line 442)
# ===========================================================================


class TestHasMeaningfulGrip:
    """Tests for _has_meaningful_grip."""

    def setup_method(self) -> None:
        equipment_store.clear_all_equipment()

    def test_returns_false_when_no_session_equipment(self) -> None:
        """Returns False when no equipment is assigned to the session (line 439)."""
        result = _has_meaningful_grip("sess-no-equip")
        assert result is False

    def test_returns_false_when_profile_missing(self) -> None:
        """Returns False when the profile referenced by session equipment does not exist."""
        from cataclysm.equipment import SessionEquipment

        se = SessionEquipment(
            session_id="sess-orphan-grip",
            profile_id="ghost-profile",
            overrides={},
            conditions=None,
        )
        equipment_store.store_session_equipment(se)
        result = _has_meaningful_grip("sess-orphan-grip")
        assert result is False

    def test_returns_false_for_formula_estimate_mu_1_0(self) -> None:
        """Returns False when mu=1.0 from FORMULA_ESTIMATE — the uncalibrated sentinel."""
        from cataclysm.equipment import (
            EquipmentProfile,
            MuSource,
            SessionEquipment,
            TireCompoundCategory,
            TireSpec,
        )

        tire = TireSpec(
            model="Generic",
            compound_category=TireCompoundCategory.STREET,
            size="205/55R16",
            treadwear_rating=0,
            estimated_mu=1.0,
            mu_source=MuSource.FORMULA_ESTIMATE,
            mu_confidence="low",
            pressure_psi=32.0,
            brand="Generic",
            age_sessions=0,
        )
        profile = EquipmentProfile(
            id="hmg-formula-prof",
            name="Formula Profile",
            tires=tire,
            brakes=None,
            suspension=None,
            notes=None,
        )
        se = SessionEquipment(
            session_id="sess-formula-grip",
            profile_id="hmg-formula-prof",
            overrides={},
            conditions=None,
        )
        equipment_store.store_profile(profile)
        equipment_store.store_session_equipment(se)

        result = _has_meaningful_grip("sess-formula-grip")
        assert result is False

    def test_returns_true_for_curated_mu(self) -> None:
        """Returns True when mu has a curated/meaningful source."""
        from cataclysm.equipment import (
            EquipmentProfile,
            MuSource,
            SessionEquipment,
            TireCompoundCategory,
            TireSpec,
        )

        tire = TireSpec(
            model="RE-71RS",
            compound_category=TireCompoundCategory.SUPER_200TW,
            size="245/40ZR18",
            treadwear_rating=200,
            estimated_mu=1.12,
            mu_source=MuSource.CURATED_TABLE,
            mu_confidence="high",
            pressure_psi=34.0,
            brand="Bridgestone",
            age_sessions=2,
        )
        profile = EquipmentProfile(
            id="hmg-curated-prof",
            name="Curated Profile",
            tires=tire,
            brakes=None,
            suspension=None,
            notes=None,
        )
        se = SessionEquipment(
            session_id="sess-curated-grip",
            profile_id="hmg-curated-prof",
            overrides={},
            conditions=None,
        )
        equipment_store.store_profile(profile)
        equipment_store.store_session_equipment(se)

        result = _has_meaningful_grip("sess-curated-grip")
        assert result is True


# ===========================================================================
# _try_lidar_elevation (lines 457, 471-475)
# ===========================================================================


class TestTryLidarElevation:
    """Tests for _try_lidar_elevation async function."""

    @pytest.mark.asyncio
    async def test_returns_none_when_lat_lon_missing(self) -> None:
        """Returns None immediately when lat/lon columns are absent (line 457)."""
        import pandas as pd

        sd = MagicMock()
        sd.processed.best_lap = 1
        df = MagicMock(spec=pd.DataFrame)
        df.columns = ["lap_distance_m", "speed"]
        df.__contains__ = lambda self, key: key in self.columns
        sd.processed.resampled_laps = {1: df}

        result = await _try_lidar_elevation(sd)
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_timeout_error(self) -> None:
        """Returns None when LIDAR fetch times out (lines 471-472)."""
        import pandas as pd

        sd = MagicMock()
        sd.processed.best_lap = 1
        df = MagicMock(spec=pd.DataFrame)
        df.columns = ["lat", "lon", "lap_distance_m"]
        df.__contains__ = lambda self, key: key in self.columns
        mock_series = MagicMock()
        mock_series.to_numpy = MagicMock(return_value=np.array([33.5, 33.51]))
        df.__getitem__ = MagicMock(return_value=mock_series)
        sd.processed.resampled_laps = {1: df}

        with patch(
            "backend.api.services.pipeline.asyncio.wait_for",
            side_effect=TimeoutError("timed out"),
        ):
            result = await _try_lidar_elevation(sd)

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_general_exception(self) -> None:
        """Returns None when LIDAR fetch raises a general exception (lines 473-474)."""
        import pandas as pd

        sd = MagicMock()
        sd.processed.best_lap = 1
        df = MagicMock(spec=pd.DataFrame)
        df.columns = ["lat", "lon", "lap_distance_m"]
        df.__contains__ = lambda self, key: key in self.columns
        mock_series = MagicMock()
        mock_series.to_numpy = MagicMock(return_value=np.array([33.5, 33.51]))
        df.__getitem__ = MagicMock(return_value=mock_series)
        sd.processed.resampled_laps = {1: df}

        with patch(
            "backend.api.services.pipeline.asyncio.wait_for",
            side_effect=RuntimeError("service unavailable"),
        ):
            result = await _try_lidar_elevation(sd)

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_source_not_usgs(self) -> None:
        """Returns None when lidar result source is not usgs_3dep."""
        import pandas as pd

        sd = MagicMock()
        sd.processed.best_lap = 1
        df = MagicMock(spec=pd.DataFrame)
        df.columns = ["lat", "lon", "lap_distance_m"]
        df.__contains__ = lambda self, key: key in self.columns
        mock_series = MagicMock()
        mock_series.to_numpy = MagicMock(return_value=np.array([33.5, 33.51]))
        df.__getitem__ = MagicMock(return_value=mock_series)
        sd.processed.resampled_laps = {1: df}

        mock_result = MagicMock()
        mock_result.source = "other_source"
        mock_result.altitude_m = np.array([200.0, 201.0])

        with patch(
            "backend.api.services.pipeline.asyncio.wait_for",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await _try_lidar_elevation(sd)

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_altitude_when_usgs_source(self) -> None:
        """Returns altitude array when LIDAR fetch succeeds with usgs_3dep source."""
        import pandas as pd

        sd = MagicMock()
        sd.processed.best_lap = 1
        df = MagicMock(spec=pd.DataFrame)
        df.columns = ["lat", "lon", "lap_distance_m"]
        df.__contains__ = lambda self, key: key in self.columns
        mock_series = MagicMock()
        mock_series.to_numpy = MagicMock(return_value=np.array([33.5, 33.51]))
        df.__getitem__ = MagicMock(return_value=mock_series)
        sd.processed.resampled_laps = {1: df}

        expected_alt = np.array([200.0, 201.0, 202.0])
        mock_result = MagicMock()
        mock_result.source = "usgs_3dep"
        mock_result.altitude_m = expected_alt

        with patch(
            "backend.api.services.pipeline.asyncio.wait_for",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await _try_lidar_elevation(sd)

        assert result is not None
        np.testing.assert_array_equal(result, expected_alt)


# ===========================================================================
# _track_lidar_task done-callback paths (lines 484-494)
# ===========================================================================


class TestTrackLidarTask:
    """Tests for _track_lidar_task including the done-callback."""

    @pytest.mark.asyncio
    async def test_done_callback_discards_task_on_completion(self) -> None:
        """A completed task is discarded from _lidar_background_tasks (lines 487-492)."""
        pipeline_module._lidar_background_tasks.clear()  # noqa: SLF001

        async def _noop() -> None:
            pass

        task = asyncio.create_task(_noop())
        _track_lidar_task(task)
        await task
        # Allow event loop to run callbacks
        await asyncio.sleep(0)
        assert task not in pipeline_module._lidar_background_tasks  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_done_callback_on_task_with_exception(self) -> None:
        """A task that raises an exception triggers the warning branch (line 491-492)."""
        pipeline_module._lidar_background_tasks.clear()  # noqa: SLF001

        async def _raiser() -> None:
            raise RuntimeError("LIDAR boom")

        task = asyncio.create_task(_raiser())
        _track_lidar_task(task)

        with pytest.raises(RuntimeError):
            await task
        await asyncio.sleep(0)
        assert task not in pipeline_module._lidar_background_tasks  # noqa: SLF001


# ===========================================================================
# _lidar_prefetch_impl (lines 499-505)
# ===========================================================================


class TestLidarPrefetchImpl:
    """Tests for _lidar_prefetch_impl."""

    @pytest.mark.asyncio
    async def test_prefetch_impl_logs_when_result_available(self) -> None:
        """_lidar_prefetch_impl logs info when LIDAR returns data (lines 500-504)."""
        sd = MagicMock()
        sd.session_id = "prefetch-sess"
        alt_arr = np.array([200.0] * 50)

        with patch(
            "backend.api.services.pipeline._try_lidar_elevation",
            new_callable=AsyncMock,
            return_value=alt_arr,
        ):
            await pipeline_module._lidar_prefetch_impl(sd)

    @pytest.mark.asyncio
    async def test_prefetch_impl_no_op_when_result_none(self) -> None:
        """_lidar_prefetch_impl does nothing when LIDAR returns None."""
        sd = MagicMock()
        sd.session_id = "prefetch-sess-none"

        with patch(
            "backend.api.services.pipeline._try_lidar_elevation",
            new_callable=AsyncMock,
            return_value=None,
        ):
            await pipeline_module._lidar_prefetch_impl(sd)


# ===========================================================================
# trigger_lidar_prefetch (line 514)
# ===========================================================================


class TestTriggerLidarPrefetch:
    """Tests for trigger_lidar_prefetch."""

    @pytest.mark.asyncio
    async def test_trigger_lidar_prefetch_creates_task(self) -> None:
        """trigger_lidar_prefetch creates a background task (line 514)."""
        pipeline_module._lidar_background_tasks.clear()  # noqa: SLF001
        sd = MagicMock()
        sd.session_id = "trigger-sess"

        with patch(
            "backend.api.services.pipeline._lidar_prefetch_impl",
            new_callable=AsyncMock,
        ) as m_impl:
            pipeline_module.trigger_lidar_prefetch(sd)
            # Allow the task to run
            await asyncio.sleep(0)
            m_impl.assert_called_once_with(sd)


# ===========================================================================
# _collect_independent_calibration_telemetry
# ===========================================================================


class TestCollectIndependentCalibrationTelemetry:
    """Tests for the calibration telemetry helper."""

    def _make_sd_with_g_cols(self, coaching_laps: list[int], best_lap: int) -> MagicMock:
        import pandas as pd

        sd = MagicMock()
        sd.coaching_laps = coaching_laps
        sd.processed.best_lap = best_lap
        laps = {}
        for n in coaching_laps:
            lat_g = np.array([0.1, 0.5, -0.3, 0.8, np.nan])
            lon_g = np.array([-0.2, 0.4, 0.6, -0.5, np.nan])
            df = pd.DataFrame({"lateral_g": lat_g, "longitudinal_g": lon_g})
            laps[n] = df
        sd.processed.resampled_laps = laps
        return sd

    def test_returns_none_when_no_independent_laps(self) -> None:
        """Returns None when only the target lap exists."""
        sd = self._make_sd_with_g_cols([1], best_lap=1)
        result = _collect_independent_calibration_telemetry(sd, target_lap=1)
        assert result is None

    def test_returns_telemetry_from_other_laps(self) -> None:
        """Returns concatenated arrays from laps other than target_lap."""
        sd = self._make_sd_with_g_cols([1, 2, 3], best_lap=1)
        result = _collect_independent_calibration_telemetry(sd, target_lap=1)
        assert result is not None
        lat_g, lon_g, used_laps = result
        assert 1 not in used_laps
        assert 2 in used_laps or 3 in used_laps

    def test_returns_none_when_g_cols_missing(self) -> None:
        """Returns None when laps have no lateral_g / longitudinal_g columns."""
        import pandas as pd

        sd = MagicMock()
        sd.coaching_laps = [1, 2]
        sd.processed.best_lap = 1
        df = pd.DataFrame({"speed": [10.0, 20.0]})
        sd.processed.resampled_laps = {1: df, 2: df}
        result = _collect_independent_calibration_telemetry(sd, target_lap=1)
        assert result is None

    def test_skips_all_nan_laps(self) -> None:
        """Laps with all-NaN g-values are skipped (returns None if only such laps remain)."""
        import pandas as pd

        sd = MagicMock()
        sd.coaching_laps = [1, 2]
        sd.processed.best_lap = 1
        df2 = pd.DataFrame({"lateral_g": [np.nan, np.nan], "longitudinal_g": [np.nan, np.nan]})
        sd.processed.resampled_laps = {1: pd.DataFrame(), 2: df2}
        result = _collect_independent_calibration_telemetry(sd, target_lap=1)
        assert result is None


# ===========================================================================
# _resolve_curvature_and_elevation (lines 592-597)
# ===========================================================================


class TestResolveCurvatureAndElevation:
    """Tests for _resolve_curvature_and_elevation."""

    def _make_sd_for_curv(self, layout=None) -> MagicMock:
        import pandas as pd

        sd = MagicMock()
        sd.layout = layout
        dist = np.linspace(0, 3000, 200)
        df = pd.DataFrame({"lap_distance_m": dist})
        df["lap_distance_m"] = dist
        sd.processed.best_lap = 1
        sd.processed.resampled_laps = {1: df}
        return sd

    def test_uses_fallback_curvature_when_no_layout(self) -> None:
        """Falls back to compute_curvature when layout is None (lines 596-597)."""
        sd = self._make_sd_for_curv(layout=None)
        mock_curv_result = MagicMock()

        with patch(
            "backend.api.services.pipeline.compute_curvature",
            return_value=mock_curv_result,
        ) as m_curv:
            curv, elev = _resolve_curvature_and_elevation(sd, lidar_alt=None)

        m_curv.assert_called_once()
        assert curv is mock_curv_result
        assert elev is None

    def test_uses_fallback_curvature_with_lidar_alt(self) -> None:
        """Falls back to curvature and passes through lidar_alt when no layout."""
        sd = self._make_sd_for_curv(layout=None)
        lidar = np.array([200.0, 201.0, 202.0])
        mock_curv_result = MagicMock()

        with patch(
            "backend.api.services.pipeline.compute_curvature",
            return_value=mock_curv_result,
        ):
            curv, elev = _resolve_curvature_and_elevation(sd, lidar_alt=lidar)

        assert elev is lidar

    def test_uses_canonical_reference_when_available(self) -> None:
        """Uses canonical track reference with its elevation (lines 581-593)."""
        import pandas as pd

        layout_mock = MagicMock()
        sd = MagicMock()
        sd.layout = layout_mock
        dist = np.linspace(0, 3000, 200)
        df = pd.DataFrame({"lap_distance_m": dist})
        sd.processed.best_lap = 1
        sd.processed.resampled_laps = {1: df}

        mock_ref = MagicMock()
        mock_ref.track_slug = "test-track"
        mock_ref.n_laps_averaged = 5
        mock_ref.gps_quality_score = 90.0

        canonical_curv = MagicMock()
        canonical_elev = np.array([200.0] * 200)

        with (
            patch(
                "backend.api.services.pipeline.get_track_reference",
                return_value=mock_ref,
            ),
            patch(
                "backend.api.services.pipeline.align_reference_to_session",
                return_value=(canonical_curv, canonical_elev),
            ),
        ):
            curv, elev = _resolve_curvature_and_elevation(sd, lidar_alt=None)

        assert curv is canonical_curv
        np.testing.assert_array_equal(elev, canonical_elev)

    def test_falls_back_to_lidar_when_canonical_elev_none(self) -> None:
        """Uses lidar_alt when canonical reference has no elevation (line 593)."""
        import pandas as pd

        layout_mock = MagicMock()
        sd = MagicMock()
        sd.layout = layout_mock
        dist = np.linspace(0, 3000, 200)
        df = pd.DataFrame({"lap_distance_m": dist})
        sd.processed.best_lap = 1
        sd.processed.resampled_laps = {1: df}

        mock_ref = MagicMock()
        mock_ref.track_slug = "test-track"
        mock_ref.n_laps_averaged = 3
        mock_ref.gps_quality_score = 85.0
        canonical_curv = MagicMock()
        lidar = np.array([200.0] * 200)

        with (
            patch(
                "backend.api.services.pipeline.get_track_reference",
                return_value=mock_ref,
            ),
            patch(
                "backend.api.services.pipeline.align_reference_to_session",
                return_value=(canonical_curv, None),  # no elevation in reference
            ),
        ):
            curv, elev = _resolve_curvature_and_elevation(sd, lidar_alt=lidar)

        assert elev is lidar

    def test_falls_back_to_curvature_when_track_reference_none(self) -> None:
        """Falls back to curvature when layout is present but track reference is None."""
        import pandas as pd

        layout_mock = MagicMock()
        sd = MagicMock()
        sd.layout = layout_mock
        dist = np.linspace(0, 3000, 200)
        df = pd.DataFrame({"lap_distance_m": dist})
        sd.processed.best_lap = 1
        sd.processed.resampled_laps = {1: df}

        mock_curv = MagicMock()

        with (
            patch(
                "backend.api.services.pipeline.get_track_reference",
                return_value=None,  # no reference found
            ),
            patch(
                "backend.api.services.pipeline.compute_curvature",
                return_value=mock_curv,
            ),
        ):
            curv, elev = _resolve_curvature_and_elevation(sd, lidar_alt=None)

        assert curv is mock_curv


# ===========================================================================
# get_optimal_profile_data (lines 670, 724)
# ===========================================================================


class TestGetOptimalProfileData:
    """Tests for the async get_optimal_profile_data function."""

    def setup_method(self) -> None:
        pipeline_module._physics_cache.clear()  # noqa: SLF001
        equipment_store.clear_all_equipment()

    def _make_optimal_result(self) -> MagicMock:
        r = MagicMock()
        r.distance_m = np.array([0.0, 100.0, 200.0])
        r.optimal_speed_mps = np.array([30.0, 35.0, 32.0])
        r.max_cornering_speed_mps = np.array([28.0, 33.0, 30.0])
        r.optimal_brake_points = []
        r.optimal_throttle_points = []
        r.lap_time_s = 95.0
        r.vehicle_params.mu = 1.0
        r.vehicle_params.max_accel_g = 0.3
        r.vehicle_params.max_decel_g = 0.9
        r.vehicle_params.max_lateral_g = 1.0
        r.vehicle_params.top_speed_mps = 60.0
        r.vehicle_params.calibrated = False
        return r

    @pytest.mark.asyncio
    async def test_returns_cached_result_on_second_call(self) -> None:
        """Second call returns the cached result without recomputing."""
        sd = _make_session_data("cached-prof-sess")
        optimal = self._make_optimal_result()

        with (
            patch(
                "backend.api.services.pipeline._try_lidar_elevation",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "backend.api.services.pipeline.compute_curvature",
                return_value=MagicMock(),
            ),
            patch(
                "backend.api.services.pipeline.compute_optimal_profile",
                return_value=optimal,
            ),
            patch(
                "backend.api.services.pipeline._collect_independent_calibration_telemetry",
                return_value=None,
            ),
        ):
            result1 = await get_optimal_profile_data(sd)
            result2 = await get_optimal_profile_data(sd)

        assert result1 is result2

    @pytest.mark.asyncio
    async def test_altitude_fallback_from_gps_column(self) -> None:
        """Uses altitude_m GPS column when LIDAR is unavailable (line 670)."""
        import pandas as pd

        sd = MagicMock()
        sd.session_id = "gps-alt-sess"
        sd.layout = None

        # Build a proper DataFrame with altitude_m
        n = 100
        dist = np.linspace(0, 2000, n)
        lat_g = np.random.default_rng(0).normal(0, 0.5, n)
        lon_g = np.random.default_rng(1).normal(0, 0.3, n)
        alt = np.linspace(200, 220, n)
        df = pd.DataFrame(
            {
                "lap_distance_m": dist,
                "lat": np.full(n, 33.5),
                "lon": np.full(n, -86.6),
                "lateral_g": lat_g,
                "longitudinal_g": lon_g,
                "altitude_m": alt,
            }
        )
        sd.processed.best_lap = 1
        sd.processed.resampled_laps = {1: df, 2: df.copy()}
        sd.coaching_laps = [1, 2]
        sd.gps_quality = None

        optimal = self._make_optimal_result()

        with (
            patch(
                "backend.api.services.pipeline._try_lidar_elevation",
                new_callable=AsyncMock,
                return_value=None,  # no LIDAR
            ),
            patch(
                "backend.api.services.pipeline.compute_curvature",
                return_value=MagicMock(),
            ),
            patch(
                "backend.api.services.pipeline.compute_optimal_profile",
                return_value=optimal,
            ),
            patch(
                "backend.api.services.pipeline.compute_gradient_array",
                return_value=np.zeros(n),
            ),
            patch(
                "backend.api.services.pipeline.compute_vertical_curvature",
                return_value=np.zeros(n),
            ),
        ):
            result = await get_optimal_profile_data(sd)

        assert "distance_m" in result
        assert "optimal_speed_mph" in result
        assert "lap_time_s" in result


# ===========================================================================
# get_optimal_comparison_data (lines 724-859)
# ===========================================================================


class TestGetOptimalComparisonData:
    """Tests for the async get_optimal_comparison_data function."""

    def setup_method(self) -> None:
        pipeline_module._physics_cache.clear()  # noqa: SLF001
        equipment_store.clear_all_equipment()

    def _make_comparison_result(self, is_valid: bool = True) -> MagicMock:
        from cataclysm.optimal_comparison import CornerOpportunity

        opp = MagicMock(spec=CornerOpportunity)
        opp.corner_number = 1
        opp.actual_min_speed_mps = 20.0
        opp.optimal_min_speed_mps = 25.0
        opp.speed_gap_mph = 11.2
        opp.brake_gap_m = 15.0
        opp.time_cost_s = 0.35

        result = MagicMock()
        result.corner_opportunities = [opp]
        result.actual_lap_time_s = 92.0
        result.optimal_lap_time_s = 88.5
        result.total_gap_s = 3.5
        result.is_valid = is_valid
        result.invalid_reasons = [] if is_valid else ["gap_too_large"]
        return result

    def _make_optimal_result(self) -> MagicMock:
        r = MagicMock()
        r.distance_m = np.array([0.0, 100.0, 200.0])
        r.optimal_speed_mps = np.array([30.0, 35.0, 32.0])
        r.max_cornering_speed_mps = np.array([28.0, 33.0, 30.0])
        r.optimal_brake_points = []
        r.optimal_throttle_points = []
        r.lap_time_s = 88.5
        r.vehicle_params.mu = 1.0
        r.vehicle_params.max_accel_g = 0.3
        r.vehicle_params.max_decel_g = 0.9
        r.vehicle_params.max_lateral_g = 1.0
        r.vehicle_params.top_speed_mps = 60.0
        r.vehicle_params.calibrated = False
        return r

    @pytest.mark.asyncio
    async def test_returns_expected_keys(self) -> None:
        """get_optimal_comparison_data returns the expected dict structure."""
        sd = _make_session_data("comp-sess-1")
        comparison = self._make_comparison_result()
        optimal = self._make_optimal_result()

        with (
            patch(
                "backend.api.services.pipeline._try_lidar_elevation",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "backend.api.services.pipeline.compute_curvature",
                return_value=MagicMock(),
            ),
            patch(
                "backend.api.services.pipeline.compute_optimal_profile",
                return_value=optimal,
            ),
            patch(
                "backend.api.services.pipeline.compare_with_optimal",
                return_value=comparison,
            ),
            patch(
                "backend.api.services.pipeline._collect_independent_calibration_telemetry",
                return_value=None,
            ),
        ):
            result = await get_optimal_comparison_data(sd)

        assert "corner_opportunities" in result
        assert "actual_lap_time_s" in result
        assert "optimal_lap_time_s" in result
        assert "total_gap_s" in result
        assert "is_valid" in result
        assert "invalid_reasons" in result

    @pytest.mark.asyncio
    async def test_returns_cached_result_on_second_call(self) -> None:
        """Second call returns cached comparison data."""
        sd = _make_session_data("comp-cached-sess")
        comparison = self._make_comparison_result()
        optimal = self._make_optimal_result()

        with (
            patch(
                "backend.api.services.pipeline._try_lidar_elevation",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "backend.api.services.pipeline.compute_curvature",
                return_value=MagicMock(),
            ),
            patch(
                "backend.api.services.pipeline.compute_optimal_profile",
                return_value=optimal,
            ),
            patch(
                "backend.api.services.pipeline.compare_with_optimal",
                return_value=comparison,
            ),
            patch(
                "backend.api.services.pipeline._collect_independent_calibration_telemetry",
                return_value=None,
            ),
        ):
            result1 = await get_optimal_comparison_data(sd)
            result2 = await get_optimal_comparison_data(sd)

        assert result1 is result2

    @pytest.mark.asyncio
    async def test_invalid_comparison_included_in_result(self) -> None:
        """An invalid comparison still returns data with is_valid=False."""
        sd = _make_session_data("comp-invalid-sess")
        comparison = self._make_comparison_result(is_valid=False)
        optimal = self._make_optimal_result()

        with (
            patch(
                "backend.api.services.pipeline._try_lidar_elevation",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "backend.api.services.pipeline.compute_curvature",
                return_value=MagicMock(),
            ),
            patch(
                "backend.api.services.pipeline.compute_optimal_profile",
                return_value=optimal,
            ),
            patch(
                "backend.api.services.pipeline.compare_with_optimal",
                return_value=comparison,
            ),
            patch(
                "backend.api.services.pipeline._collect_independent_calibration_telemetry",
                return_value=None,
            ),
        ):
            result = await get_optimal_comparison_data(sd)

        assert result["is_valid"] is False
        assert result["invalid_reasons"] == ["gap_too_large"]

    @pytest.mark.asyncio
    async def test_grip_calibration_applied_when_no_equipment(self) -> None:
        """Grip calibration is applied when no meaningful equipment grip is available."""
        sd = _make_session_data("comp-calib-sess")
        comparison = self._make_comparison_result()
        optimal = self._make_optimal_result()

        # Provide fake calibration data
        lat_g = np.random.default_rng(42).normal(0, 0.8, 100)
        lon_g = np.random.default_rng(43).normal(0, 0.5, 100)
        mock_grip = MagicMock()
        mock_grip.max_lateral_g = 1.1
        mock_grip.max_brake_g = 1.0
        mock_grip.max_accel_g = 0.4
        mock_grip.confidence = "high"

        with (
            patch(
                "backend.api.services.pipeline._try_lidar_elevation",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "backend.api.services.pipeline.compute_curvature",
                return_value=MagicMock(),
            ),
            patch(
                "backend.api.services.pipeline.compute_optimal_profile",
                return_value=optimal,
            ),
            patch(
                "backend.api.services.pipeline.compare_with_optimal",
                return_value=comparison,
            ),
            patch(
                "backend.api.services.pipeline._collect_independent_calibration_telemetry",
                return_value=(lat_g, lon_g, [2, 3]),
            ),
            patch(
                "backend.api.services.pipeline.calibrate_grip_from_telemetry",
                return_value=mock_grip,
            ),
            patch(
                "backend.api.services.pipeline.apply_calibration_to_params",
                return_value=MagicMock(),
            ),
        ):
            result = await get_optimal_comparison_data(sd)

        assert "corner_opportunities" in result

    @pytest.mark.asyncio
    async def test_brake_gap_none_is_preserved(self) -> None:
        """A corner with brake_gap_m=None is serialised as None in the result."""
        sd = _make_session_data("comp-brake-none-sess")
        optimal = self._make_optimal_result()

        opp = MagicMock()
        opp.corner_number = 2
        opp.actual_min_speed_mps = 18.0
        opp.optimal_min_speed_mps = 22.0
        opp.speed_gap_mph = 8.9
        opp.brake_gap_m = None  # no brake gap
        opp.time_cost_s = 0.25

        comparison = MagicMock()
        comparison.corner_opportunities = [opp]
        comparison.actual_lap_time_s = 94.0
        comparison.optimal_lap_time_s = 90.0
        comparison.total_gap_s = 4.0
        comparison.is_valid = True
        comparison.invalid_reasons = []

        with (
            patch(
                "backend.api.services.pipeline._try_lidar_elevation",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "backend.api.services.pipeline.compute_curvature",
                return_value=MagicMock(),
            ),
            patch(
                "backend.api.services.pipeline.compute_optimal_profile",
                return_value=optimal,
            ),
            patch(
                "backend.api.services.pipeline.compare_with_optimal",
                return_value=comparison,
            ),
            patch(
                "backend.api.services.pipeline._collect_independent_calibration_telemetry",
                return_value=None,
            ),
        ):
            result = await get_optimal_comparison_data(sd)

        assert result["corner_opportunities"][0]["brake_gap_m"] is None

    @pytest.mark.asyncio
    async def test_elevation_used_in_comparison_when_altitude_col_present(self) -> None:
        """get_optimal_comparison_data uses altitude_m column when LIDAR unavailable."""
        import pandas as pd

        sd = MagicMock()
        sd.session_id = "comp-alt-sess"
        sd.layout = None
        sd.corners = []
        sd.coaching_laps = [1, 2]

        n = 80
        dist = np.linspace(0, 2000, n)
        alt = np.linspace(200, 215, n)
        df = pd.DataFrame(
            {
                "lap_distance_m": dist,
                "lat": np.full(n, 33.5),
                "lon": np.full(n, -86.6),
                "lateral_g": np.random.default_rng(10).normal(0, 0.5, n),
                "longitudinal_g": np.random.default_rng(11).normal(0, 0.3, n),
                "altitude_m": alt,
            }
        )
        sd.processed.best_lap = 1
        sd.processed.resampled_laps = {1: df, 2: df.copy()}

        comparison = self._make_comparison_result()
        optimal = self._make_optimal_result()

        with (
            patch(
                "backend.api.services.pipeline._try_lidar_elevation",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "backend.api.services.pipeline.compute_curvature",
                return_value=MagicMock(),
            ),
            patch(
                "backend.api.services.pipeline.compute_optimal_profile",
                return_value=optimal,
            ),
            patch(
                "backend.api.services.pipeline.compare_with_optimal",
                return_value=comparison,
            ),
            patch(
                "backend.api.services.pipeline.compute_gradient_array",
                return_value=np.zeros(n),
            ),
            patch(
                "backend.api.services.pipeline.compute_vertical_curvature",
                return_value=np.zeros(n),
            ),
        ):
            result = await get_optimal_comparison_data(sd)

        assert "actual_lap_time_s" in result


# ===========================================================================
# enrich_corners_with_elevation (line 231) — truthy elev path
# ===========================================================================


class TestEnrichCornersWithElevation:
    """enrich_corners_with_elevation called when compute_corner_elevation returns truthy."""

    def test_enrich_called_when_elevation_truthy(self) -> None:
        """Line 231: enrich_corners_with_elevation is called when elev is truthy."""
        with (
            patch("backend.api.services.pipeline.parse_racechrono_csv") as m_parse,
            patch("backend.api.services.pipeline.process_session") as m_process,
            patch("backend.api.services.pipeline.find_anomalous_laps") as m_anom,
            patch("backend.api.services.pipeline.detect_track_or_lookup") as m_track,
            patch("backend.api.services.pipeline.locate_official_corners"),
            patch("backend.api.services.pipeline.extract_corner_kpis_for_lap") as m_extract,
            patch("backend.api.services.pipeline.detect_corners") as m_detect,
            patch("backend.api.services.pipeline.compute_corner_elevation") as m_elev,
            patch("backend.api.services.pipeline.enrich_corners_with_elevation") as m_enrich,
            patch("backend.api.services.pipeline.assess_gps_quality") as m_gps,
            patch("backend.api.services.pipeline.compute_session_consistency") as m_consist,
            patch("backend.api.services.pipeline.estimate_gains") as m_gains,
            patch("backend.api.services.pipeline.estimate_grip_limit") as m_grip,
            patch("backend.api.services.pipeline.build_session_snapshot") as m_snap,
            patch("backend.api.services.pipeline._fallback_lap_consistency") as m_fallback,
            patch("backend.api.services.pipeline.should_enable_line_analysis") as m_line_ok,
            patch("backend.api.services.pipeline.analyze_corner_lines") as m_corner_lines,
            patch("backend.api.services.pipeline.maybe_update_track_reference"),
        ):
            parsed = _make_parsed()
            processed = _make_processed(n_laps=3)
            snap = _make_snapshot()
            m_parse.return_value = parsed
            m_process.return_value = processed
            m_anom.return_value = set()
            m_track.return_value = None
            m_detect.return_value = [MagicMock()]
            m_extract.return_value = []
            # Return a truthy elev dict so enrich_corners_with_elevation is called
            m_elev.return_value = {1: MagicMock()}
            m_gps.return_value = MagicMock(overall_score=95.0, grade="A")
            m_consist.return_value = MagicMock(lap_consistency=MagicMock(), corner_consistency=[])
            m_gains.return_value = MagicMock()
            m_grip.return_value = MagicMock()
            m_snap.return_value = snap
            m_fallback.return_value = MagicMock()
            m_line_ok.return_value = False
            m_corner_lines.return_value = []

            pipeline_module._run_pipeline_sync(b"fake_csv", "test.csv")  # noqa: SLF001

        m_enrich.assert_called_once()


# ===========================================================================
# corner line analysis success path — logger.info (line 240)
# ===========================================================================


class TestCornerLineAnalysisSuccessPath:
    """analyze_corner_lines success path exercises the logger.info (line 240)."""

    def test_corner_line_profiles_populated_on_success(self) -> None:
        """Lines 239-244: analyze_corner_lines returns profiles, logger.info called."""
        with (
            patch("backend.api.services.pipeline.parse_racechrono_csv") as m_parse,
            patch("backend.api.services.pipeline.process_session") as m_process,
            patch("backend.api.services.pipeline.find_anomalous_laps") as m_anom,
            patch("backend.api.services.pipeline.detect_track_or_lookup") as m_track,
            patch("backend.api.services.pipeline.locate_official_corners"),
            patch("backend.api.services.pipeline.extract_corner_kpis_for_lap") as m_extract,
            patch("backend.api.services.pipeline.detect_corners") as m_detect,
            patch("backend.api.services.pipeline.compute_corner_elevation") as m_elev,
            patch("backend.api.services.pipeline.enrich_corners_with_elevation"),
            patch("backend.api.services.pipeline.assess_gps_quality") as m_gps,
            patch("backend.api.services.pipeline.compute_session_consistency") as m_consist,
            patch("backend.api.services.pipeline.estimate_gains") as m_gains,
            patch("backend.api.services.pipeline.estimate_grip_limit") as m_grip,
            patch("backend.api.services.pipeline.build_session_snapshot") as m_snap,
            patch("backend.api.services.pipeline._fallback_lap_consistency") as m_fallback,
            patch("backend.api.services.pipeline.should_enable_line_analysis") as m_line_ok,
            patch("backend.api.services.pipeline.build_gps_trace") as m_trace,
            patch("backend.api.services.pipeline.compute_reference_centerline"),
            patch("backend.api.services.pipeline.analyze_corner_lines") as m_corner_lines,
            patch("backend.api.services.pipeline.maybe_update_track_reference"),
        ):
            parsed = _make_parsed()
            processed = _make_processed(n_laps=4)
            snap = _make_snapshot()
            m_parse.return_value = parsed
            m_process.return_value = processed
            m_anom.return_value = set()
            m_track.return_value = None
            m_detect.return_value = [MagicMock()]
            m_extract.return_value = []
            m_elev.return_value = {}
            m_gps.return_value = MagicMock(overall_score=95.0, grade="A")
            m_consist.return_value = MagicMock(lap_consistency=MagicMock(), corner_consistency=[])
            m_gains.return_value = MagicMock()
            m_grip.return_value = MagicMock()
            m_snap.return_value = snap
            m_fallback.return_value = MagicMock()
            m_line_ok.return_value = True
            m_trace.return_value = MagicMock()
            # analyze_corner_lines returns a non-empty list (success path)
            profile_mock = MagicMock()
            m_corner_lines.return_value = [profile_mock, profile_mock]

            result = pipeline_module._run_pipeline_sync(b"fake_csv", "test.csv")  # noqa: SLF001

        assert len(result.corner_line_profiles) == 2


# ===========================================================================
# _fallback_lap_consistency (lines 341-343)
# ===========================================================================


class TestFallbackLapConsistency:
    """_fallback_lap_consistency calls compute_lap_consistency (lines 341-343)."""

    def test_fallback_calls_compute_lap_consistency(self) -> None:
        """The fallback function delegates to compute_lap_consistency."""
        from backend.api.services.pipeline import _fallback_lap_consistency

        mock_summaries = [MagicMock()]
        mock_anomalous: set[int] = {2}
        mock_result = MagicMock()

        # compute_lap_consistency is imported *inside* _fallback_lap_consistency's body:
        #   from cataclysm.consistency import compute_lap_consistency
        # So the attribute lives in cataclysm.consistency, not in the pipeline module.
        with patch(
            "cataclysm.consistency.compute_lap_consistency",
            return_value=mock_result,
        ) as m_clc:
            result = _fallback_lap_consistency(mock_summaries, mock_anomalous)

        m_clc.assert_called_once_with(mock_summaries, mock_anomalous)
        assert result is mock_result


# ===========================================================================
# compute_session_id_from_csv (lines 352-358)
# ===========================================================================


class TestComputeSessionIdFromCsv:
    """compute_session_id_from_csv parses CSV header and returns a deterministic ID."""

    def test_returns_string_session_id(self) -> None:
        """Lines 352-358: decodes bytes, parses metadata, computes ID."""
        from backend.api.services.pipeline import compute_session_id_from_csv
        from backend.tests.conftest import build_synthetic_csv

        csv_bytes = build_synthetic_csv(track_name="Barber Motorsports Park", n_laps=2)
        session_id = compute_session_id_from_csv(csv_bytes, "barber_session.csv")

        assert isinstance(session_id, str)
        assert len(session_id) > 0

    def test_same_csv_returns_same_id(self) -> None:
        """Same input always produces the same deterministic session ID."""
        from backend.api.services.pipeline import compute_session_id_from_csv
        from backend.tests.conftest import build_synthetic_csv

        csv_bytes = build_synthetic_csv(track_name="Road Atlanta", n_laps=3)
        id1 = compute_session_id_from_csv(csv_bytes, "road_atlanta.csv")
        id2 = compute_session_id_from_csv(csv_bytes, "road_atlanta.csv")

        assert id1 == id2


# ===========================================================================
# _track_lidar_task — cancelled task path (line 496)
# ===========================================================================


class TestTrackLidarTaskCancelled:
    """_on_done returns early when task was cancelled (line 496)."""

    @pytest.mark.asyncio
    async def test_cancelled_task_handled_silently(self) -> None:
        """Line 496: if t.cancelled() is True, _on_done returns without calling t.exception()."""
        pipeline_module._lidar_background_tasks.clear()  # noqa: SLF001

        async def _long_running() -> None:
            await asyncio.sleep(10)

        task = asyncio.create_task(_long_running())
        _track_lidar_task(task)
        # Cancel immediately
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        await asyncio.sleep(0)
        # Task should be discarded from tracking set without raising
        assert task not in pipeline_module._lidar_background_tasks  # noqa: SLF001


# ===========================================================================
# get_optimal_profile_data — grip calibration applied (lines 656-658)
# ===========================================================================


class TestGetOptimalProfileDataGripCalibration:
    """Grip calibration path in get_optimal_profile_data (lines 656-658)."""

    def setup_method(self) -> None:
        pipeline_module._physics_cache.clear()  # noqa: SLF001
        equipment_store.clear_all_equipment()

    def _make_optimal_result(self) -> MagicMock:
        r = MagicMock()
        r.distance_m = np.array([0.0, 100.0])
        r.optimal_speed_mps = np.array([30.0, 35.0])
        r.max_cornering_speed_mps = np.array([28.0, 33.0])
        r.optimal_brake_points = []
        r.optimal_throttle_points = []
        r.lap_time_s = 92.0
        r.vehicle_params.mu = 1.1
        r.vehicle_params.max_accel_g = 0.35
        r.vehicle_params.max_decel_g = 0.95
        r.vehicle_params.max_lateral_g = 1.1
        r.vehicle_params.top_speed_mps = 58.0
        r.vehicle_params.calibrated = True
        return r

    @pytest.mark.asyncio
    async def test_grip_calibration_applied_updates_vehicle_params(self) -> None:
        """Lines 656-658: calibrate_grip_from_telemetry result is applied to params."""
        sd = _make_session_data("prof-calib-grip-sess")
        optimal = self._make_optimal_result()

        lat_g = np.random.default_rng(5).normal(0, 0.9, 100)
        lon_g = np.random.default_rng(6).normal(0, 0.6, 100)
        mock_grip = MagicMock()
        mock_grip.max_lateral_g = 1.15
        mock_grip.max_brake_g = 1.05
        mock_grip.max_accel_g = 0.42
        mock_grip.confidence = "medium"

        with (
            patch(
                "backend.api.services.pipeline._try_lidar_elevation",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "backend.api.services.pipeline.compute_curvature",
                return_value=MagicMock(),
            ),
            patch(
                "backend.api.services.pipeline.compute_optimal_profile",
                return_value=optimal,
            ),
            patch(
                "backend.api.services.pipeline._collect_independent_calibration_telemetry",
                return_value=(lat_g, lon_g, [2, 3]),
            ),
            patch(
                "backend.api.services.pipeline.calibrate_grip_from_telemetry",
                return_value=mock_grip,
            ),
            patch(
                "backend.api.services.pipeline.apply_calibration_to_params",
                return_value=MagicMock(),
            ) as m_apply,
        ):
            result = await get_optimal_profile_data(sd)

        m_apply.assert_called_once()
        assert "distance_m" in result


# ===========================================================================
# get_ideal_lap_data
# ===========================================================================


class TestGetIdealLapData:
    """Tests for get_ideal_lap_data."""

    @pytest.mark.asyncio
    async def test_returns_expected_keys(self) -> None:
        """get_ideal_lap_data returns distance_m, speed_mph, segment_sources."""
        import pandas as pd

        sd = MagicMock()
        n = 50
        dist = np.linspace(0, 2000, n)
        df = pd.DataFrame({"lap_distance_m": dist})
        sd.processed.best_lap = 1
        sd.processed.resampled_laps = {1: df}
        sd.corners = []
        sd.coaching_laps = [1, 2]

        ideal_mock = MagicMock()
        ideal_mock.distance_m = np.array([0.0, 100.0])
        ideal_mock.speed_mps = np.array([30.0, 35.0])
        ideal_mock.segment_sources = ["lap_1", "lap_1"]

        with (
            patch(
                "backend.api.services.pipeline.build_segments",
                return_value=[],
            ),
            patch(
                "backend.api.services.pipeline.compute_segment_times",
                return_value={},
            ),
            patch(
                "backend.api.services.pipeline.reconstruct_ideal_lap",
                return_value=ideal_mock,
            ),
        ):
            result = await get_ideal_lap_data(sd)

        assert "distance_m" in result
        assert "speed_mph" in result
        assert "segment_sources" in result
