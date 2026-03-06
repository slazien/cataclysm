# Numerical Trust Hardening

## Codex-implemented (verified)
- [x] Read `CLAUDE.md` before continuing implementation
- [x] Remove accidental `.venv-codex` and switch back to the existing `./.venv`
- [x] Confirm `./.venv` has required Python dependencies for verification
- [x] Stabilize LIDAR cache identity so altitude traces cannot collide across sessions
- [x] Preserve full `VehicleParams` when applying grip calibration
- [x] Keep optimal-model calibration independent from the lap being evaluated
- [x] Add invalid-optimal detection to optimal comparison responses
- [x] Score GPS quality from raw normalized telemetry instead of already-filtered rows
- [x] Prevent majority partial laps from becoming the best lap
- [x] Recompute per-lap apex distance from the actual lap apex
- [x] Use real lap numbers for degradation slope fitting
- [x] Mark consistency metrics as insufficient-data instead of implying false certainty internally

## Claude-implemented (continuation)
- [x] Fix CornerSpeedGapPanel: warning banner for invalid optimal, remove "ahead of model" messaging
- [x] Fix help text: chart.speed-gap, metric.optimal-lap, section.score-breakdown, chart.gg-diagram
- [x] Surface consistency insufficient-data states: SessionDashboard + MetricsGrid show "Low sample" warnings
- [x] Stop manufacturing IMU traces: nullable `lateral_g`/`longitudinal_g` through full stack
  - [x] Frontend types: `number[] | null`
  - [x] BrakeThrottle.tsx: null guards + "unavailable" fallback
  - [x] CornerSpeedOverlay.tsx: null guards
  - [x] LapReplay.tsx: optional chaining
  - [x] Backend parser: stop fillna on missing IMU columns
  - [x] Backend engine: skip channels with <2 finite points
  - [x] Backend schemas: nullable fields
  - [x] Backend routers: return None for missing traces
- [x] Priority time cost bounding: Pydantic validator + deterministic cap from corner gains (Codex)
- [x] Fix pre-existing textUtils bold title extraction (strip trailing punctuation in bold markers)
- [x] Fix pre-existing ruff errors: slowapi stub naming, pymap3d unused var

## Quality gates
- [x] ruff format + ruff check: clean (0 errors)
- [x] mypy (dmypy): clean (0 errors in 155 files)
- [x] pytest: 2654/2654 passed
- [x] vitest: 466/466 passed (including fixed pre-existing failures)
- [x] Code review agent: dispatched, awaiting results
- [ ] Playwright QA for changed frontend surfaces
- [ ] Commit + push

## Review
- Code review agent running on full diff (~1400 lines across 48 files)
