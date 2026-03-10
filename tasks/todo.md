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
- [ ] 9. Commit, merge into `staging`, push, and validate in browser on staging

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
