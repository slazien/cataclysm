#!/usr/bin/env python3
"""Analyze actual output token usage from LLM usage events.

Run: python scripts/analyze_output_tokens.py
Requires: DATABASE_URL env var pointing to staging/prod Postgres.
"""

from __future__ import annotations

import os
import statistics

from sqlalchemy import create_engine, text


def main() -> None:
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("No DATABASE_URL. Set it to query production data.")
        return

    engine = create_engine(db_url)
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT output_tokens FROM llm_usage_events "
                "WHERE task = 'coaching_report' AND success = true "
                "ORDER BY event_timestamp DESC LIMIT 200"
            )
        ).fetchall()

    if not rows:
        print("No coaching_report events found.")
        return

    tokens = [r[0] for r in rows]
    print(f"Samples: {len(tokens)}")
    print(f"Min:  {min(tokens)}")
    print(f"P50:  {statistics.median(tokens):.0f}")
    print(f"P75:  {statistics.quantiles(tokens, n=4)[2]:.0f}")
    print(f"P90:  {statistics.quantiles(tokens, n=10)[8]:.0f}")
    print(f"P95:  {statistics.quantiles(tokens, n=20)[18]:.0f}")
    print(f"Max:  {max(tokens)}")
    print(f"Mean: {statistics.mean(tokens):.0f}")
    print(f"StdDev: {statistics.stdev(tokens):.0f}")

    p95 = statistics.quantiles(tokens, n=20)[18]
    recommended = int(p95 * 1.10)
    print(f"\nRecommended max_tokens: {recommended} (p95 + 10% buffer)")
    print("Current max_tokens: 8192")
    print(f"Potential savings: {(8192 - recommended) / 8192 * 100:.0f}% of output cost")


if __name__ == "__main__":
    main()
