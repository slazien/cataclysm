#!/usr/bin/env python3
"""Seed the demo session CSV into PostgreSQL.

One-time script to insert the demo Barber Motorsports Park session into the
database so it can be rehydrated at backend startup.  Safe to run multiple
times (upserts).

Usage:
    DATABASE_URL=postgresql+asyncpg://... python scripts/seed_demo_session.py

If DATABASE_URL is not set, falls back to the default local dev database.
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

# Ensure project root on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

DEMO_CSV = (
    PROJECT_ROOT
    / "data"
    / "session"
    / "barber_motorsports_park"
    / "session_20260222_162404_barber_motorsports_park_v3.csv"
)


async def main() -> None:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from backend.api.services.demo_session import DEMO_SESSION_ID, DEMO_USER_ID

    db_url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://cataclysm:cataclysm@localhost:5432/cataclysm",
    )
    engine = create_async_engine(db_url, echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    if not DEMO_CSV.exists():
        print(f"ERROR: Demo CSV not found at {DEMO_CSV}")
        sys.exit(1)

    csv_bytes = DEMO_CSV.read_bytes()
    filename = DEMO_CSV.name
    print(f"Read {len(csv_bytes):,} bytes from {filename}")

    async with async_session() as db:
        # Ensure __demo__ user exists (FK constraint on sessions.user_id)
        existing_user = await db.execute(
            text("SELECT id FROM users WHERE id = :uid"),
            {"uid": DEMO_USER_ID},
        )
        if existing_user.scalar_one_or_none() is None:
            await db.execute(
                text(
                    "INSERT INTO users (id, email, name, skill_level, role) "
                    "VALUES (:id, :email, :name, :skill, :role)"
                ),
                {
                    "id": DEMO_USER_ID,
                    "email": "demo@cataclysm.app",
                    "name": "Demo Driver",
                    "skill": "intermediate",
                    "role": "driver",
                },
            )
            print(f"Created user '{DEMO_USER_ID}'")

        # Upsert Session row
        existing_session = await db.execute(
            text("SELECT session_id FROM sessions WHERE session_id = :sid"),
            {"sid": DEMO_SESSION_ID},
        )
        if existing_session.scalar_one_or_none() is None:
            await db.execute(
                text(
                    "INSERT INTO sessions "
                    "(session_id, user_id, track_name, session_date, file_key, n_laps) "
                    "VALUES (:sid, :uid, :track, :sdate, :fkey, :nlaps)"
                ),
                {
                    "sid": DEMO_SESSION_ID,
                    "uid": DEMO_USER_ID,
                    "track": "Barber Motorsports Park",
                    "sdate": datetime(2026, 2, 22, 16, 24, 4, tzinfo=UTC),
                    "fkey": filename,
                    "nlaps": 0,  # Will be computed at startup rehydration
                },
            )
            print(f"Inserted session '{DEMO_SESSION_ID}'")
        else:
            print(f"Session '{DEMO_SESSION_ID}' already exists")

        # Upsert SessionFile row (raw CSV bytes for rehydration)
        existing_file = await db.execute(
            text("SELECT session_id FROM session_files WHERE session_id = :sid"),
            {"sid": DEMO_SESSION_ID},
        )
        if existing_file.scalar_one_or_none() is None:
            await db.execute(
                text(
                    "INSERT INTO session_files (session_id, filename, csv_bytes) "
                    "VALUES (:sid, :fname, :csv)"
                ),
                {
                    "sid": DEMO_SESSION_ID,
                    "fname": filename,
                    "csv": csv_bytes,
                },
            )
            print(f"Inserted session file ({len(csv_bytes):,} bytes)")
        else:
            # Update CSV bytes in case they changed
            await db.execute(
                text(
                    "UPDATE session_files SET csv_bytes = :csv, filename = :fname "
                    "WHERE session_id = :sid"
                ),
                {
                    "sid": DEMO_SESSION_ID,
                    "fname": filename,
                    "csv": csv_bytes,
                },
            )
            print(f"Updated session file ({len(csv_bytes):,} bytes)")

        await db.commit()
        print("Done! Demo session seeded successfully.")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
