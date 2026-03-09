"""Tests for the hybrid DB+Python track lookup layer."""

from __future__ import annotations

from unittest.mock import MagicMock

from cataclysm.track_db import OfficialCorner, TrackLayout
from cataclysm.track_db_hybrid import (
    db_track_to_layout,
    get_all_tracks_hybrid,
    lookup_track_hybrid,
)


class TestDbTrackToLayout:
    def test_converts_db_track_to_layout(self) -> None:
        db_track = MagicMock()
        db_track.name = "Test Track"
        db_track.center_lat = 33.53
        db_track.center_lon = -86.62
        db_track.country = "US"
        db_track.length_m = 3662.4
        db_track.elevation_range_m = 24.0
        db_track.aliases = ["test"]

        db_corners = [
            MagicMock(
                number=1,
                name="T1",
                fraction=0.05,
                lat=None,
                lon=None,
                character="brake",
                direction="left",
                corner_type="sweeper",
                elevation_trend="downhill",
                camber="positive",
                blind=False,
                coaching_notes="Heavy braking.",
            )
        ]

        db_landmarks = [
            MagicMock(
                name="S/F gantry",
                distance_m=0.0,
                landmark_type="structure",
                lat=None,
                lon=None,
                description="Timing gantry",
            )
        ]

        layout = db_track_to_layout(db_track, db_corners, db_landmarks)
        assert isinstance(layout, TrackLayout)
        assert layout.name == "Test Track"
        assert len(layout.corners) == 1
        assert layout.corners[0].direction == "left"
        assert layout.corners[0].character == "brake"
        assert len(layout.landmarks) == 1


class TestLookupTrackHybrid:
    def test_falls_back_to_python(self) -> None:
        layout = lookup_track_hybrid("Barber Motorsports Park", db_tracks={})
        assert layout is not None
        assert layout.name == "Barber Motorsports Park"

    def test_uses_db_when_available(self) -> None:
        mock_layout = TrackLayout(
            name="DB Barber",
            corners=[OfficialCorner(1, "T1 DB", 0.05)],
            center_lat=33.53,
            center_lon=-86.62,
        )
        db_tracks = {"barber motorsports park": mock_layout}
        layout = lookup_track_hybrid("Barber Motorsports Park", db_tracks=db_tracks)
        assert layout is not None
        assert layout.name == "DB Barber"

    def test_unknown_track_returns_none(self) -> None:
        layout = lookup_track_hybrid("Unknown Circuit", db_tracks={})
        assert layout is None


class TestGetAllTracksHybrid:
    def test_merges_db_and_python(self) -> None:
        mock_layout = TrackLayout(name="DB Track Only", corners=[])
        db_tracks = {"db track only": mock_layout}
        all_tracks = get_all_tracks_hybrid(db_tracks=db_tracks)
        names = [t.name for t in all_tracks]
        assert "DB Track Only" in names
        assert "Barber Motorsports Park" in names  # From Python fallback
