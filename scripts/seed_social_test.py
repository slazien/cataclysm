"""Seed the production database with fake users and redistribute sessions for social feature QA.

Creates 3 test users, redistributes existing sessions among them,
extracts corner KPIs from the backend API, inserts corner_records,
and computes corner kings.

Usage:
    python scripts/seed_social_test.py \
        --db-url "postgresql://user:pass@host:port/db" \
        --backend-url "https://backend-production-4c97.up.railway.app"

    python scripts/seed_social_test.py --db-url "..." --backend-url "..." --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any

import asyncpg
import httpx

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MPH_TO_MPS = 0.44704

TEST_USER_IDS = ["test-alex", "test-jordan", "test-morgan"]

FAKE_USERS: list[dict[str, Any]] = [
    {
        "id": "test-alex",
        "email": "alex@test.cataclysm.dev",
        "name": "Alex Racer",
        "skill_level": "advanced",
        "role": "driver",
    },
    {
        "id": "test-jordan",
        "email": "jordan@test.cataclysm.dev",
        "name": "Jordan Swift",
        "skill_level": "intermediate",
        "role": "driver",
    },
    {
        "id": "test-morgan",
        "email": "morgan@test.cataclysm.dev",
        "name": "Morgan Apex",
        "skill_level": "intermediate",
        "role": "driver",
    },
]

# Track name -> (expected_count, {index_list_alex}, {index_list_jordan}, {index_list_morgan})
TRACK_DISTRIBUTION: dict[str, tuple[int, list[int], list[int], list[int]]] = {
    "Barber Motorsports Park": (
        20,
        list(range(5, 13)),  # Alex: 5-12  (8 sessions)
        list(range(0, 5)) + list(range(13, 18)),  # Jordan: 0-4, 13-17  (10 sessions)
        [18, 19],  # Morgan: 18-19  (2 sessions)
    ),
    "Roebling Road Raceway": (
        8,
        [1, 3, 5],  # Alex
        [0, 2, 4],  # Jordan
        [6, 7],  # Morgan
    ),
    "Atlanta Motorsports Park": (
        4,
        [2, 3],  # Alex
        [1],  # Jordan
        [0],  # Morgan
    ),
}

API_HEADERS = {"X-Test-User-Id": "dev-user"}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _log(prefix: str, msg: str) -> None:
    print(f"  [{prefix}] {msg}")


def _normalize_db_url(url: str) -> str:
    """Ensure the URL uses plain postgresql:// scheme for asyncpg."""
    if url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return url


def _proportional_distribute(count: int) -> tuple[list[int], list[int], list[int]]:
    """Distribute indices proportionally: Alex ~40%, Jordan ~35%, Morgan ~25%."""
    alex_n = round(count * 0.40)
    jordan_n = round(count * 0.35)

    indices = list(range(count))
    alex_idx = indices[:alex_n]
    jordan_idx = indices[alex_n : alex_n + jordan_n]
    morgan_idx = indices[alex_n + jordan_n :]

    # Safety: ensure morgan gets at least what's left
    assert len(alex_idx) + len(jordan_idx) + len(morgan_idx) == count
    return alex_idx, jordan_idx, morgan_idx


def _get_distribution(track_name: str, actual_count: int) -> tuple[list[int], list[int], list[int]]:
    """Get index distribution for a track, falling back to proportional if count differs."""
    if track_name in TRACK_DISTRIBUTION:
        expected, alex_idx, jordan_idx, morgan_idx = TRACK_DISTRIBUTION[track_name]
        if actual_count == expected:
            return alex_idx, jordan_idx, morgan_idx
        _log(
            "SESSIONS",
            f"  WARNING: {track_name} has {actual_count} sessions "
            f"(expected {expected}), using proportional distribution",
        )

    return _proportional_distribute(actual_count)


# ---------------------------------------------------------------------------
# Phase 1: Create / upsert fake users
# ---------------------------------------------------------------------------


async def seed_users(conn: asyncpg.Connection, *, dry_run: bool) -> None:
    _log("USERS", "Creating / upserting 3 test users...")
    for user in FAKE_USERS:
        if dry_run:
            _log("USERS", f"  [DRY-RUN] Would upsert user {user['id']} ({user['name']})")
            continue

        await conn.execute(
            """
            INSERT INTO users (id, email, name, skill_level, role)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (id) DO UPDATE SET
                email = EXCLUDED.email,
                name = EXCLUDED.name,
                skill_level = EXCLUDED.skill_level,
                role = EXCLUDED.role
            """,
            user["id"],
            user["email"],
            user["name"],
            user["skill_level"],
            user["role"],
        )
        _log("USERS", f"  Upserted {user['id']} ({user['name']})")
    _log("USERS", "Done.")


# ---------------------------------------------------------------------------
# Phase 2: Clean up old test data
# ---------------------------------------------------------------------------


async def cleanup_test_data(conn: asyncpg.Connection, *, dry_run: bool) -> None:
    _log("CLEANUP", "Removing old test data...")

    tables_and_conditions = [
        ("corner_kings", "user_id LIKE 'test-%'"),
        ("corner_records", "user_id LIKE 'test-%'"),
    ]

    for table, condition in tables_and_conditions:
        if dry_run:
            count = await conn.fetchval(
                f"SELECT COUNT(*) FROM {table} WHERE {condition}"  # noqa: S608
            )
            _log("CLEANUP", f"  [DRY-RUN] Would delete {count} rows from {table}")
        else:
            result = await conn.execute(
                f"DELETE FROM {table} WHERE {condition}"  # noqa: S608
            )
            _log("CLEANUP", f"  Deleted from {table}: {result}")

    _log("CLEANUP", "Done.")


# ---------------------------------------------------------------------------
# Phase 3: Redistribute sessions
# ---------------------------------------------------------------------------


async def redistribute_sessions(
    conn: asyncpg.Connection, *, dry_run: bool
) -> dict[str, list[tuple[str, str]]]:
    """Reassign sessions to test users. Returns {track: [(session_id, user_id), ...]}."""
    _log("SESSIONS", "Loading sessions grouped by track...")

    rows = await conn.fetch(
        """
        SELECT session_id, track_name, session_date, user_id
        FROM sessions
        ORDER BY track_name, session_date ASC
        """
    )

    # Group by track
    tracks: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        tn = row["track_name"]
        tracks.setdefault(tn, []).append(dict(row))

    _log("SESSIONS", f"Found {len(rows)} sessions across {len(tracks)} tracks:")
    for tn, sessions in tracks.items():
        _log("SESSIONS", f"  {tn}: {len(sessions)} sessions")

    # Build assignment map: track -> [(session_id, assigned_user_id)]
    assignments: dict[str, list[tuple[str, str]]] = {}

    for track_name, sessions in tracks.items():
        # Sessions are already sorted by session_date ASC from the query
        count = len(sessions)
        alex_idx, jordan_idx, morgan_idx = _get_distribution(track_name, count)

        track_assignments: list[tuple[str, str]] = []
        for i, sess in enumerate(sessions):
            sid = sess["session_id"]
            if i in alex_idx:
                new_user = "test-alex"
            elif i in jordan_idx:
                new_user = "test-jordan"
            elif i in morgan_idx:
                new_user = "test-morgan"
            else:
                _log("SESSIONS", f"  WARNING: session index {i} not in any distribution bucket")
                continue

            track_assignments.append((sid, new_user))

            if dry_run:
                _log(
                    "SESSIONS",
                    f"  [DRY-RUN] {track_name} #{i}: {sid[:20]}... -> {new_user}",
                )
            else:
                await conn.execute(
                    "UPDATE sessions SET user_id = $1 WHERE session_id = $2",
                    new_user,
                    sid,
                )

        assignments[track_name] = track_assignments

    if not dry_run:
        # Summary
        for track_name, ta in assignments.items():
            user_counts: dict[str, int] = {}
            for _, uid in ta:
                user_counts[uid] = user_counts.get(uid, 0) + 1
            _log(
                "SESSIONS",
                f"  {track_name}: "
                + ", ".join(f"{uid}={cnt}" for uid, cnt in sorted(user_counts.items())),
            )

    _log("SESSIONS", "Done.")
    return assignments


# ---------------------------------------------------------------------------
# Phase 4: Extract corner data from API and insert corner_records
# ---------------------------------------------------------------------------


async def _fetch_session_gains(
    client: httpx.AsyncClient, backend_url: str, session_id: str
) -> dict[str, Any] | None:
    """Fetch /api/sessions/{id}/gains, return parsed JSON or None on failure."""
    url = f"{backend_url}/api/sessions/{session_id}/gains"
    try:
        resp = await client.get(url, headers=API_HEADERS, timeout=30.0)
        resp.raise_for_status()
        result: dict[str, Any] = resp.json()
        return result
    except (httpx.HTTPStatusError, httpx.RequestError, json.JSONDecodeError) as exc:
        _log("CORNERS", f"  WARNING: gains API failed for {session_id[:20]}...: {exc}")
        return None


async def _fetch_session_corners(
    client: httpx.AsyncClient, backend_url: str, session_id: str
) -> dict[str, Any] | None:
    """Fetch /api/sessions/{id}/corners/all-laps, return parsed JSON or None."""
    url = f"{backend_url}/api/sessions/{session_id}/corners/all-laps"
    try:
        resp = await client.get(url, headers=API_HEADERS, timeout=30.0)
        resp.raise_for_status()
        result: dict[str, Any] = resp.json()
        return result
    except (httpx.HTTPStatusError, httpx.RequestError, json.JSONDecodeError) as exc:
        _log("CORNERS", f"  WARNING: corners API failed for {session_id[:20]}...: {exc}")
        return None


def _parse_corner_number(segment_name: str) -> int | None:
    """Extract corner number from segment name like 'T5' -> 5."""
    name = segment_name.strip().upper()
    if name.startswith("T") and name[1:].isdigit():
        return int(name[1:])
    # Try pure numeric
    if name.isdigit():
        return int(name)
    return None


async def seed_corner_records(
    conn: asyncpg.Connection,
    client: httpx.AsyncClient,
    backend_url: str,
    assignments: dict[str, list[tuple[str, str]]],
    *,
    dry_run: bool,
) -> None:
    """For each assigned session, fetch corner data from API and insert corner_records."""
    _log("CORNERS", "Seeding corner records from API data...")

    total_sessions = sum(len(v) for v in assignments.values())
    processed = 0
    inserted_total = 0
    skipped = 0

    for track_name, session_list in assignments.items():
        _log("CORNERS", f"Processing track: {track_name} ({len(session_list)} sessions)")

        for session_id, user_id in session_list:
            processed += 1
            short_id = session_id[:20]

            # Fetch gains and corners in parallel
            gains_data, corners_data = await asyncio.gather(
                _fetch_session_gains(client, backend_url, session_id),
                _fetch_session_corners(client, backend_url, session_id),
            )

            if gains_data is None or corners_data is None:
                _log("CORNERS", f"  [{processed}/{total_sessions}] SKIP {short_id}... (API error)")
                skipped += 1
                continue

            # Parse gains: build {corner_number: {lap_number: sector_time_s}}
            data_envelope = gains_data.get("data", gains_data)
            consistency = data_envelope.get("consistency", {})
            segment_gains = consistency.get("segment_gains", [])

            corner_times: dict[int, dict[int, float]] = {}
            for sg in segment_gains:
                segment = sg.get("segment", {})
                if not segment.get("is_corner", False):
                    continue
                corner_num = _parse_corner_number(segment.get("name", ""))
                if corner_num is None:
                    continue
                lap_times = sg.get("lap_times_s", {})
                corner_times[corner_num] = {int(k): float(v) for k, v in lap_times.items()}

            # Parse corners/all-laps: build {lap_number: {corner_number: corner_data}}
            laps_envelope = corners_data.get("laps", corners_data)
            corner_details: dict[int, dict[int, dict[str, Any]]] = {}
            for lap_str, corners_list in laps_envelope.items():
                try:
                    lap_num = int(lap_str)
                except ValueError:
                    continue
                for corner in corners_list:
                    cn = corner.get("number")
                    if cn is not None:
                        corner_details.setdefault(lap_num, {})[int(cn)] = corner

            # Build insert rows (9 columns: includes consistency_cv)
            rows_to_insert: list[
                tuple[str, str, str, int, float, float, int, float | None, float | None]
            ] = []

            # Compute per-corner consistency CV (coefficient of variation of sector times)
            corner_cvs: dict[int, float | None] = {}
            for corner_num, lap_times in corner_times.items():
                times = list(lap_times.values())
                if len(times) >= 2:
                    mean = sum(times) / len(times)
                    if mean > 0:
                        variance = sum((t - mean) ** 2 for t in times) / len(times)
                        std = variance**0.5
                        corner_cvs[corner_num] = std / mean
                    else:
                        corner_cvs[corner_num] = None
                else:
                    corner_cvs[corner_num] = None

            for corner_num, lap_times in corner_times.items():
                consistency_cv = corner_cvs.get(corner_num)
                for lap_num, sector_time in lap_times.items():
                    # Get min_speed and brake_point from corner details
                    lap_corners = corner_details.get(lap_num, {})
                    corner_info = lap_corners.get(corner_num)

                    if corner_info is not None:
                        min_speed_mph = corner_info.get("min_speed_mph")
                        min_speed_mps = (
                            float(min_speed_mph) * MPH_TO_MPS if min_speed_mph is not None else 0.0
                        )
                        brake_point = corner_info.get("brake_point_m")
                        # Treat 0.0 as missing — real brake points are always positive
                        brake_point_m = (
                            float(brake_point)
                            if brake_point is not None and float(brake_point) > 0
                            else None
                        )
                    else:
                        # No detailed corner data for this lap — use defaults
                        min_speed_mps = 0.0
                        brake_point_m = None

                    rows_to_insert.append(
                        (
                            user_id,
                            session_id,
                            track_name,
                            corner_num,
                            min_speed_mps,
                            sector_time,
                            lap_num,
                            brake_point_m,
                            consistency_cv,
                        )
                    )

            if dry_run:
                _log(
                    "CORNERS",
                    f"  [{processed}/{total_sessions}] [DRY-RUN] "
                    f"{short_id}... -> {len(rows_to_insert)} corner records for {user_id}",
                )
            else:
                if rows_to_insert:
                    await conn.executemany(
                        """
                        INSERT INTO corner_records
                            (user_id, session_id, track_name, corner_number,
                             min_speed_mps, sector_time_s, lap_number, brake_point_m,
                             consistency_cv)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                        """,
                        rows_to_insert,
                    )
                _log(
                    "CORNERS",
                    f"  [{processed}/{total_sessions}] "
                    f"{short_id}... -> {len(rows_to_insert)} records for {user_id}",
                )

            inserted_total += len(rows_to_insert)

    _log("CORNERS", f"Done. Inserted {inserted_total} corner records, skipped {skipped} sessions.")


# ---------------------------------------------------------------------------
# Phase 5: Compute corner kings
# ---------------------------------------------------------------------------


async def compute_kings(conn: asyncpg.Connection, *, dry_run: bool) -> None:
    """For each (track, corner), find the user with the fastest sector_time_s and upsert kings."""
    _log("KINGS", "Computing corner kings...")

    if dry_run:
        rows = await conn.fetch(
            """
            SELECT cr.track_name, cr.corner_number,
                   cr.user_id, cr.sector_time_s, cr.session_id
            FROM corner_records cr
            WHERE cr.sector_time_s = (
                  SELECT MIN(cr2.sector_time_s)
                  FROM corner_records cr2
                  WHERE cr2.track_name = cr.track_name
                    AND cr2.corner_number = cr.corner_number
              )
            ORDER BY cr.track_name, cr.corner_number
            """
        )
        for row in rows:
            _log(
                "KINGS",
                f"  [DRY-RUN] {row['track_name']} T{row['corner_number']}: "
                f"{row['user_id']} ({row['sector_time_s']:.3f}s)",
            )
        _log("KINGS", f"  [DRY-RUN] Would upsert {len(rows)} corner kings")
        return

    # Clear existing kings for tracks that have test user corner records
    await conn.execute(
        """
        DELETE FROM corner_kings
        WHERE track_name IN (
            SELECT DISTINCT track_name FROM corner_records WHERE user_id LIKE 'test-%'
        )
        """
    )

    # Compute and insert kings: for each (track, corner), the user with min sector_time_s
    result = await conn.execute(
        """
        INSERT INTO corner_kings (track_name, corner_number, user_id, best_time_s, session_id)
        SELECT DISTINCT ON (cr.track_name, cr.corner_number)
               cr.track_name,
               cr.corner_number,
               cr.user_id,
               cr.sector_time_s,
               cr.session_id
        FROM corner_records cr
        ORDER BY cr.track_name, cr.corner_number, cr.sector_time_s ASC
        ON CONFLICT (track_name, corner_number) DO UPDATE SET
            user_id = EXCLUDED.user_id,
            best_time_s = EXCLUDED.best_time_s,
            session_id = EXCLUDED.session_id,
            updated_at = now()
        """
    )
    _log("KINGS", f"  Upserted kings: {result}")

    # Print summary
    kings = await conn.fetch(
        """
        SELECT track_name, corner_number, user_id, best_time_s
        FROM corner_kings
        ORDER BY track_name, corner_number
        """
    )
    current_track = ""
    for king in kings:
        if king["track_name"] != current_track:
            current_track = king["track_name"]
            _log("KINGS", f"  {current_track}:")
        _log(
            "KINGS",
            f"    T{king['corner_number']}: {king['user_id']} ({king['best_time_s']:.3f}s)",
        )

    _log("KINGS", "Done.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main(db_url: str, backend_url: str, *, dry_run: bool) -> None:
    db_url = _normalize_db_url(db_url)
    backend_url = backend_url.rstrip("/")

    print(f"\n{'=' * 60}")
    print("  Cataclysm Social Features — Database Seeder")
    print(f"{'=' * 60}")
    print(f"  DB:      {db_url[:40]}...")
    print(f"  API:     {backend_url}")
    print(f"  Dry run: {dry_run}")
    print(f"{'=' * 60}\n")

    conn = await asyncpg.connect(db_url, ssl="require")
    try:
        # Phase 1: Create users
        await seed_users(conn, dry_run=dry_run)
        print()

        # Phase 2: Clean up old test data
        await cleanup_test_data(conn, dry_run=dry_run)
        print()

        # Phase 3: Redistribute sessions
        assignments = await redistribute_sessions(conn, dry_run=dry_run)
        print()

        # Phase 4: Seed corner records from API
        async with httpx.AsyncClient() as client:
            await seed_corner_records(conn, client, backend_url, assignments, dry_run=dry_run)
        print()

        # Phase 5: Compute kings
        await compute_kings(conn, dry_run=dry_run)
        print()

    finally:
        await conn.close()

    print(f"\n{'=' * 60}")
    if dry_run:
        print("  DRY RUN COMPLETE — no changes were made")
    else:
        print("  SEEDING COMPLETE")
    print(f"{'=' * 60}\n")


def cli() -> None:
    parser = argparse.ArgumentParser(
        description="Seed production DB with fake users for social feature QA",
    )
    parser.add_argument(
        "--db-url",
        required=True,
        help="PostgreSQL connection URL (asyncpg-compatible)",
    )
    parser.add_argument(
        "--backend-url",
        required=True,
        help="Backend API base URL (e.g. https://backend-production-4c97.up.railway.app)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would happen without making changes",
    )
    args = parser.parse_args()
    asyncio.run(main(args.db_url, args.backend_url, dry_run=args.dry_run))


if __name__ == "__main__":
    cli()
