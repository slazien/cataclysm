from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import backend.api.services.track_corners as tc_module
from backend.api.services.track_corners import (
    _corner_override_hashes,
    _corner_overrides,
    _corners_content_hash,
    get_corner_override_version,
    update_corner_cache,
)

_CORNERS_A = [{"number": 1, "name": "T1", "fraction": 0.1}]
_CORNERS_B = [{"number": 1, "name": "T1", "fraction": 0.15}]


class TestCornerOverrideVersioning:
    def setup_method(self) -> None:
        _corner_overrides.clear()
        _corner_override_hashes.clear()

    def test_initial_version_is_none(self) -> None:
        assert get_corner_override_version("barber-motorsports-park") is None

    def test_update_sets_hash(self) -> None:
        update_corner_cache("barber-motorsports-park", _CORNERS_A)
        version = get_corner_override_version("barber-motorsports-park")
        assert version is not None
        assert version == _corners_content_hash(_CORNERS_A)

    def test_second_update_changes_hash(self) -> None:
        update_corner_cache("barber-motorsports-park", _CORNERS_A)
        v1 = get_corner_override_version("barber-motorsports-park")
        update_corner_cache("barber-motorsports-park", _CORNERS_B)
        v2 = get_corner_override_version("barber-motorsports-park")
        assert v1 != v2

    def test_same_content_produces_same_hash(self) -> None:
        """Restart-safety: same DB corners → same hash regardless of process lifetime."""
        update_corner_cache("barber-motorsports-park", _CORNERS_A)
        v1 = get_corner_override_version("barber-motorsports-park")
        # Simulate restart: clear and reload same data
        _corner_overrides.clear()
        _corner_override_hashes.clear()
        update_corner_cache("barber-motorsports-park", _CORNERS_A)
        v2 = get_corner_override_version("barber-motorsports-park")
        assert v1 == v2

    def test_different_tracks_have_independent_versions(self) -> None:
        update_corner_cache("barber-motorsports-park", _CORNERS_A)
        update_corner_cache("road-atlanta", _CORNERS_B)
        assert get_corner_override_version("barber-motorsports-park") is not None
        assert get_corner_override_version("road-atlanta") is not None
        assert get_corner_override_version(
            "barber-motorsports-park"
        ) != get_corner_override_version("road-atlanta")


class TestReapplyCornerOverrides:
    def setup_method(self) -> None:
        tc_module._corner_overrides.clear()
        tc_module._corner_override_hashes.clear()
        tc_module._cache_loaded = False

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
        corners = [{"number": 1, "name": "T1", "fraction": 0.1}]
        h = _corners_content_hash(corners)
        sd = MagicMock()
        sd.layout = MagicMock()
        sd.layout.name = "Barber Motorsports Park"
        sd.corner_override_version = h
        tc_module._corner_override_hashes["barber-motorsports-park"] = h
        assert tc_module.reapply_corner_overrides_if_stale(sd) is False

    def test_stale_version_triggers_reextraction(self) -> None:
        corners_old = [{"number": 1, "name": "T1", "fraction": 0.1}]
        corners_new = [{"number": 1, "name": "T1", "fraction": 0.2}]

        sd = MagicMock()
        sd.layout = MagicMock()
        sd.layout.name = "Barber Motorsports Park"
        sd.corner_override_version = _corners_content_hash(corners_old)
        sd.processed.best_lap = 3
        sd.coaching_laps = [3, 5]
        sd.processed.resampled_laps = {3: MagicMock(), 5: MagicMock()}
        sd.session_id = "test-sess"

        tc_module._corner_override_hashes["barber-motorsports-park"] = _corners_content_hash(
            corners_new
        )
        tc_module._corner_overrides["barber-motorsports-park"] = corners_new
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
        assert sd.corner_override_version == _corners_content_hash(corners_new)
        assert sd.corners == mock_skeletons
        assert sd.layout == mock_new_layout

    def test_version_none_to_hash_triggers_reextraction(self) -> None:
        """Sessions processed before versioning (version=None) pick up overrides."""
        corners = [{"number": 1, "name": "T1", "fraction": 0.1}]

        sd = MagicMock()
        sd.layout = MagicMock()
        sd.layout.name = "Barber Motorsports Park"
        sd.corner_override_version = None
        sd.processed.best_lap = 3
        sd.coaching_laps = [3]
        sd.processed.resampled_laps = {3: MagicMock()}
        sd.session_id = "test-sess"

        tc_module._corner_override_hashes["barber-motorsports-park"] = _corners_content_hash(
            corners
        )
        tc_module._corner_overrides["barber-motorsports-park"] = corners
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
        assert sd.corner_override_version == _corners_content_hash(corners)


class TestIntegrationReapply:
    def setup_method(self) -> None:
        tc_module._corner_overrides.clear()
        tc_module._corner_override_hashes.clear()
        tc_module._cache_loaded = True  # simulate startup load

    def test_full_round_trip(self) -> None:
        """Admin saves corners -> existing session picks them up on next read."""
        from cataclysm.track_db import OfficialCorner, TrackLayout

        sd = MagicMock()
        sd.layout = TrackLayout(
            name="Test Track",
            country="US",
            length_m=3000,
            corners=[OfficialCorner(number=1, name="T1", fraction=0.1)],
        )
        sd.corner_override_version = None
        sd.processed.best_lap = 1
        sd.coaching_laps = [1]
        sd.processed.resampled_laps = {1: MagicMock()}
        sd.session_id = "integration-test"

        new_corners = [
            {"number": 1, "name": "T1-moved", "fraction": 0.15},
            {"number": 2, "name": "T2-new", "fraction": 0.5},
        ]
        tc_module.update_corner_cache("test-track", new_corners)

        mock_skeletons = [MagicMock(), MagicMock()]
        with (
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
        assert sd.corner_override_version == _corners_content_hash(new_corners)
        assert sd.corners == mock_skeletons
        assert len(sd.layout.corners) == 2
        assert sd.layout.corners[0].name == "T1-moved"
        assert sd.layout.corners[1].name == "T2-new"

        # Second call should be no-op (same hash)
        result2 = tc_module.reapply_corner_overrides_if_stale(sd)
        assert result2 is False

    @pytest.mark.asyncio
    async def test_ensure_corners_current_invalidates_caches(self) -> None:
        """ensure_corners_current invalidates physics + coaching caches when stale."""
        corners_old = [{"number": 1, "name": "T1", "fraction": 0.1}]
        corners_new = [{"number": 1, "name": "T1", "fraction": 0.2}]

        sd = MagicMock()
        sd.layout = MagicMock()
        sd.layout.name = "Barber Motorsports Park"
        sd.corner_override_version = _corners_content_hash(corners_old)
        sd.processed.best_lap = 1
        sd.coaching_laps = [1]
        sd.processed.resampled_laps = {1: MagicMock()}
        sd.session_id = "cache-test"

        tc_module._corner_override_hashes["barber-motorsports-park"] = _corners_content_hash(
            corners_new
        )
        tc_module._corner_overrides["barber-motorsports-park"] = corners_new

        mock_corners = [MagicMock()]
        with (
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
            patch(
                "backend.api.services.track_corners.override_layout_corners",
                return_value=sd.layout,
            ),
            patch(
                "backend.api.services.pipeline.invalidate_physics_cache",
            ) as mock_physics,
            patch(
                "backend.api.services.coaching_store.clear_coaching_data",
                new_callable=AsyncMock,
            ) as mock_coaching,
        ):
            await tc_module.ensure_corners_current(sd)

        mock_physics.assert_called_once_with("cache-test")
        mock_coaching.assert_called_once_with("cache-test")
