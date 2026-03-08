# Solver Improvements — Scoped Action List

> Phase 2 output from multi-model solver review (2026-03-08)
> Sources: `solver_review_grip_findings.md`, `solver_review_velocity_findings.md`,
> `solver_review_corner_findings.md`, `solver_review_curvature_findings.md`

## Classification

### 🔴 Critical Bugs (formula errors affecting output)

| ID | Issue | Source | File | Impact | Effort |
|----|-------|--------|------|--------|--------|
| **BUG-1** | `normal_scale` (vertical curvature) applied to power-limited acceleration. Engine thrust is drivetrain-limited, not normal-force-limited. Only grip-limited accel should be scaled. | 🔴 Codex + 🔵 Claude | `velocity_profile.py:263-265` | Overestimates power-limited acceleration on compressions, underestimates on crests. Affects all tracks with elevation changes. | Low (~5 lines) |

### 🟡 Material Improvements (>1% lap time or accuracy impact)

| ID | Issue | Source | File | Impact | Effort |
|----|-------|--------|------|--------|--------|
| **IMP-1** | Double-counting load sensitivity for calibrated params. Telemetry-derived `max_lateral_g` (p95) already includes real load transfer effects. Applying power-law correction on top may over-penalize. | 🔴 Codex | `velocity_profile.py:140-155` | Could underestimate optimal speed by 2-5% on high-CG vehicles | Medium |
| **IMP-2** | Wire banking corrections into pipeline. `apply_banking_to_mu_array()` exists with tests but is never called. `track_db.py` already has `banking_deg` data per corner. | Phase 0 audit | `pipeline.py` + `banking.py` | Missing grip correction on banked corners (e.g., Road Atlanta T12, Barber T5) | Low-Medium |
| **IMP-3** | Wire linked corner grouping. `detect_linked_corners()` exists but unused. Chicanes/esses are analysed as individual corners when they should be grouped. | Phase 0 audit + 🟡 Gemini | `pipeline.py` + `linked_corners.py` | Better coaching insights for chicane complexes | Medium |

### 🟢 Nice-to-haves (<1% impact or documentation)

| ID | Issue | Source | File | Impact | Effort |
|----|-------|--------|------|--------|--------|
| DOC-1 | Document 50% denom floor as numerical guard, not physics | 🔴🔵 Both | `velocity_profile.py` | Clarity | Trivial |
| DOC-2 | Document dLT factor-of-2 simplification | 🟡 Gemini | `velocity_profile.py` | Clarity | Trivial |
| NTH-1 | Compound-dependent 0.3G lateral filter | 🔵 Claude | `grip_calibration.py` | Marginal grip accuracy | Low |
| NTH-2 | Brake point G-threshold (e.g., -0.2G) vs onset detection | 🟡 Gemini | `optimal_comparison.py` | Robustness | Low |
| NTH-3 | ICP lap alignment before multi-lap averaging | 🟡 Gemini | `curvature_averaging.py` | ~1-2m apex accuracy | Medium |
| NTH-4 | Wire tire warmup factor for lap 1 analysis | Phase 0 audit | `pipeline.py` + `grip_calibration.py` | Lap 1 accuracy | Medium |

### ⏸️ Deferred (need data we don't have or too complex)

| ID | Issue | Source | Why Deferred |
|----|-------|--------|--------------|
| DEF-1 | GGGV surface (speed-dependent envelope) | 🔴 Codex | Dead code exists (`build_ggv_surface`). Requires per-speed grip data we don't have. |
| DEF-2 | Trail braking model (combined braking+cornering) | Research doc | Requires slip-angle data (not in GPS telemetry) |
| DEF-3 | Tire degradation over session | Research doc | Requires multi-session tire data |
| DEF-4 | Clothoid curvature for canonical track reference | 🟡 Gemini | Current spline approach is appropriate for coaching |
| DEF-5 | Allow calibration to lower grip (not just raise) | 🔵 Claude | Complex UX implications — user might not understand why optimal got slower |
| DEF-6 | Tire-specific friction ellipse exponent | 🔵 Claude | Needs per-tire test data |

---

## Prioritised Implementation Order

### Phase 3.1: Fix BUG-1 (normal_scale on power accel) — MUST DO
- **What**: Move `normal_scale` application to before the `min(accel_g, power_accel_g)`, applying only to `accel_g`
- **Test**: Existing tests should catch if output changes. Add explicit test for compression + power-limited scenario.
- **Cache**: Bump `PHYSICS_CODE_VERSION`

### Phase 3.2: Fix IMP-1 (load sensitivity double-counting) — SHOULD DO
- **What**: Skip or reduce load sensitivity correction when `params.calibrated == True`
- **Options**:
  a. Skip entirely for calibrated params (simplest)
  b. Apply half correction for calibrated (compromise)
  c. Apply only when `mu_array` is not provided (per-corner mu already reflects local load)
- **Decision point**: Need user input on which option. Option (a) is cleanest.
- **Cache**: Bump `PHYSICS_CODE_VERSION`

### Phase 3.3: Wire IMP-2 (banking corrections) — SHOULD DO
- **What**: Call `apply_banking_to_mu_array()` with corner banking_deg data before solver
- **Where**: `pipeline.py`, after mu_array construction, before `compute_optimal_profile()`
- **Data**: `track_db.py` already has per-corner `banking_deg`
- **Cache**: Bump `PHYSICS_CODE_VERSION`

### Phase 3.4: Wire IMP-3 (linked corners) — SHOULD DO
- **What**: Call `detect_linked_corners()` after optimal profile, tag corners with `linked_group_id`
- **Where**: `pipeline.py`, after corner detection
- **API**: Expose `linked_group_id` in corner API response
- **Cache**: No cache impact (post-processing only)

### Phase 3.5: Documentation (DOC-1, DOC-2) — QUICK WINS
- Add docstring comments explaining the 50% floor and dLT simplification
- No code changes, no cache bump

### Phase 3.6: Optional improvements (NTH-1 through NTH-4) — IF TIME
- Prioritise NTH-2 (brake threshold) and NTH-1 (compound-dependent filter) as low-effort wins

---

## Go/No-Go Assessment

| ID | Go? | Rationale |
|----|-----|-----------|
| BUG-1 | ✅ Go | Real bug, affects all tracks with elevation. Low effort. |
| IMP-1 | ✅ Go (option a or c) | Logical inconsistency. Need user decision on approach. |
| IMP-2 | ✅ Go | Dead code with existing tests. Data available. |
| IMP-3 | ✅ Go | Dead code with existing tests. Improves coaching. |
| DOC-1/2 | ✅ Go | Trivial effort. |
| NTH-1-4 | ⏸️ Stretch | Do if time permits after main items. |
| DEF-1-6 | ❌ No-go | Data or complexity barriers. |

---

## Breaking Changes & Cache

- BUG-1, IMP-1, IMP-2 all change solver output → **MUST bump `PHYSICS_CODE_VERSION`**
- IMP-3 is post-processing → no cache impact
- Combine all solver changes into a single `PHYSICS_CODE_VERSION` bump
- File: `backend/api/services/db_physics_cache.py`

---

## Phase 3.7: Comprehensive Per-Corner QA — MANDATORY

> Added per user request: validate solver output makes physical sense for HPDE3 driver.

### Method
For each track with sessions, pick the best session (highest session score). Trace through every corner:
1. **Min actual vs min optimal speed** — optimal should always be ≥ actual (driver hasn't exceeded physics limit). If optimal < actual, something is wrong (curvature overestimate, mu too low, etc.)
2. **Speed gap magnitude** — for HPDE3 driver, typical gaps 3-15 mph per corner. Gaps >25 mph in a single corner are suspicious.
3. **Corner chains** — linked corners (chicanes/esses) should have speeds that make sense together. Speed between linked corners shouldn't drop to near-zero.
4. **Lap time gap** — total optimal should be 5-15% faster than actual for HPDE3. <3% = model too conservative. >20% = model too aggressive.
5. **Brake gaps** — should be 0-50m (HPDE3 brakes early). Negative brake gaps = something wrong.

### Tracks to validate
- All tracks with sessions in the system

### Fix loop
Keep fixing until all corners make physical sense. Document any fixes made.
