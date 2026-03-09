from __future__ import annotations

from unittest.mock import MagicMock, patch

import backend.api.services.track_corners as tc_module
from backend.api.services.track_corners import (
    _corner_override_versions,
    _corner_overrides,
    get_corner_override_version,
    update_corner_cache,
)


class TestCornerOverrideVersioning:
    def setup_method(self) -> None:
        _corner_overrides.clear()
        _corner_override_versions.clear()

    def test_initial_version_is_none(self) -> None:
        assert get_corner_override_version("barber-motorsports-park") is None

    def test_update_sets_version_1(self) -> None:
        update_corner_cache(
            "barber-motorsports-park",
            [{"number": 1, "name": "T1", "fraction": 0.1}],
        )
        assert get_corner_override_version("barber-motorsports-park") == 1

    def test_second_update_increments_version(self) -> None:
        update_corner_cache(
            "barber-motorsports-park",
            [{"number": 1, "name": "T1", "fraction": 0.1}],
        )
        update_corner_cache(
            "barber-motorsports-park",
            [{"number": 1, "name": "T1", "fraction": 0.15}],
        )
        assert get_corner_override_version("barber-motorsports-park") == 2

    def test_different_tracks_have_independent_versions(self) -> None:
        update_corner_cache(
            "barber-motorsports-park",
            [{"number": 1, "name": "T1", "fraction": 0.1}],
        )
        update_corner_cache(
            "road-atlanta",
            [{"number": 1, "name": "T1", "fraction": 0.2}],
        )
        assert get_corner_override_version("barber-motorsports-park") == 1
        assert get_corner_override_version("road-atlanta") == 1


class TestReapplyCornerOverrides:
    def setup_method(self) -> None:
        tc_module._corner_overrides.clear()
        tc_module._corner_override_versions.clear()

    def test_no_layout_returns_false(self) -> None:
        sd = MagicMock()
        sd.layout = None
        assert tc_module.reapply_corner_overrides_if_stale(sd) is False

    def test_no_override_returns_false(self) -> None:
        sd = MagicMock()
        sd.layout = MagicMock()
        sd.layout.name = "Barber Motorsports Park"
        sd.corner_override_version = None
        # No override in cache → version is None → return False
        assert tc_module.reapply_corner_overrides_if_stale(sd) is False

    def test_same_version_returns_false(self) -> None:
        sd = MagicMock()
        sd.layout = MagicMock()
        sd.layout.name = "Barber Motorsports Park"
        sd.corner_override_version = 2
        tc_module._corner_override_versions["barber-motorsports-park"] = 2
        assert tc_module.reapply_corner_overrides_if_stale(sd) is False

    def test_stale_version_triggers_reextraction(self) -> None:
        sd = MagicMock()
        sd.layout = MagicMock()
        sd.layout.name = "Barber Motorsports Park"
        sd.corner_override_version = 1
        sd.processed.best_lap = 3
        sd.coaching_laps = [3, 5]
        sd.processed.resampled_laps = {3: MagicMock(), 5: MagicMock()}
        sd.session_id = "test-sess"

        tc_module._corner_override_versions["barber-motorsports-park"] = 2
        tc_module._corner_overrides["barber-motorsports-park"] = [
            {"number": 1, "name": "T1", "fraction": 0.1}
        ]
        tc_module._cache_loaded = True

        mock_new_layout = MagicMock()
        mock_skeletons = [MagicMock()]
        with (
            patch(
                "backend.api.services.track_corners.override_layout_corners",
                return_value=mock_new_layout,
            ),
            patch(
                "backend.api.services.track_corners.locate_official_corners",
                return_value=mock_skeletons,
            ),
            patch(
                "backend.api.services.track_corners.extract_corner_kpis_for_lap",
                return_value=mock_skeletons,
            ),
            patch(
                "backend.api.services.track_corners.compute_corner_elevation",
                return_value=None,
            ),
        ):
            result = tc_module.reapply_corner_overrides_if_stale(sd)

        assert result is True
        assert sd.corner_override_version == 2
        assert sd.corners == mock_skeletons
        assert sd.layout == mock_new_layout

    def test_version_none_to_1_triggers_reextraction(self) -> None:
        """Sessions processed before versioning (version=None) pick up v1 overrides."""
        sd = MagicMock()
        sd.layout = MagicMock()
        sd.layout.name = "Barber Motorsports Park"
        sd.corner_override_version = None
        sd.processed.best_lap = 3
        sd.coaching_laps = [3]
        sd.processed.resampled_laps = {3: MagicMock()}
        sd.session_id = "test-sess"

        tc_module._corner_override_versions["barber-motorsports-park"] = 1
        tc_module._corner_overrides["barber-motorsports-park"] = [
            {"number": 1, "name": "T1", "fraction": 0.1}
        ]
        tc_module._cache_loaded = True

        mock_new_layout = MagicMock()
        mock_corners = [MagicMock()]
        with (
            patch(
                "backend.api.services.track_corners.override_layout_corners",
                return_value=mock_new_layout,
            ),
            patch(
                "backend.api.services.track_corners.locate_official_corners",
                return_value=mock_corners,
            ),
            patch(
                "backend.api.services.track_corners.extract_corner_kpis_for_lap",
                return_value=mock_corners,
            ),
            patch(
                "backend.api.services.track_corners.compute_corner_elevation",
                return_value=None,
            ),
        ):
            result = tc_module.reapply_corner_overrides_if_stale(sd)

        assert result is True
        assert sd.corner_override_version == 1
