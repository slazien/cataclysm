"""Tests for telemetry-driven corner metadata enrichment."""

from __future__ import annotations

import math

import numpy as np

from cataclysm.corner_enrichment import auto_enrich_corner_metadata
from cataclysm.corners import Corner


def _make_corner(
    *,
    number: int = 1,
    entry: float = 100.0,
    apex: float = 160.0,
    exit: float = 220.0,
) -> Corner:
    return Corner(
        number=number,
        entry_distance_m=entry,
        exit_distance_m=exit,
        apex_distance_m=apex,
        min_speed_mps=20.0,
        brake_point_m=None,
        peak_brake_g=None,
        throttle_commit_m=None,
        apex_type="mid",
    )


def _base_lap_data(n: int = 401) -> dict[str, np.ndarray]:
    distance = np.linspace(0.0, 400.0, n)
    lat = 40.0 + distance / 111_320.0
    lon = np.full_like(distance, -86.0)
    return {
        "distance_m": distance,
        "speed_mps": np.full(n, 40.0),
        "heading_deg": np.zeros(n),
        "lateral_g": np.zeros(n),
        "longitudinal_g": np.zeros(n),
        "throttle_pct": np.full(n, 100.0),
        "brake_pct": np.zeros(n),
        "altitude_m": np.full(n, 100.0),
        "lat": lat,
        "lon": lon,
    }


def _apply_approach_profile(
    lap_data: dict[str, np.ndarray],
    *,
    corner: Corner,
    speed_start: float,
    speed_end: float,
    throttle_start: float,
    throttle_end: float,
    brake_pct: float,
    long_g: float,
) -> None:
    dist = lap_data["distance_m"]
    start = corner.apex_distance_m - 80.0
    end = corner.apex_distance_m - 10.0
    mask = (dist >= start) & (dist <= end)
    count = int(np.sum(mask))
    if count < 2:
        return

    lap_data["speed_mps"][mask] = np.linspace(speed_start, speed_end, count)
    lap_data["throttle_pct"][mask] = np.linspace(throttle_start, throttle_end, count)
    lap_data["brake_pct"][mask] = brake_pct
    lap_data["longitudinal_g"][mask] = long_g


class TestCharacterDetection:
    def test_flat_out_corner(self) -> None:
        corner = _make_corner()
        lap = _base_lap_data()
        _apply_approach_profile(
            lap,
            corner=corner,
            speed_start=40.0,
            speed_end=39.2,
            throttle_start=100.0,
            throttle_end=100.0,
            brake_pct=0.0,
            long_g=-0.01,
        )

        auto_enrich_corner_metadata([corner], lap)
        assert corner.character == "flat"

    def test_lift_corner(self) -> None:
        corner = _make_corner()
        lap = _base_lap_data()
        _apply_approach_profile(
            lap,
            corner=corner,
            speed_start=40.0,
            speed_end=36.5,
            throttle_start=100.0,
            throttle_end=60.0,
            brake_pct=0.0,
            long_g=-0.05,
        )

        auto_enrich_corner_metadata([corner], lap)
        assert corner.character == "lift"

    def test_brake_corner(self) -> None:
        corner = _make_corner()
        lap = _base_lap_data()
        _apply_approach_profile(
            lap,
            corner=corner,
            speed_start=40.0,
            speed_end=31.0,
            throttle_start=80.0,
            throttle_end=20.0,
            brake_pct=35.0,
            long_g=-0.35,
        )

        auto_enrich_corner_metadata([corner], lap)
        assert corner.character == "brake"

    def test_left_foot_braking(self) -> None:
        corner = _make_corner()
        lap = _base_lap_data()
        _apply_approach_profile(
            lap,
            corner=corner,
            speed_start=40.0,
            speed_end=33.0,
            throttle_start=70.0,
            throttle_end=50.0,
            brake_pct=12.0,
            long_g=-0.20,
        )

        auto_enrich_corner_metadata([corner], lap)
        assert corner.character == "brake"

    def test_short_approach_window(self) -> None:
        corner = _make_corner(entry=100.0, apex=107.0, exit=130.0)
        lap = _base_lap_data()

        auto_enrich_corner_metadata([corner], lap)
        assert corner.character is None

    def test_preserves_curated_character(self) -> None:
        corner = _make_corner()
        corner.character = "lift"
        lap = _base_lap_data()
        _apply_approach_profile(
            lap,
            corner=corner,
            speed_start=40.0,
            speed_end=30.0,
            throttle_start=90.0,
            throttle_end=10.0,
            brake_pct=50.0,
            long_g=-0.6,
        )

        auto_enrich_corner_metadata([corner], lap)
        assert corner.character == "lift"


class TestDirectionDetection:
    def test_left_turn(self) -> None:
        corner = _make_corner(entry=20.0, apex=50.0, exit=80.0)
        lap = _base_lap_data(n=121)
        dist = lap["distance_m"]
        lap["heading_deg"] = np.interp(dist, [0.0, 20.0, 80.0, 120.0], [90.0, 90.0, 40.0, 40.0])

        auto_enrich_corner_metadata([corner], lap)
        assert corner.direction == "left"

    def test_right_turn(self) -> None:
        corner = _make_corner(entry=20.0, apex=50.0, exit=80.0)
        lap = _base_lap_data(n=121)
        dist = lap["distance_m"]
        lap["heading_deg"] = np.interp(dist, [0.0, 20.0, 80.0, 120.0], [90.0, 90.0, 140.0, 140.0])

        auto_enrich_corner_metadata([corner], lap)
        assert corner.direction == "right"

    def test_preserves_curated_direction(self) -> None:
        corner = _make_corner()
        corner.direction = "left"
        lap = _base_lap_data()
        lap["heading_deg"] += np.linspace(0.0, 30.0, len(lap["heading_deg"]))

        auto_enrich_corner_metadata([corner], lap)
        assert corner.direction == "left"

    def test_wrap_around_heading(self) -> None:
        corner = _make_corner(entry=10.0, apex=20.0, exit=30.0)
        lap = _base_lap_data(n=41)
        dist = lap["distance_m"]
        lap["heading_deg"] = np.interp(dist, [0.0, 10.0, 30.0, 40.0], [350.0, 350.0, 370.0, 370.0])
        lap["heading_deg"] = np.mod(lap["heading_deg"], 360.0)

        auto_enrich_corner_metadata([corner], lap)
        assert corner.direction == "right"


class TestCamberDetection:
    def _build_camber_lap(
        self,
        phi_deg: float,
        *,
        heading_rate_deg_per_m: float = 0.8,
    ) -> dict[str, np.ndarray]:
        distance = np.linspace(0.0, 200.0, 401)
        heading = 90.0 + heading_rate_deg_per_m * distance
        speed = np.full_like(distance, 20.0)
        kappa = np.deg2rad(heading_rate_deg_per_m)
        ay_kin = speed * speed * kappa
        ay_imu = ay_kin - 9.81 * math.sin(math.radians(phi_deg))
        lateral_g = ay_imu / 9.81

        lat = 40.0 + distance / 111_320.0
        lon = np.full_like(distance, -86.0)
        return {
            "distance_m": distance,
            "speed_mps": speed,
            "heading_deg": heading,
            "lateral_g": lateral_g,
            "brake_pct": np.zeros_like(distance),
            "lat": lat,
            "lon": lon,
        }

    def test_positive_camber(self) -> None:
        corner = _make_corner(entry=50.0, apex=100.0, exit=150.0)
        lap = _base_lap_data(n=401)
        all_laps = {
            1: self._build_camber_lap(3.0),
            2: self._build_camber_lap(3.2),
            3: self._build_camber_lap(2.8),
        }

        auto_enrich_corner_metadata([corner], lap, all_laps)
        assert corner.camber == "positive"
        assert corner.banking_deg is not None
        assert corner.banking_deg > 1.5

    def test_off_camber(self) -> None:
        corner = _make_corner(entry=50.0, apex=100.0, exit=150.0)
        lap = _base_lap_data(n=401)
        all_laps = {
            1: self._build_camber_lap(-5.0),
            2: self._build_camber_lap(-4.8),
            3: self._build_camber_lap(-5.2),
        }

        auto_enrich_corner_metadata([corner], lap, all_laps)
        assert corner.camber == "off-camber"

    def test_flat(self) -> None:
        corner = _make_corner(entry=50.0, apex=100.0, exit=150.0)
        lap = _base_lap_data(n=401)
        all_laps = {
            1: self._build_camber_lap(0.2),
            2: self._build_camber_lap(-0.3),
            3: self._build_camber_lap(0.1),
        }

        auto_enrich_corner_metadata([corner], lap, all_laps)
        assert corner.camber == "flat"

    def test_insufficient_laps(self) -> None:
        corner = _make_corner(entry=50.0, apex=100.0, exit=150.0)
        lap = _base_lap_data(n=401)
        all_laps = {
            1: self._build_camber_lap(3.0),
            2: self._build_camber_lap(3.2),
        }

        auto_enrich_corner_metadata([corner], lap, all_laps)
        assert corner.camber is None
        assert corner.banking_deg is None

    def test_preserves_curated_camber(self) -> None:
        corner = _make_corner(entry=50.0, apex=100.0, exit=150.0)
        corner.camber = "positive"
        lap = _base_lap_data(n=401)
        all_laps = {
            1: self._build_camber_lap(-5.0),
            2: self._build_camber_lap(-5.0),
            3: self._build_camber_lap(-5.0),
        }

        auto_enrich_corner_metadata([corner], lap, all_laps)
        assert corner.camber == "positive"

    def test_sets_banking_deg(self) -> None:
        corner = _make_corner(entry=50.0, apex=100.0, exit=150.0)
        lap = _base_lap_data(n=401)
        all_laps = {
            1: self._build_camber_lap(2.0),
            2: self._build_camber_lap(2.0),
            3: self._build_camber_lap(2.0),
        }

        auto_enrich_corner_metadata([corner], lap, all_laps)
        assert corner.banking_deg is not None


class TestBlindCrestDetection:
    def test_crest_before_apex(self) -> None:
        corner = _make_corner(entry=60.0, apex=100.0, exit=140.0)
        corner.brake_point_m = 70.0
        lap = _base_lap_data(n=401)
        dist = lap["distance_m"]
        lap["altitude_m"] = 100.0 + np.exp(-((dist - 85.0) ** 2) / (2 * 7.0**2)) * 4.0

        auto_enrich_corner_metadata([corner], lap)
        assert corner.blind is True

    def test_flat_approach(self) -> None:
        corner = _make_corner(entry=60.0, apex=100.0, exit=140.0)
        corner.brake_point_m = 70.0
        lap = _base_lap_data(n=401)

        auto_enrich_corner_metadata([corner], lap)
        assert corner.blind is False

    def test_downhill_approach(self) -> None:
        corner = _make_corner(entry=60.0, apex=100.0, exit=140.0)
        corner.brake_point_m = 70.0
        lap = _base_lap_data(n=401)
        dist = lap["distance_m"]
        lap["altitude_m"] = 120.0 - 0.05 * dist

        auto_enrich_corner_metadata([corner], lap)
        assert corner.blind is False

    def test_preserves_curated_blind(self) -> None:
        corner = _make_corner()
        corner.blind = True
        lap = _base_lap_data()

        auto_enrich_corner_metadata([corner], lap)
        assert corner.blind is True


class TestCoachingNotes:
    def test_brake_downhill_notes(self) -> None:
        corner = _make_corner()
        corner.character = "brake"
        corner.elevation_trend = "downhill"

        auto_enrich_corner_metadata([corner], _base_lap_data())
        assert corner.coaching_notes is not None
        assert "Trail-brake" in corner.coaching_notes
        assert "downhill" in corner.coaching_notes.lower()

    def test_offcamber_blind_notes(self) -> None:
        corner = _make_corner()
        corner.camber = "off-camber"
        corner.blind = True

        auto_enrich_corner_metadata([corner], _base_lap_data())
        assert corner.coaching_notes is not None
        assert "Off-camber" in corner.coaching_notes
        assert "Blind apex" in corner.coaching_notes

    def test_preserves_curated_notes(self) -> None:
        corner = _make_corner()
        corner.coaching_notes = "Use curb on exit."

        auto_enrich_corner_metadata([corner], _base_lap_data())
        assert corner.coaching_notes == "Use curb on exit."

    def test_empty_when_no_metadata(self) -> None:
        corner = _make_corner()
        lap = _base_lap_data()

        auto_enrich_corner_metadata([corner], lap)
        # Direction/shape may be inferred, so clear any auto-note triggers.
        if corner.character is None and corner.elevation_trend is None and not corner.blind:
            assert corner.coaching_notes is None


class TestFullEnrichment:
    def test_partial_curated_fills_gaps(self) -> None:
        corner = _make_corner(entry=60.0, apex=120.0, exit=180.0)
        corner.direction = "left"  # curated value should remain

        lap = _base_lap_data(n=401)
        dist = lap["distance_m"]
        lap["heading_deg"] = np.interp(dist, [0.0, 60.0, 180.0, 400.0], [90.0, 90.0, 150.0, 150.0])
        _apply_approach_profile(
            lap,
            corner=corner,
            speed_start=40.0,
            speed_end=33.0,
            throttle_start=90.0,
            throttle_end=35.0,
            brake_pct=20.0,
            long_g=-0.3,
        )
        all_laps = {
            1: TestCamberDetection()._build_camber_lap(2.5),
            2: TestCamberDetection()._build_camber_lap(2.4),
            3: TestCamberDetection()._build_camber_lap(2.6),
        }

        auto_enrich_corner_metadata([corner], lap, all_laps)

        assert corner.direction == "left"
        assert corner.character == "brake"
        assert corner.corner_type_hint is not None
        assert corner.apex_lat is not None and corner.apex_lon is not None
        assert corner.camber in {"positive", "flat", "negative", "off-camber"}

    def test_preserves_all_curated_fields(self) -> None:
        corner = _make_corner()
        corner.character = "lift"
        corner.direction = "left"
        corner.corner_type_hint = "hairpin"
        corner.elevation_trend = "uphill"
        corner.camber = "positive"
        corner.blind = True
        corner.coaching_notes = "Custom tip"

        auto_enrich_corner_metadata([corner], _base_lap_data())

        assert corner.character == "lift"
        assert corner.direction == "left"
        assert corner.corner_type_hint == "hairpin"
        assert corner.elevation_trend == "uphill"
        assert corner.camber == "positive"
        assert corner.blind is True
        assert corner.coaching_notes == "Custom tip"
