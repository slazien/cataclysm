"""Tests for backend.api.services.pipeline — error path coverage.

Targets the uncovered error-handling branches in _run_pipeline_sync:
- Lines 68-69: assess_gps_quality raises → gps_quality stays None
- Line 78: detect_track_or_lookup returns None → detect_corners fallback
- Lines 94-95: compute_corner_elevation raises → graceful skip
- Lines 108-109: compute_session_consistency raises → consistency stays None
- Lines 122-123: estimate_gains raises → gains stays None
- Lines 130-131: estimate_grip_limit raises → grip stays None
- Line 248: resolve_vehicle_params when profile is missing

All tests mock the heavy cataclysm functions so the suite stays fast.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from backend.api.services import equipment_store
from backend.api.services import pipeline as pipeline_module
from backend.api.services.pipeline import resolve_vehicle_params
from backend.api.services.session_store import SessionData

# ---------------------------------------------------------------------------
# Helpers — build minimal mocks that satisfy _run_pipeline_sync's interface
# ---------------------------------------------------------------------------


def _make_mock_lap_df() -> MagicMock:
    import pandas as pd

    df = MagicMock(spec=pd.DataFrame)
    df.__getitem__ = MagicMock(return_value=MagicMock())
    df.iloc = MagicMock()
    return df


def _make_processed(best_lap: int = 1, n_laps: int = 3) -> MagicMock:
    """Return a minimal ProcessedSession-like mock."""
    lap_df = _make_mock_lap_df()
    processed = MagicMock()
    processed.best_lap = best_lap
    processed.resampled_laps = {i: lap_df for i in range(1, n_laps + 1)}
    processed.lap_summaries = [MagicMock() for _ in range(n_laps)]
    return processed


def _make_parsed() -> MagicMock:
    import pandas as pd

    parsed = MagicMock()
    parsed.metadata.track_name = "Test Circuit"
    parsed.metadata.session_date = "22/02/2026"
    parsed.data = pd.DataFrame({"lat": [33.53], "lon": [-86.62], "speed": [30.0]})
    return parsed


def _make_snapshot() -> MagicMock:
    snap = MagicMock()
    snap.session_id = "snap-sess-1"
    snap.metadata.track_name = "Test Circuit"
    snap.metadata.session_date = "22/02/2026"
    snap.n_laps = 3
    snap.n_clean_laps = 2
    snap.best_lap_time_s = 90.5
    snap.top3_avg_time_s = 92.0
    snap.avg_lap_time_s = 93.0
    snap.consistency_score = 85.0
    snap.session_date_parsed = MagicMock()
    return snap


def _make_session_data_mock(session_id: str = "snap-sess-1") -> MagicMock:
    """SessionData mock with the attributes pipeline returns."""
    sd = MagicMock()
    sd.session_id = session_id
    sd.snapshot = _make_snapshot()
    sd.snapshot.session_id = session_id
    return sd


# Core patches always needed when running _run_pipeline_sync
_ALWAYS_PATCHES = {
    "backend.api.services.pipeline.parse_racechrono_csv": None,
    "backend.api.services.pipeline.process_session": None,
    "backend.api.services.pipeline.find_anomalous_laps": None,
    "backend.api.services.pipeline.detect_track_or_lookup": None,
    "backend.api.services.pipeline.locate_official_corners": None,
    "backend.api.services.pipeline.extract_corner_kpis_for_lap": None,
    "backend.api.services.pipeline.detect_corners": None,
    "backend.api.services.pipeline.compute_corner_elevation": None,
    "backend.api.services.pipeline.enrich_corners_with_elevation": None,
    "backend.api.services.pipeline.assess_gps_quality": None,
    "backend.api.services.pipeline.compute_session_consistency": None,
    "backend.api.services.pipeline.estimate_gains": None,
    "backend.api.services.pipeline.estimate_grip_limit": None,
    "backend.api.services.pipeline.build_session_snapshot": None,
    "backend.api.services.pipeline.store_session": None,
}


def _apply_base_mocks(
    mocks: dict[str, MagicMock], parsed: MagicMock, processed: MagicMock, snap: MagicMock
) -> None:  # noqa: E501
    """Wire base pipeline function mocks to sensible return values."""
    mocks["parse_racechrono_csv"].return_value = parsed
    mocks["process_session"].return_value = processed
    mocks["find_anomalous_laps"].return_value = set()
    mocks["detect_track_or_lookup"].return_value = None  # fallback path
    mocks["detect_corners"].return_value = []
    mocks["extract_corner_kpis_for_lap"].return_value = []
    mocks["compute_corner_elevation"].return_value = {}
    mocks["assess_gps_quality"].return_value = MagicMock(overall_score=95.0, grade="A")
    mocks["compute_session_consistency"].return_value = MagicMock(
        lap_consistency=MagicMock(), corner_consistency=[]
    )
    mocks["estimate_gains"].return_value = MagicMock()
    mocks["estimate_grip_limit"].return_value = MagicMock()
    mocks["build_session_snapshot"].return_value = snap


# ---------------------------------------------------------------------------
# Error-path tests
# ---------------------------------------------------------------------------


class TestRunPipelineSyncErrorPaths:
    """Each test injects a failure into one pipeline stage and checks recovery."""

    def _run_with_patches(
        self, extra_setup: object = None
    ) -> tuple[SessionData, dict[str, MagicMock]]:
        """Run _run_pipeline_sync under full patch, returning all mocks.

        Also patches _fallback_lap_consistency to avoid needing real LapSummary objects
        with comparable lap_number attributes when compute_session_consistency is mocked.
        """
        parsed = _make_parsed()
        processed = _make_processed(n_laps=3)
        snap = _make_snapshot()

        with (
            patch("backend.api.services.pipeline.parse_racechrono_csv") as m_parse,
            patch("backend.api.services.pipeline.process_session") as m_process,
            patch("backend.api.services.pipeline.find_anomalous_laps") as m_anom,
            patch("backend.api.services.pipeline.detect_track_or_lookup") as m_track,
            patch("backend.api.services.pipeline.locate_official_corners") as m_corners_official,
            patch("backend.api.services.pipeline.extract_corner_kpis_for_lap") as m_extract,
            patch("backend.api.services.pipeline.detect_corners") as m_detect_corners,
            patch("backend.api.services.pipeline.compute_corner_elevation") as m_elev,
            patch("backend.api.services.pipeline.enrich_corners_with_elevation") as m_enrich,
            patch("backend.api.services.pipeline.assess_gps_quality") as m_gps,
            patch("backend.api.services.pipeline.compute_session_consistency") as m_consist,
            patch("backend.api.services.pipeline.estimate_gains") as m_gains,
            patch("backend.api.services.pipeline.estimate_grip_limit") as m_grip,
            patch("backend.api.services.pipeline.build_session_snapshot") as m_snap,
            patch("backend.api.services.pipeline._fallback_lap_consistency") as m_fallback,
            patch("backend.api.services.pipeline.get_corner_override_sync", return_value=None) as m_corner_override,
            patch("backend.api.services.pipeline.track_slug_from_layout", return_value="test-track") as m_slug,
        ):
            mocks = {
                "parse_racechrono_csv": m_parse,
                "process_session": m_process,
                "find_anomalous_laps": m_anom,
                "detect_track_or_lookup": m_track,
                "locate_official_corners": m_corners_official,
                "extract_corner_kpis_for_lap": m_extract,
                "detect_corners": m_detect_corners,
                "compute_corner_elevation": m_elev,
                "enrich_corners_with_elevation": m_enrich,
                "assess_gps_quality": m_gps,
                "compute_session_consistency": m_consist,
                "estimate_gains": m_gains,
                "estimate_grip_limit": m_grip,
                "build_session_snapshot": m_snap,
                "_fallback_lap_consistency": m_fallback,
                "get_corner_override_sync": m_corner_override,
                "track_slug_from_layout": m_slug,
            }
            m_fallback.return_value = MagicMock()
            _apply_base_mocks(mocks, parsed, processed, snap)
            if callable(extra_setup):
                extra_setup(mocks)

            result = pipeline_module._run_pipeline_sync(b"fake_csv", "test.csv")  # noqa: SLF001
            return result, mocks  # type: ignore[return-value]

    def test_gps_quality_failure_sets_none(self) -> None:
        """When assess_gps_quality raises ValueError, gps_quality is None in result."""

        def _setup(mocks: dict[str, MagicMock]) -> None:
            mocks["assess_gps_quality"].side_effect = ValueError("GPS column missing")

        result, _ = self._run_with_patches(_setup)
        assert result.gps_quality is None

    def test_gps_quality_keyerror_handled(self) -> None:
        """KeyError from assess_gps_quality is also caught."""

        def _setup(mocks: dict[str, MagicMock]) -> None:
            mocks["assess_gps_quality"].side_effect = KeyError("lat")

        result, _ = self._run_with_patches(_setup)
        assert result.gps_quality is None

    def test_gps_quality_uses_raw_parsed_data_when_available(self) -> None:
        """GPS quality should receive raw parsed telemetry, not filtered session data."""

        def _setup(mocks: dict[str, MagicMock]) -> None:
            raw_df = MagicMock(name="raw_df")
            filtered_df = MagicMock(name="filtered_df")
            parsed = mocks["parse_racechrono_csv"].return_value
            parsed.raw_data = raw_df
            parsed.data = filtered_df

        _, mocks = self._run_with_patches(_setup)
        assert (
            mocks["assess_gps_quality"].call_args.args[0]
            is mocks["parse_racechrono_csv"].return_value.raw_data
        )

    def test_detect_corners_fallback_when_no_track_layout(self) -> None:
        """detect_corners is called when detect_track_or_lookup returns None."""

        def _setup(mocks: dict[str, MagicMock]) -> None:
            mocks["detect_track_or_lookup"].return_value = None

        result, mocks = self._run_with_patches(_setup)
        mocks["detect_corners"].assert_called_once()
        mocks["locate_official_corners"].assert_not_called()

    def test_official_corners_used_when_track_layout_found(self) -> None:
        """When detect_track_or_lookup returns a layout, official corners are used."""

        def _setup(mocks: dict[str, MagicMock]) -> None:
            mocks["detect_track_or_lookup"].return_value = MagicMock()
            mocks["locate_official_corners"].return_value = []

        result, mocks = self._run_with_patches(_setup)
        mocks["locate_official_corners"].assert_called_once()
        mocks["detect_corners"].assert_not_called()

    def test_elevation_failure_is_swallowed(self) -> None:
        """ValueError from compute_corner_elevation does not propagate."""

        def _setup(mocks: dict[str, MagicMock]) -> None:
            mocks["compute_corner_elevation"].side_effect = ValueError("no elevation data")

        result, mocks = self._run_with_patches(_setup)
        # Pipeline should still complete normally
        assert result is not None
        mocks["enrich_corners_with_elevation"].assert_not_called()

    def test_elevation_keyerror_is_swallowed(self) -> None:
        """KeyError from compute_corner_elevation is swallowed."""

        def _setup(mocks: dict[str, MagicMock]) -> None:
            mocks["compute_corner_elevation"].side_effect = KeyError("distance_m")

        result, _ = self._run_with_patches(_setup)
        assert result is not None

    def test_consistency_failure_sets_none(self) -> None:
        """ValueError from compute_session_consistency sets consistency to None."""

        def _setup(mocks: dict[str, MagicMock]) -> None:
            mocks["compute_session_consistency"].side_effect = ValueError("bad laps")

        result, _ = self._run_with_patches(_setup)
        assert result.consistency is None

    def test_consistency_keyerror_sets_none(self) -> None:
        """KeyError from compute_session_consistency is caught."""

        def _setup(mocks: dict[str, MagicMock]) -> None:
            mocks["compute_session_consistency"].side_effect = KeyError("corner_idx")

        result, _ = self._run_with_patches(_setup)
        assert result.consistency is None

    def test_gains_failure_sets_none(self) -> None:
        """ValueError from estimate_gains sets gains to None."""

        def _setup(mocks: dict[str, MagicMock]) -> None:
            mocks["estimate_gains"].side_effect = ValueError("not enough laps")

        result, _ = self._run_with_patches(_setup)
        assert result.gains is None

    def test_gains_indexerror_sets_none(self) -> None:
        """IndexError from estimate_gains is caught."""

        def _setup(mocks: dict[str, MagicMock]) -> None:
            mocks["estimate_gains"].side_effect = IndexError("out of range")

        result, _ = self._run_with_patches(_setup)
        assert result.gains is None

    def test_grip_failure_sets_none(self) -> None:
        """ValueError from estimate_grip_limit sets grip to None."""

        def _setup(mocks: dict[str, MagicMock]) -> None:
            mocks["estimate_grip_limit"].side_effect = ValueError("too few points")

        result, _ = self._run_with_patches(_setup)
        assert result.grip is None

    def test_grip_keyerror_sets_none(self) -> None:
        """KeyError from estimate_grip_limit is caught."""

        def _setup(mocks: dict[str, MagicMock]) -> None:
            mocks["estimate_grip_limit"].side_effect = KeyError("lateral_acc")

        result, _ = self._run_with_patches(_setup)
        assert result.grip is None

    def test_all_errors_fire_simultaneously_still_returns_session_data(self) -> None:
        """Multiple simultaneous failures still produce a complete SessionData."""

        def _setup(mocks: dict[str, MagicMock]) -> None:
            mocks["assess_gps_quality"].side_effect = ValueError("GPS down")
            mocks["compute_corner_elevation"].side_effect = ValueError("no DEM")
            mocks["compute_session_consistency"].side_effect = ValueError("unstable")
            mocks["estimate_gains"].side_effect = ValueError("no gains")
            mocks["estimate_grip_limit"].side_effect = ValueError("no grip")

        result, _ = self._run_with_patches(_setup)
        assert result is not None
        assert result.gps_quality is None
        assert result.consistency is None
        assert result.gains is None
        assert result.grip is None


# ---------------------------------------------------------------------------
# resolve_vehicle_params
# ---------------------------------------------------------------------------


class TestResolveVehicleParams:
    """Tests for resolve_vehicle_params — the uncovered line 248 branch."""

    def setup_method(self) -> None:
        equipment_store.clear_all_equipment()

    def test_returns_none_when_no_session_equipment(self) -> None:
        """When no equipment is assigned to the session, returns None."""
        result = resolve_vehicle_params("no-equipment-session")
        assert result is None

    def test_returns_none_when_profile_missing(self) -> None:
        """When session equipment references a non-existent profile, returns None.

        This is line 248 — the second early-return path in resolve_vehicle_params.
        """
        from cataclysm.equipment import SessionEquipment

        se = SessionEquipment(
            session_id="sess-orphan",
            profile_id="ghost-profile-id",
            overrides={},
            conditions=None,
        )
        equipment_store.store_session_equipment(se)

        result = resolve_vehicle_params("sess-orphan")
        assert result is None

    def test_returns_vehicle_params_when_equipment_complete(self) -> None:
        """Returns VehicleParams when session equipment and profile are both present."""
        from cataclysm.equipment import (
            EquipmentProfile,
            MuSource,
            SessionEquipment,
            TireCompoundCategory,
            TireSpec,
        )

        tire = TireSpec(
            model="Pilot Sport 4S",
            compound_category=TireCompoundCategory.SUPER_200TW,
            size="255/35ZR18",
            treadwear_rating=300,
            estimated_mu=1.10,
            mu_source=MuSource.FORMULA_ESTIMATE,
            mu_confidence="medium",
            pressure_psi=34.0,
            brand="Michelin",
            age_sessions=5,
        )
        profile = EquipmentProfile(
            id="vp-prof",
            name="Velocity Profile Setup",
            tires=tire,
            brakes=None,
            suspension=None,
            notes=None,
        )
        se = SessionEquipment(
            session_id="sess-with-equip",
            profile_id="vp-prof",
            overrides={},
            conditions=None,
        )
        equipment_store.store_profile(profile)
        equipment_store.store_session_equipment(se)

        result = resolve_vehicle_params("sess-with-equip")
        assert result is not None


# ---------------------------------------------------------------------------
# process_upload (async wrapper)
# ---------------------------------------------------------------------------


class TestProcessUpload:
    """Tests for the async process_upload wrapper."""

    @pytest.mark.asyncio
    async def test_process_upload_returns_session_metadata(self) -> None:
        """process_upload returns the expected dict keys."""
        snap = _make_snapshot()
        sd = _make_session_data_mock()
        sd.snapshot = snap

        with (
            patch(
                "backend.api.services.pipeline._run_pipeline_sync",
                return_value=sd,
            ),
            patch("backend.api.services.pipeline.store_session"),
        ):
            result = await pipeline_module.process_upload(b"csv", "session.csv")

        assert "session_id" in result
        assert "track_name" in result
        assert "n_laps" in result
        assert "best_lap_time_s" in result

    @pytest.mark.asyncio
    async def test_process_file_path_delegates_to_process_upload(self) -> None:
        """process_file_path reads bytes then calls process_upload."""
        import tempfile
        from pathlib import Path

        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            f.write(b"fake csv content")
            tmp_path = f.name

        snap = _make_snapshot()
        sd = _make_session_data_mock()
        sd.snapshot = snap

        try:
            with (
                patch(
                    "backend.api.services.pipeline._run_pipeline_sync",
                    return_value=sd,
                ),
                patch("backend.api.services.pipeline.store_session"),
            ):
                result = await pipeline_module.process_file_path(tmp_path)

            assert "session_id" in result
        finally:
            Path(tmp_path).unlink(missing_ok=True)
