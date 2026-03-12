# Session TODO — 2026-03-11 (Per-Corner Braking Calibration)

## Implementation
- [x] 1. Add per-corner braking calibration extraction in `cataclysm/grip_calibration.py`
- [x] 2. Add `decel_array` support to the velocity solver backward pass
- [x] 3. Thread `decel_array` through `compute_optimal_profile()`
- [x] 4. Add braking calibration collection and decel-array building in `pipeline.py`
- [x] 5. Wire best-lap-inclusive braking calibration into optimal profile computation

## Verification
- [x] 6. Run targeted grip calibration, velocity profile, and pipeline tests
- [x] 7. Run repo quality gates relevant to the touched modules
- [x] 8. Run code review, update lessons, commit, and push `temp/per-corner-braking-calibration`

# Session TODO — 2026-03-12 (Per-Corner Braking Calibration QA Fixes)

## Implementation
- [x] 1. Fix braking-zone masking so in-corner brake onset uses local corner geometry instead of wrap heuristics
- [x] 2. Exclude the target/best lap from braking calibration telemetry
- [x] 3. Add regressions for in-corner and long-corner braking-zone handling in unit and pipeline tests

## Verification
- [x] 4. Re-run `ruff`, `dmypy`, targeted physics tests, and full regression
- [x] 5. Re-run real-session QA against `origin/staging` and quantify solver impact across the local corpus

# Session TODO — 2026-03-12 (Physics Cache Version Bump)

## Implementation
- [x] 1. Version the in-memory physics cache keys so old warmed results stop being reused
- [x] 2. Bump the shared physics code version used by the DB-backed cache
- [x] 3. Update cache tests for the new key shape and old-version miss behavior

## Verification
- [x] 4. Re-run lint, type-checks, and targeted cache tests
- [x] 5. Re-run the full backend/unit regression suite and push the branch

# Session TODO — 2026-03-10 (Corner Enrichment Accuracy)

## Implementation
- [x] 1. Fix character detector windowing + thresholds + decel fallback
- [x] 2. Fix corner type classifier thresholds and complex fallback behavior
- [x] 3. Improve elevation trend with multi-lap altitude smoothing
- [x] 4. Relax camber detector filters and sample requirements
- [x] 5. Harden blind detector against altitude noise
- [x] 6. Improve coaching-note gating and templates

## Verification
- [x] 7. Run targeted unit tests for character/classifier/elevation/camber/blind/notes
- [x] 8. Run full quality gates (ruff, mypy, pytest)
- [x] 9. Commit, merge into `staging`, push, and validate in browser on staging

# Session TODO — 2026-03-05

## Frontend UI
- [ ] 1. Move "vs Optimal" time inline with Turn header (CornerDetailPanel + CornerQuickCard)
- [ ] 2. Add `hoveredBrakeLap` to analysisStore for cross-chart state
- [ ] 3. BrakeConsistency: hover handler → set hoveredBrakeLap, draw highlight ring
- [ ] 4. CornerSpeedOverlay: read hoveredBrakeLap → highlight lap line + vertical brake marker

## Coaching
- [ ] 5. Update coaching prompts to avoid "mechanically sounding" advice
- [ ] 6. Add coaching progress indicator with ETA (backend timing + frontend UI)

## Quality Gates
- [ ] 7. Commit + push all changes
- [ ] 8. Visual QA via Playwright
- [ ] 9. Code review agent
