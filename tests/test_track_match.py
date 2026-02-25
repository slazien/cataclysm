"""Tests for cataclysm.track_match: GPS-based track auto-detection."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from cataclysm.track_match import (
    TrackMatch,
    compute_session_centroid,
    detect_track,
    detect_track_or_lookup,
    haversine,
)


class TestHaversine:
    def test_same_point_is_zero(self) -> None:
        assert haversine(33.53, -86.62, 33.53, -86.62) == 0.0

    def test_known_distance(self) -> None:
        # New York to London: ~5570 km
        dist = haversine(40.7128, -74.0060, 51.5074, -0.1278)
        assert dist == pytest.approx(5_570_000, rel=0.02)

    def test_short_distance(self) -> None:
        # ~111 km per degree of latitude
        dist = haversine(33.0, -86.0, 34.0, -86.0)
        assert dist == pytest.approx(111_000, rel=0.01)

    def test_symmetric(self) -> None:
        d1 = haversine(33.53, -86.62, 34.0, -86.0)
        d2 = haversine(34.0, -86.0, 33.53, -86.62)
        assert d1 == pytest.approx(d2)


class TestComputeSessionCentroid:
    def test_basic_centroid(self) -> None:
        df = pd.DataFrame({"lat": np.full(100, 33.53), "lon": np.full(100, -86.62)})
        lat, lon = compute_session_centroid(df)
        assert lat == pytest.approx(33.53)
        assert lon == pytest.approx(-86.62)

    def test_insufficient_points_raises(self) -> None:
        df = pd.DataFrame({"lat": [33.53] * 10, "lon": [-86.62] * 10})
        with pytest.raises(ValueError, match="at least"):
            compute_session_centroid(df)

    def test_nan_values_handled(self) -> None:
        lats = np.full(60, 33.53)
        lons = np.full(60, -86.62)
        lats[0] = np.nan
        lons[0] = np.nan
        df = pd.DataFrame({"lat": lats, "lon": lons})
        lat, lon = compute_session_centroid(df)
        assert lat == pytest.approx(33.53)
        assert lon == pytest.approx(-86.62)


class TestDetectTrack:
    def _make_gps_df(self, lat: float = 33.53, lon: float = -86.62, n: int = 200) -> pd.DataFrame:
        rng = np.random.default_rng(42)
        return pd.DataFrame(
            {
                "lat": lat + rng.normal(0, 0.001, n),
                "lon": lon + rng.normal(0, 0.001, n),
            }
        )

    def test_detects_barber(self) -> None:
        df = self._make_gps_df(lat=33.5302, lon=-86.6215)
        match = detect_track(df)
        assert match is not None
        assert isinstance(match, TrackMatch)
        assert match.layout.name == "Barber Motorsports Park"
        assert match.distance_m < 1000
        assert match.confidence > 0.5

    def test_no_match_far_away(self) -> None:
        df = self._make_gps_df(lat=0.0, lon=0.0)
        match = detect_track(df)
        assert match is None

    def test_insufficient_points_returns_none(self) -> None:
        df = pd.DataFrame({"lat": [33.53] * 10, "lon": [-86.62] * 10})
        match = detect_track(df)
        assert match is None

    def test_confidence_decreases_with_distance(self) -> None:
        close = self._make_gps_df(lat=33.5302, lon=-86.6215)
        far = self._make_gps_df(lat=33.55, lon=-86.60)
        m_close = detect_track(close)
        m_far = detect_track(far)
        assert m_close is not None
        assert m_far is not None
        assert m_close.confidence > m_far.confidence


class TestDetectTrackOrLookup:
    def _make_gps_df(self, lat: float = 33.53, lon: float = -86.62, n: int = 200) -> pd.DataFrame:
        rng = np.random.default_rng(42)
        return pd.DataFrame(
            {
                "lat": lat + rng.normal(0, 0.001, n),
                "lon": lon + rng.normal(0, 0.001, n),
            }
        )

    def test_gps_preferred_over_name(self) -> None:
        df = self._make_gps_df(lat=33.5302, lon=-86.6215)
        layout = detect_track_or_lookup(df, "Wrong Name")
        assert layout is not None
        assert layout.name == "Barber Motorsports Park"

    def test_falls_back_to_name(self) -> None:
        df = self._make_gps_df(lat=0.0, lon=0.0)
        layout = detect_track_or_lookup(df, "Barber Motorsports Park")
        assert layout is not None
        assert layout.name == "Barber Motorsports Park"

    def test_both_fail_returns_none(self) -> None:
        df = self._make_gps_df(lat=0.0, lon=0.0)
        layout = detect_track_or_lookup(df, "Unknown Track")
        assert layout is None

    def test_insufficient_gps_falls_back(self) -> None:
        df = pd.DataFrame({"lat": [33.53], "lon": [-86.62]})
        layout = detect_track_or_lookup(df, "Barber Motorsports Park")
        assert layout is not None
        assert layout.name == "Barber Motorsports Park"
