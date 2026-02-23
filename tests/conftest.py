"""Shared test fixtures for Cataclysm tests."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

# CSV header/unit/source rows are necessarily long (raw RaceChrono format)
_CSV_COLUMNS = (
    "timestamp,fragment_id,lap_number,elapsed_time,"
    "distance_traveled,accuracy,altitude,bearing,"
    "device_battery_level,device_update_rate,fix_type,"
    "latitude,longitude,satellites,speed,combined_acc,"
    "device_update_rate,lateral_acc,lean_angle,"
    "longitudinal_acc,speed,device_update_rate,"
    "x_acc,y_acc,z_acc,device_update_rate,"
    "x_rate_of_rotation,y_rate_of_rotation,z_rate_of_rotation"
)

_CSV_UNITS = (
    "unix time,,,s,m,m,m,deg,%,Hz,,deg,deg,sats,m/s,G,Hz,G,deg,G,m/s,Hz,G,G,G,Hz,deg/s,deg/s,deg/s"
)

_CSV_SOURCES = (
    ",,,,,100: gps,100: gps,100: gps,100: gps,100: gps,"
    "100: gps,100: gps,100: gps,100: gps,100: gps,"
    "calc,calc,calc,calc,calc,calc,"
    "101: acc,101: acc,101: acc,101: acc,"
    "102: gyro,102: gyro,102: gyro,102: gyro"
)


def _build_header() -> str:
    """Build the RaceChrono CSV v3 metadata + header rows."""
    lines = [
        "This file is created using RaceChrono v9.1.3 ( http://racechrono.com/ ).",
        "Format,3",
        'Session title,"Test Track"',
        "Session type,Lap timing",
        'Track name,"Test Circuit"',
        "Driver name,Tester",
        "Created,22/02/2026,10:00",
        "Note,",
        "",
        _CSV_COLUMNS,
        _CSV_UNITS,
        _CSV_SOURCES,
    ]
    return "\n".join(lines) + "\n"


def _build_data_row(
    ts: float,
    elapsed: float,
    dist: float,
    lat: float,
    lon: float,
    speed: float,
    heading: float,
    acc: float,
    sats: int,
    lap_num: str,
    lat_g: float = 0.0,
    lon_g: float = 0.0,
    yaw: float = 0.0,
) -> str:
    """Build a single CSV data row."""
    return (
        f"{ts},0,{lap_num},{elapsed},{dist},{acc},200.0,"
        f"{heading},95,25,3,{lat},{lon},{sats},{speed},"
        f"0.0,20,{lat_g},0.0,{lon_g},{speed},25,"
        f"0.0,0.0,1.0,25,0.0,0.0,{yaw}"
    )


@pytest.fixture
def racechrono_csv_text() -> str:
    """Minimal valid RaceChrono CSV v3 text with 2 laps."""
    header = _build_header()

    lines: list[str] = []
    base_ts = 1700000000.0
    rng = np.random.default_rng(42)

    # Out-lap: 20 points, no lap_number
    for i in range(20):
        t = base_ts + i * 0.04
        elapsed = i * 0.04
        dist = i * 0.5
        lat = 33.53 + i * 0.00001
        lon = -86.62 + i * 0.00001
        speed = i * 0.5
        heading = 45.0
        lines.append(
            _build_data_row(
                t,
                elapsed,
                dist,
                lat,
                lon,
                speed,
                heading,
                acc=0.5,
                sats=10,
                lap_num="",
            )
        )

    # Lap 1: 200 points, ~500m
    base_elapsed = 20 * 0.04
    base_dist = 20 * 0.5
    for i in range(200):
        t = base_ts + base_elapsed + i * 0.04
        elapsed = base_elapsed + i * 0.04
        dist = base_dist + i * 2.5
        lat = 33.53 + 0.0002 * np.sin(2 * np.pi * i / 200)
        lon = -86.62 + 0.0004 * np.cos(2 * np.pi * i / 200)
        speed = 30.0 + 10.0 * np.sin(2 * np.pi * i / 50)
        heading = (i * 360 / 200) % 360
        lat_g = 0.5 * np.sin(2 * np.pi * i / 50)
        lon_g = -0.3 * np.cos(2 * np.pi * i / 50) + rng.normal(0, 0.02)
        yaw = 10.0 * np.sin(2 * np.pi * i / 50)
        lines.append(
            _build_data_row(
                t,
                elapsed,
                dist,
                lat,
                lon,
                speed,
                heading,
                acc=0.3,
                sats=12,
                lap_num="1",
                lat_g=lat_g,
                lon_g=lon_g,
                yaw=yaw,
            )
        )

    # Lap 2: 200 points, ~500m (slightly slower)
    base_elapsed2 = base_elapsed + 200 * 0.04
    base_dist2 = base_dist + 200 * 2.5
    for i in range(200):
        t = base_ts + base_elapsed2 + i * 0.042
        elapsed = base_elapsed2 + i * 0.042
        dist = base_dist2 + i * 2.5
        lat = 33.53 + 0.0002 * np.sin(2 * np.pi * i / 200)
        lon = -86.62 + 0.0004 * np.cos(2 * np.pi * i / 200)
        speed = 29.0 + 10.0 * np.sin(2 * np.pi * i / 50)
        heading = (i * 360 / 200) % 360
        lat_g = 0.5 * np.sin(2 * np.pi * i / 50)
        lon_g = -0.3 * np.cos(2 * np.pi * i / 50) + rng.normal(0, 0.02)
        yaw = 10.0 * np.sin(2 * np.pi * i / 50)
        lines.append(
            _build_data_row(
                t,
                elapsed,
                dist,
                lat,
                lon,
                speed,
                heading,
                acc=0.3,
                sats=12,
                lap_num="2",
                lat_g=lat_g,
                lon_g=lon_g,
                yaw=yaw,
            )
        )

    return header + "\n".join(lines) + "\n"


@pytest.fixture
def racechrono_csv_file(racechrono_csv_text: str, tmp_path: object) -> str:
    """Write the synthetic CSV to a temp file and return the path."""
    import pathlib

    p = pathlib.Path(str(tmp_path)) / "test_session.csv"
    p.write_text(racechrono_csv_text)
    return str(p)


@pytest.fixture
def parsed_session(racechrono_csv_file: str) -> object:
    """Parse the synthetic CSV."""
    from cataclysm.parser import parse_racechrono_csv

    return parse_racechrono_csv(racechrono_csv_file)


@pytest.fixture
def processed_session(parsed_session: object) -> object:
    """Process the parsed session."""
    from cataclysm.engine import process_session

    return process_session(parsed_session.data)  # type: ignore[union-attr]


@pytest.fixture
def sample_resampled_lap() -> pd.DataFrame:
    """Create a synthetic resampled lap DataFrame for testing."""
    n_points = 1000
    step = 0.7
    distance = np.arange(n_points) * step

    # Simulate an oval track with 4 corners
    heading = np.zeros(n_points)
    speed = np.ones(n_points) * 40.0

    for corner_center in [125, 375, 625, 875]:
        corner_range = np.arange(
            max(0, corner_center - 40),
            min(n_points, corner_center + 40),
        )
        for j in corner_range:
            offset = j - corner_center
            heading[j] = heading[max(0, j - 1)] + 3.0 * np.exp(-(offset**2) / 200)
        for j in corner_range:
            offset = j - corner_center
            speed[j] = 40.0 - 15.0 * np.exp(-(offset**2) / 200)

    heading = np.cumsum(np.concatenate([[0], np.diff(heading)])) % 360

    # Compute time from speed
    dt = step / np.maximum(speed, 1.0)
    lap_time = np.cumsum(dt)

    # Generate G-forces
    lon_g = np.gradient(speed) / 9.81 * 10
    lat_g = np.zeros(n_points)
    yaw = np.gradient(heading) * speed

    lat = 33.53 + np.sin(np.radians(heading)) * distance / 111000
    lon = -86.62 + np.cos(np.radians(heading)) * distance / 111000

    return pd.DataFrame(
        {
            "lap_distance_m": distance,
            "lap_time_s": lap_time,
            "speed_mps": speed,
            "heading_deg": heading % 360,
            "lat": lat,
            "lon": lon,
            "lateral_g": lat_g,
            "longitudinal_g": lon_g,
            "yaw_rate_dps": yaw,
            "altitude_m": np.full(n_points, 200.0),
            "x_acc_g": np.zeros(n_points),
            "y_acc_g": np.zeros(n_points),
            "z_acc_g": np.ones(n_points),
        }
    )
