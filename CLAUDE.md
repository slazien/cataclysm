# CLAUDE.md

## Project Context

Motorsport telemetry analysis and AI coaching platform (Python + Streamlit + Next.js/FastAPI). Primary language is Python. Use Python idioms and tooling by default.

## Communication Style

Before implementing changes, ask clarifying questions rather than writing long inline markdown plans. Be concise and action-oriented.

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

### 6. Autonomous Bug Fixing
- When given a bug report: just fix it. Don't ask for hand-holding
- Point at logs, errors, failing tests then resolve them
- Zero context switching required from the user
- Go fix failing CI tests without being told how

### 7. Never Underestimate Your Own Speed
- NEVER say "this is ambitious" or hedge about scope. You are Claude Code with parallel agents — you implement in hours, not weeks.
- Implement everything requested. No sandbagging, no "stretch goals", no artificial prioritization of scope you were asked to deliver.
- A human's 3-week deadline = massive runway for you. Just build it all.

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

Current state: Next.js + FastAPI on `nextjs-rewrite` branch (dev), merged to `main` for deployment. Streamlit MVP was removed.

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
ruff check cataclysm/ tests/ backend/  # lint errors
ruff format cataclysm/ tests/ backend/ # auto-format
mypy cataclysm/ backend/               # type checking (must pass with 0 errors)

# Debugging
pytest -x --tb=short                     # stop on first failure, short traceback
pytest --pdb                             # drop into debugger on failure
pytest -k "test_name" -v                 # run specific test verbosely
```

## Architecture

All processing converts time-domain GPS telemetry into **distance-domain** data (resampled at 0.7m intervals to match 25Hz GPS resolution).

**Data pipeline flow:**
```
RaceChrono CSV v3 → parser.py → engine.py → corners.py / delta.py → coaching.py → FastAPI backend → Next.js frontend
```

**Core modules in `cataclysm/`:**

- **parser.py** — Parses RaceChrono CSV v3 files. Uses positional column indexing (columns have duplicate names in RaceChrono format). Expects 8-line metadata header + 3 header rows (columns, units, sources). Validates GPS accuracy (<2.0m) and satellite count (>=6).
- **engine.py** — Splits parsed data into laps by `lap_number` transitions, resamples each to 0.7m distance steps via linear interpolation, computes `LapSummary` stats. Filters short laps (<80% of median distance) and anomalous laps (median ± 2*IQR on lap time).
- **corners.py** — Detects corners from heading rate (threshold ~1.0 deg/m, smoothed over 20m window). Merges corners within 30m, discards segments <15m. Extracts per-corner KPIs: apex type (early/mid/late), min speed, brake point, peak brake g, throttle commit point.
- **delta.py** — Computes delta-T between two resampled laps at each distance point.
- **coaching.py** — Sends structured telemetry context to Claude API (claude-sonnet-4-6) and parses JSON coaching reports with per-corner grades and improvement suggestions.
- **track_db.py** — Database of known tracks with official corner positions stored as % of lap distance. Currently has Barber Motorsports Park.
- **track_match.py** — GPS-based track auto-detection using session centroid vs known track coordinates.
- **sectors.py** — Sector time analysis reusing gains.py segment infrastructure.

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

1. **Ruff check** — zero lint errors: `ruff check cataclysm/ tests/ backend/`
2. **Ruff format** — auto-format first, then verify: `ruff format cataclysm/ tests/ backend/`
3. **Mypy** — zero type errors: `mypy cataclysm/ backend/`
4. **Tests** — all pass: `pytest tests/ backend/tests/ -v`
5. **Coverage** — write tests targeting as close to 100% coverage as realistically possible. Every new module needs a companion test file. Test edge cases, error paths, and boundary conditions, not just the happy path.

**CRITICAL: Fix ALL errors, including pre-existing ones.** Never dismiss errors as "pre-existing" and move on. If mypy, ruff, or tests show failures — even from code you didn't write — fix them immediately. Zero errors means zero errors, no exceptions.

## Testing Philosophy

- Every new module gets a `tests/test_<module>.py` companion
- Test edge cases: empty inputs, single-element inputs, None values, boundary conditions
- Use synthetic data fixtures in `conftest.py` — never depend on real session files in tests
- Mock external APIs (Claude API) to keep tests fast and deterministic
- Run `pytest --cov=cataclysm --cov-report=term-missing` to find untested lines and fill gaps

## Frontend QA Testing

**Always QA test frontend changes before marking them done.** Backend unit tests alone are not enough — the frontend must be functional and visually correct.

- After implementing frontend changes, use a browser automation agent (Playwright MCP) to verify every affected tab and interaction
- Check all tabs render without errors (no blank screens, no console errors, no "No data available" when data exists)
- Verify data flows end-to-end: upload CSVs → session appears in sidebar → all tabs show correct data
- Fix all critical and major bugs before committing — don't leave broken UI for the user to discover
- Common failure modes to check:
  - API response envelope mismatches (backend wraps data in `{session_id, data: {...}}` — frontend must unwrap)
  - Type/field name mismatches between backend responses and frontend TypeScript types
  - Charts rendering with empty or undefined data
  - File upload edge cases (large files, multiple files)
- The frontend should be beautiful and provide great UX — not just "technically working"

## Deployment (Railway)

The app is deployed on Railway (3 services: PostgreSQL, backend, frontend).

- **Railway auto-deploys from the `main` branch.** After committing to `nextjs-rewrite`, always merge to `main` and push for changes to go live.
- Railway project: `cataclysm` on railway.com
- Frontend URL: `https://frontend-production-edca.up.railway.app`
- Backend URL: `https://backend-production-4c97.up.railway.app`
- Backend `PORT=8000` is explicitly set (Railway assigns dynamic ports otherwise — must match `BACKEND_URL` in frontend)
- Frontend connects to backend via Railway private network: `http://backend.railway.internal:8000`
- `.railwayignore` controls what Railway CLI uploads (mirrors `.dockerignore`)
- **CRLF warning**: Railway Docker builds fail on Windows CRLF line endings. Always ensure `.dockerignore`, `railway.json`, and Dockerfiles have LF endings.

## Workflow

- Always ask all clarifying questions before making assumptions
- Use agent teams wherever possible for parallel work
- Always commit and push after making changes. Merge `nextjs-rewrite` → `main` for Railway deployment. Do not wait to be asked.

## Git & GitHub

- When asked to push to GitHub, confirm the correct remote URL first. The personal repo is on github.com, NOT github.intuit.com.
- Development branch: `nextjs-rewrite`. Production branch: `main`.

## File Operations

- When creating zip/compressed archives, exclude files over 50MB (especially model checkpoints, .pt, .bin files) and use Python's zipfile module as fallback since zip may not be installed.

## Code Review

- When exploring or reviewing code, verify you are analyzing the correct directory. Check for nested/scaffold copies and confirm the production code path before reporting findings.

## Environment

- `ANTHROPIC_API_KEY` env var required for AI coaching features
- `NEXTAUTH_SECRET` shared between frontend and backend for JWT validation
- `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` for Google OAuth (NextAuth.js v5)
- `DATABASE_URL` PostgreSQL connection string (backend, uses `postgresql+asyncpg://`)
- `BACKEND_URL` set on frontend service (Railway private network URL)
- `CORS_ORIGINS` on backend must be valid JSON array, e.g. `["https://frontend-production-edca.up.railway.app"]`
