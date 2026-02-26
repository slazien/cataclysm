"""Test fixtures for the backend test suite."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Generator
from unittest.mock import patch

import numpy as np
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import JSON, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.api.db.database import get_db
from backend.api.db.models import Base
from backend.api.dependencies import AuthenticatedUser, get_current_user
from backend.api.main import app
from backend.api.services.session_store import clear_all

# In-memory SQLite for test isolation — map JSONB → JSON for SQLite compat
_test_engine = create_async_engine("sqlite+aiosqlite:///", echo=False)


@event.listens_for(_test_engine.sync_engine, "connect")
def _set_sqlite_pragma(dbapi_conn: object, connection_record: object) -> None:
    """Enable WAL mode and foreign keys for SQLite test database."""
    cursor = dbapi_conn.cursor()  # type: ignore[union-attr]
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


# Patch JSONB columns to use JSON for SQLite
for table in Base.metadata.tables.values():
    for column in table.columns:
        if isinstance(column.type, JSONB):
            column.type = JSON()
_test_session_factory = async_sessionmaker(
    bind=_test_engine, class_=AsyncSession, expire_on_commit=False
)

_TEST_USER = AuthenticatedUser(
    user_id="test-user-123",
    email="test@example.com",
    name="Test Driver",
)

# CSV header/unit/source rows matching the RaceChrono v3 format from tests/conftest.py
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


def _build_header(track_name: str = "Test Circuit") -> str:
    """Build the RaceChrono CSV v3 metadata + header rows."""
    lines = [
        "This file is created using RaceChrono v9.1.3 ( http://racechrono.com/ ).",
        "Format,3",
        f'Session title,"{track_name}"',
        "Session type,Lap timing",
        f'Track name,"{track_name}"',
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


def build_synthetic_csv(
    track_name: str = "Test Circuit",
    n_laps: int = 2,
    points_per_lap: int = 200,
) -> bytes:
    """Build a synthetic RaceChrono CSV v3 as bytes for upload testing.

    Generates an out-lap + n_laps of realistic-looking data with varying
    speed, heading, and g-forces.
    """
    rng = np.random.default_rng(42)
    header = _build_header(track_name)
    lines: list[str] = []
    base_ts = 1700000000.0

    # Out-lap: 20 points, no lap_number
    for i in range(20):
        t = base_ts + i * 0.04
        elapsed = i * 0.04
        dist = i * 0.5
        lat = 33.53 + i * 0.00001
        lon = -86.62 + i * 0.00001
        speed = i * 0.5
        heading = 45.0
        lines.append(_build_data_row(t, elapsed, dist, lat, lon, speed, heading, 0.5, 10, ""))

    base_elapsed = 20 * 0.04
    base_dist = 20 * 0.5

    for lap in range(1, n_laps + 1):
        time_scale = 0.04 + (lap - 1) * 0.002  # each lap slightly slower
        for i in range(points_per_lap):
            t = base_ts + base_elapsed + i * time_scale
            elapsed = base_elapsed + i * time_scale
            dist = base_dist + i * 2.5
            lat = 33.53 + 0.0002 * np.sin(2 * np.pi * i / points_per_lap)
            lon = -86.62 + 0.0004 * np.cos(2 * np.pi * i / points_per_lap)
            speed = 30.0 + 10.0 * np.sin(2 * np.pi * i / 50)
            heading = (i * 360 / points_per_lap) % 360
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
                    0.3,
                    12,
                    str(lap),
                    lat_g,
                    lon_g,
                    yaw,
                )
            )
        base_elapsed += points_per_lap * time_scale
        base_dist += points_per_lap * 2.5

    csv_text = header + "\n".join(lines) + "\n"
    return csv_text.encode("utf-8")


@pytest.fixture
def synthetic_csv_bytes() -> bytes:
    """Return synthetic RaceChrono CSV bytes with 2 laps."""
    return build_synthetic_csv(n_laps=2)


@pytest.fixture
def synthetic_csv_bytes_3laps() -> bytes:
    """Return synthetic RaceChrono CSV bytes with 3 laps (needed for gains/consistency)."""
    return build_synthetic_csv(n_laps=3)


@pytest.fixture(autouse=True)
def _disable_auto_coaching() -> Generator[None, None, None]:
    """Disable auto-coaching on upload in all tests by default.

    Tests that specifically test auto-coaching should override this fixture.
    """
    with patch("backend.api.routers.sessions.trigger_auto_coaching"):
        yield


@pytest.fixture(autouse=True)
def _mock_auth() -> Generator[None, None, None]:
    """Override the auth dependency so all test requests are authenticated."""
    app.dependency_overrides[get_current_user] = lambda: _TEST_USER
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest_asyncio.fixture(autouse=True)
async def _test_db() -> AsyncGenerator[None, None]:
    """Create tables in in-memory SQLite and override get_db for each test."""
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with _test_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = _override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)

    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Yield an async HTTP test client wired to the FastAPI app.

    Clears the in-memory session store before and after each test.
    """
    clear_all()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    clear_all()
