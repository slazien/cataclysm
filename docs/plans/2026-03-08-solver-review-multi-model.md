# Solver Review & Update — Multi-Model Workflow Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Audit the physics solver for correctness, identify remaining gaps, and implement improvements — using Gemini + Codex + Claude in tandem via `octo:multi` / `octo:discover`.

**Architecture:** Four-phase Double Diamond workflow. Phase 1 (Discover) uses multi-model research to validate current physics. Phase 2 (Grasp) synthesizes findings into a scoped improvement list. Phase 3 (Dev) implements changes. Phase 4 (Review) multi-model code review.

**Tech Stack:** Python 3.11+, NumPy, SciPy, pytest. Octo plugin for multi-model orchestration.

**Prior work:** `tasks/velocity_model_research.md` (60+ sources), `docs/plans/2026-03-05-velocity-model-improvements.md` (P0-P11), `docs/plans/2026-03-05-velocity-model-phase2.md` (6 tasks). Most P0-P5 items already implemented.

---

## Phase 0: Inventory — What's Done vs What's Left

Before research, establish ground truth on current solver state.

### Task 0.1: Audit implemented vs planned features

**Files to read (via Serena `get_symbols_overview`):**
- `cataclysm/velocity_profile.py` — VehicleParams fields, solver passes
- `cataclysm/grip_calibration.py` — calibration functions
- `cataclysm/grip.py` — multi-approach grip estimation
- `cataclysm/equipment.py` — equipment→VehicleParams mapping
- `cataclysm/elevation_profile.py` — gradient + vertical curvature
- `cataclysm/curvature.py` — curvature computation
- `cataclysm/optimal_comparison.py` — speed gap analysis
- `cataclysm/corners.py` — corner detection + KPIs

**Produce a checklist** of each P0-P11 item from the research doc:

| Priority | Feature | Status | Evidence |
|----------|---------|--------|----------|
| P0 | Data-driven grip (3 semi-axes) | ✅/❌/Partial | file:line |
| P1 | Friction ellipse | ✅/❌/Partial | file:line |
| P2 | Elevation/gradient | ✅/❌/Partial | file:line |
| P3 | Smoothing spline curvature | ✅/❌/Partial | file:line |
| P4 | Linked corner grouping | ✅/❌/Partial | file:line |
| P5 | Per-corner mu | ✅/❌/Partial | file:line |
| P6 | Banking/camber | ✅/❌/Partial | file:line |
| P7 | Multi-lap curvature averaging | ✅/❌/Partial | file:line |
| P8 | Full GGV surface | ✅/❌/Partial | file:line |
| P9 | Clothoid spline fitting | ✅/❌/Partial | file:line |
| P10 | Tire thermal model | ✅/❌/Partial | file:line |
| P11 | Load sensitivity | ✅/❌/Partial | file:line |

Also check Phase 2 plan tasks (Barber elevation, friction circle wiring, drag coefficient, load sensitivity wiring, power-limited accel, LIDAR).

**Output:** Updated checklist saved to `tasks/solver_audit_status.md`.

**Commit:** `chore: audit solver implementation status vs planned improvements`

---

## Phase 1: Discover — Multi-Model Physics Validation

Use `/octo:discover` (which orchestrates Gemini + Codex + Claude) for domain research.

### Task 1.1: Validate current tire/grip model

**Invoke:** `/octo:discover` with:

> "Review this motorsport lap time simulator's tire grip model for physical correctness. The model uses:
> 1. Data-driven grip calibration: 95th percentile of |ay| when |ax|<0.2g gives max_lateral_g (grip_calibration.py)
> 2. Friction ellipse: (ax/ax_max)^p + (ay/ay_max)^p ≤ 1 with compound-specific exponent p=1.8-2.3
> 3. Load sensitivity: power-law correction mu_eff = mu * 0.5*((1+dLT)^(n-1) + (1-dLT)^(n-1)) where dLT = mu*h_cg/track_w
> 4. Per-corner mu from observed lateral G at each corner zone
> 5. Compound mu cap: category default * 1.15
>
> Questions for each model:
> - Is the formula physically correct?
> - What are common errors in this approach?
> - What does SAE / Pacejka / MoTeC recommend instead?
> - What's the expected accuracy band?
> - Any quick wins to improve without adding complexity?"

**Focus:** Technical implementation, ~3 min depth, detailed report format.

**Output:** Save Gemini + Codex + Claude perspectives to `tasks/solver_review_grip_findings.md`.

### Task 1.2: Validate velocity solver physics

**Invoke:** `/octo:discover` with:

> "Review this forward-backward velocity profile solver (Kapania 2016) for a motorsport lap time simulator:
> 1. Max cornering speed: v = sqrt(mu*g / |κ|) with vertical curvature correction: N_eff = m*(g*cos(θ) + v²*κ_v)
> 2. Forward pass: dv/ds = a_net/v where a_net = min(grip_accel, power_accel) - drag - gradient
> 3. Backward pass: mirror of forward with braking limits
> 4. Combined: pointwise min(forward, backward, cornering)
> 5. Elevation: g*sin(θ) in longitudinal, g*cos(θ) in normal force
> 6. Aero: drag_g = drag_coefficient * v² (in forward/backward) + aero_coefficient for downforce in cornering
> 7. Vertical curvature: denom floor at 50% of lateral curvature to prevent GPS noise dominance
>
> Questions:
> - Is the vertical curvature formula and denom floor physically justified?
> - Is the power-limited model (P_wheel / m*v*g) correct?
> - Are there known numerical instabilities in this approach?
> - What accuracy should we expect vs real lap times?
> - What do TUMFTM, OpenLAP, and OptimumLap do differently?"

**Output:** Save to `tasks/solver_review_velocity_findings.md`.

### Task 1.3: Validate corner detection & comparison metrics

**Invoke:** `/octo:discover` with:

> "Review motorsport corner detection and speed gap analysis:
> 1. Corner detection: heading rate threshold (1 deg/m), min length 15m, merge gap 30m
> 2. Apex: geometric vs speed-minimum reconciliation in 50% window
> 3. Speed gap metric: min(actual) vs min(optimal) in ±30% apex window (min 20m)
> 4. Brake gap: search 200m before corner entry for deceleration onset
> 5. Time cost: trapezoidal integration of speed delta over corner zone
>
> Questions:
> - Is ±30% apex window appropriate? What do MoTeC/Pi Toolbox use?
> - Is the brake point detection algorithm robust?
> - Are there better time cost attribution methods?
> - How should chicanes/esses be handled (linked corners)?
> - What accuracy band for speed gap metrics with RaceBox GPS (~0.5m)?"

**Output:** Save to `tasks/solver_review_corner_findings.md`.

### Task 1.4: Validate curvature computation

**Invoke:** `/octo:multi` with:

> "Review GPS curvature computation for a lap time simulator:
> 1. GPS lat/lon → equirectangular XY projection
> 2. Fit SciPy UnivariateSpline with smoothing factor per point
> 3. Curvature from spline derivatives: κ = (x'y'' - y'x'') / (x'² + y'²)^(3/2)
> 4. Post-processing: Savitzky-Golay filter, rate limiter (0.02 1/m²), physical clamp (0.33 1/m)
> 5. GPS accuracy: ~0.5m (RaceBox multi-band GNSS)
>
> Questions:
> - Is the smoothing approach optimal for 0.5m GPS noise?
> - Is the rate limiter (0.02 1/m²) physically justified?
> - Would clothoid fitting be materially better?
> - What does the academic literature say about GPS curvature error bounds?"

**Output:** Save to `tasks/solver_review_curvature_findings.md`.

**Commit after all 1.x tasks:** `docs: multi-model physics validation findings`

---

## Phase 2: Grasp — Define Improvement Scope

### Task 2.1: Synthesize findings into action items

**Invoke:** `/octo:grasp` with:

> "Based on these multi-model physics validation findings [attach all 4 findings files], define:
> 1. Critical bugs: formulas that are wrong and need immediate fixing
> 2. Material improvements: changes that would improve accuracy by >1% on lap time
> 3. Nice-to-haves: theoretical improvements with <1% impact
> 4. Deferred: changes that need data we don't have
>
> For each item, specify: what to change, in which file, expected impact, effort level."

**Output:** Scoped improvement list saved to `tasks/solver_improvements_scoped.md`.

### Task 2.2: Prioritize and estimate

Review the scoped list against:
- Current solver state (Phase 0 audit)
- Effort vs impact
- Data availability (do we have the inputs?)
- Breaking changes (cache invalidation, API schema changes?)

**Output:** Final ordered task list with go/no-go for each item.

**Commit:** `docs: scoped solver improvement plan from multi-model review`

---

## Phase 3: Dev — Implement Improvements

### Task 3.1: Switch to dev mode

**Invoke:** `/octo:dev`

### Task 3.2-N: Implement each approved improvement

For each improvement from the scoped list:

1. **Create temp branch:** `temp/solver-<improvement-name>`
2. **Write failing test** (TDD)
3. **Implement** using `python-development:python-pro` agent
4. **Run quality gates:** ruff format → ruff check → dmypy → pytest
5. **Commit** with descriptive message
6. **Bump `PHYSICS_CODE_VERSION`** in `db_physics_cache.py` (invalidates stale cache)
7. **Merge to staging**

### Task 3.X: Bump physics cache version

**Files:**
- Modify: `backend/api/services/db_physics_cache.py` — bump `PHYSICS_CODE_VERSION`

Any solver change that affects output values MUST bump this version to invalidate the two-tier cache (in-memory + PostgreSQL). Without this, users see stale results.

**Commit:** `chore: bump PHYSICS_CODE_VERSION for solver improvements`

---

## Phase 4: Review — Multi-Model Code Review

### Task 4.1: Multi-model review of all changes

**Invoke:** `/octo:review` with:

> "Review the physics solver changes on the current branch. Focus on:
> 1. Physical correctness of formulas
> 2. Numerical stability (division by zero, overflow, NaN propagation)
> 3. Backward compatibility (do existing tests still pass?)
> 4. Cache invalidation (is PHYSICS_CODE_VERSION bumped?)
> 5. Performance impact (any new O(n²) or expensive operations?)"

### Task 4.2: Mandatory code review

**Invoke:** `superpowers:code-reviewer` (per CLAUDE.md requirement)

### Task 4.3: Run full quality gates

```bash
source .venv/bin/activate
ruff format cataclysm/ tests/ backend/
ruff check cataclysm/ tests/ backend/
dmypy run -- cataclysm/ backend/
pytest tests/ backend/tests/ -v -n auto
cd frontend && npx tsc --noEmit && cd ..
```

**Commit:** Any fixes from review findings.

---

## Execution Strategy

### Multi-model tool usage per phase:

| Phase | Tool | Models Used | Purpose |
|-------|------|-------------|---------|
| 0. Inventory | Serena + Explore agent | Claude only | Map current state |
| 1. Discover | `/octo:discover` | Gemini + Codex + Claude | Physics validation |
| 2. Grasp | `/octo:grasp` | Claude (synthesis) | Scope definition |
| 3. Dev | `/octo:dev` + python-pro | Claude (impl) | Code changes |
| 4. Review | `/octo:review` | Gemini + Codex + Claude | Code review |

### Parallelization:

- Tasks 1.1–1.4 can run in parallel (independent research queries)
- Phase 3 tasks are sequential (each builds on previous)
- Tasks 4.1 and 4.2 can run in parallel

### Estimated costs:

- `/octo:discover` × 4 queries: ~$0.12–0.32
- `/octo:multi` × 1 query: ~$0.02–0.08
- `/octo:review` × 1 query: ~$0.02–0.08
- Total external model cost: ~$0.16–0.48

---

## Success Criteria

1. All findings documented with citations to academic sources
2. Any formula bugs identified and fixed
3. Quality gates green (ruff, mypy, pytest, tsc)
4. `PHYSICS_CODE_VERSION` bumped if solver output changed
5. No regression in existing test assertions
6. Multi-model consensus on physical correctness of changes
