from __future__ import annotations

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
