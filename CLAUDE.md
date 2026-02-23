# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Cataclysm is an AI-powered motorsport telemetry analysis and coaching platform for track day drivers. It ingests RaceChrono CSV v3 exports, processes them in the distance domain, detects corners, and generates AI coaching reports via the Claude API.

Current state: Streamlit MVP on branch `claude/review-track-plan-FQmfe` (main branch only has CSV data files).

## Commands

```bash
# Install dependencies
pip install -e ".[dev]"

# Run the Streamlit app
streamlit run app.py

# Run tests
pytest
pytest tests/test_engine.py              # single module
pytest tests/test_engine.py::test_name   # single test
pytest --cov=cataclysm --cov-report=term-missing  # with coverage (90% required)

# Linting and type checking
ruff check cataclysm/ tests/
ruff format --check cataclysm/ tests/
mypy cataclysm/
```

## Architecture

All processing converts time-domain GPS telemetry into **distance-domain** data (resampled at 0.7m intervals to match 25Hz GPS resolution).

**Data pipeline flow:**
```
RaceChrono CSV v3 → parser.py → engine.py → corners.py / delta.py → coaching.py → charts.py → app.py (Streamlit UI)
```

**Core modules in `cataclysm/`:**

- **parser.py** — Parses RaceChrono CSV v3 files. Uses positional column indexing (columns have duplicate names in RaceChrono format). Expects 8-line metadata header + 3 header rows (columns, units, sources). Validates GPS accuracy (<2.0m) and satellite count (>=6).
- **engine.py** — Splits parsed data into laps by `lap_number` transitions, resamples each to 0.7m distance steps via linear interpolation, computes `LapSummary` stats. Filters short laps (<80% of median distance) and anomalous laps (median ± 2*IQR on lap time).
- **corners.py** — Detects corners from heading rate (threshold ~1.0 deg/m, smoothed over 20m window). Merges corners within 30m, discards segments <15m. Extracts per-corner KPIs: apex type (early/mid/late), min speed, brake point, peak brake g, throttle commit point.
- **delta.py** — Computes delta-T between two resampled laps at each distance point.
- **coaching.py** — Sends structured telemetry context to Claude API (claude-sonnet-4-6) and parses JSON coaching reports with per-corner grades and improvement suggestions.
- **track_db.py** — Database of known tracks with official corner positions stored as % of lap distance. Currently has Barber Motorsports Park.
- **charts.py** — Plotly chart builders: speed traces, delta-T, g-force scatter, track map, lap times bar chart, corner KPI table.

**Entry point:** `app.py` — Streamlit app that orchestrates the full pipeline. Auto-loads CSV files from the working directory or accepts uploads.

## Key Data Types

All structured data uses **dataclasses**: `ParsedSession`, `SessionMetadata`, `LapSummary`, `ProcessedSession`, `Corner`, `CoachingReport`, `CornerGrade`, `CoachingContext`. Type alias `AllLapCorners = dict[int, list[Corner]]`.

## Code Conventions

- Python 3.11+, type hints required on all functions (mypy `disallow_untyped_defs`)
- Line length: 100 chars (ruff)
- Ruff rules: E, F, W, I (isort), N, UP, B, SIM
- Module-level constants in UPPER_SNAKE_CASE (e.g., `RESAMPLE_STEP_M`, `MIN_CORNER_LENGTH_M`)
- All files start with `from __future__ import annotations`
- Test fixtures in `tests/conftest.py` generate synthetic RaceChrono CSV data

## Workflow

- Always commit and push after making changes — the app is deployed on Streamlit Cloud and serves from the remote branch.

## Environment

- `ANTHROPIC_API_KEY` env var required for AI coaching features
- Streamlit Cloud deployment config in `.streamlit/config.toml`
