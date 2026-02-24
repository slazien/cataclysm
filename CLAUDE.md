# CLAUDE.md

## Workflow Orchestration

### 1. Plan Mode Default
- Enter plan mode for ANY non-trivial task (3+ steps or architectural decisions) - If something goes sideways, STOP and re-plan immediately - don't keep pushing - Use plan mode for verification steps, not just building
- Write detailed specs upfront to reduce ambiguity

### 2. Subagent Strategy
Use subagents liberally to keep main context window clean
- Offload research, exploration, and parallel analysis to subagents
- For complex problems, throw more compute at it via subagents
- One task per subagent for focused execution

### 3. Self-Improvement Loop
- After ANY correction from the user: update `tasks/lessons.md with the pattern
- Write rules for yourself that prevent the same mistake
- Ruthlessly iterate on these lessons until mistake rate drops
- Review lessons at session start for relevant project

### 4. Verification Before Done
- Never mark a task complete without proving it works
- Diff behavior between main and your changes when relevant
- Ask yourself: "Would a staff engineer approve this?"
- Run tests, check logs, demonstrate correctness

### 5. Demand Elegance (Balanced)
- For non-trivial changes: pause and ask "is there a more elegant way?"
- If a fix feels hacky: "Knowing everything I know now, implement the elegant solution" Skip this for simple, obvious fixes - don't over-engineer
- Challenge your own work before presenting it

### 6. Autonomous Bug Fizing
- When given a bug report: just fix it. Don't ask for hand-holding
- Point at logs, errors, failing tests then resolve them
- Zero context switching required from the user
- Go fix failing CI tests without being told how

## Task Management

1. *Plan First*: Write plan to tasks/todo.md with checkable items
2. *Verify Plan*: Check in before starting implementation
3. *Track Progress*: Mark items complete as you go
4. *Explain Changes*: High-level summary at each step
5. *Document Results*: Add review section to tasks/todo.md`
6. *Capture Lessons*: Update tasks/lessons.md after corrections

## Core Principles

- *Simplicity First*: Make every change as simple as possible. Impact minimal code. - *No Laziness*: Find root causes. No temporary fixes. Senior developer standards.
- *Minimat Impact*: Changes should only touch what's necessary. Avoid introducing bugs.

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Cataclysm is an AI-powered motorsport telemetry analysis and coaching platform for track day drivers. It ingests RaceChrono CSV v3 exports, processes them in the distance domain, detects corners, and generates AI coaching reports via the Claude API.

Current state: Streamlit MVP on branch `claude/review-track-plan-FQmfe` (main branch only has CSV data files). Next.js + FastAPI rewrite in progress on `nextjs-rewrite` branch.

## Virtual Environment

**Always work inside the project venv.** Never install packages globally.

```bash
# Create venv (first time only)
python3 -m venv .venv

# Activate venv (every session)
source .venv/bin/activate

# Install all deps
pip install -e ".[dev]"
pip install fastapi uvicorn pydantic-settings sqlalchemy asyncpg alembic httpx pytest-asyncio
```

The `.venv/` directory is gitignored. All `pip install`, `pytest`, `ruff`, `mypy`, and `streamlit` commands assume the venv is active.

## Commands

```bash
# Install dependencies (venv must be active)
pip install -e ".[dev]"

# Run the Streamlit app
streamlit run app.py

# Run tests
pytest
pytest tests/test_engine.py              # single module
pytest tests/test_engine.py::test_name   # single test
pytest --cov=cataclysm --cov-report=term-missing  # with coverage

# Backend tests
pytest backend/tests/ -v

# Run backend dev server
uvicorn backend.api.main:app --reload --port 8000

# Linting, formatting, and type checking — run ALL THREE before committing
ruff check cataclysm/ tests/ app.py backend/  # lint errors
ruff format cataclysm/ tests/ app.py backend/ # auto-format
mypy cataclysm/ app.py backend/               # type checking (must pass with 0 errors)

# Debugging
pytest -x --tb=short                     # stop on first failure, short traceback
pytest --pdb                             # drop into debugger on failure
pytest -k "test_name" -v                 # run specific test verbosely
streamlit run app.py --logger.level=debug  # verbose Streamlit logging
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

## Architecture (Next.js Rewrite)

The app is being rewritten from Streamlit to Next.js + FastAPI:

**Frontend** (Next.js 14+, TypeScript, Tailwind, D3.js):
- Port 3000
- Pages: /, /sessions, /analysis/[id]
- 5 tabs: Overview, Speed Trace, Corners, AI Coach, Trends
- 22 D3 chart components
- State: Zustand (UI) + TanStack Query (API)

**Backend** (FastAPI):
- Port 8000
- Routes: /api/sessions/*, /api/coaching/*, /api/trends/*, /api/tracks/*
- Services: pipeline.py (wraps cataclysm/), session_store.py, serializers.py
- In-memory session store (PostgreSQL ready for future)

**Development:**
```bash
# Backend
source .venv/bin/activate
uvicorn backend.api.main:app --reload --port 8000

# Frontend
cd frontend && npm run dev

# Docker (all services)
docker compose up
```

## Key Data Types

All structured data uses **dataclasses**: `ParsedSession`, `SessionMetadata`, `LapSummary`, `ProcessedSession`, `Corner`, `CoachingReport`, `CornerGrade`, `CoachingContext`. Type alias `AllLapCorners = dict[int, list[Corner]]`.

## Code Conventions

- Python 3.11+, type hints required on all functions (mypy `disallow_untyped_defs`)
- Line length: 100 chars (ruff)
- Ruff rules: E, F, W, I (isort), N, UP, B, SIM
- Module-level constants in UPPER_SNAKE_CASE (e.g., `RESAMPLE_STEP_M`, `MIN_CORNER_LENGTH_M`)
- All files start with `from __future__ import annotations`
- Test fixtures in `tests/conftest.py` generate synthetic RaceChrono CSV data

## Quality Gates

All of these must pass before committing:

1. **Ruff check** — zero lint errors: `ruff check cataclysm/ tests/ app.py backend/`
2. **Ruff format** — auto-format first, then verify: `ruff format cataclysm/ tests/ app.py backend/`
3. **Mypy** — zero type errors: `mypy cataclysm/ app.py backend/`
4. **Tests** — all pass: `pytest tests/ backend/tests/ -v`
5. **Coverage** — write tests targeting as close to 100% coverage as realistically possible. Every new module needs a companion test file. Test edge cases, error paths, and boundary conditions, not just the happy path.

## Testing Philosophy

- Every new module gets a `tests/test_<module>.py` companion
- Test edge cases: empty inputs, single-element inputs, None values, boundary conditions
- Use synthetic data fixtures in `conftest.py` — never depend on real session files in tests
- Mock external APIs (Claude API) to keep tests fast and deterministic
- Run `pytest --cov=cataclysm --cov-report=term-missing` to find untested lines and fill gaps

## Workflow

- Always ask all clarifying questions before making assumptions
- Use agent teams wherever possible for parallel work
- Always commit and push after making changes — the app is deployed on Streamlit Cloud and serves from the remote branch.

## Environment

- `ANTHROPIC_API_KEY` env var required for AI coaching features
- Streamlit Cloud deployment config in `.streamlit/config.toml`
