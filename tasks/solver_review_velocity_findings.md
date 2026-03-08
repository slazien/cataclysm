# Solver Review: Velocity Profile Solver — Multi-Model Findings

> Task 1.2 from `docs/plans/2026-03-08-solver-review-multi-model.md`

## Models Used
- 🔴 Codex (gpt-5.3-codex) — Formula validation
- 🔵 Claude Opus 4 — Implementation code review

---

## 1. Cornering Speed Formula

### v² = mu·g·cos(θ) / (|κ_lat| - mu·κ_v - aero·G)

**Consensus: Correct derivation**
- Standard quasi-static normal force balance with vertical curvature
- Aero downforce term sign is correct (negative in denom = higher speed)

### 50% Denominator Floor

- 🔴 Codex: "Not physically justified as a universal rule. It is a numerical guardrail."
- 🔵 Claude: "Pragmatic guard against GPS noise, not a physics justification."
- 🔴 Codex: "Hard-caps aero/vertical-curvature benefit to about √2 speed gain."
- 🔴 Codex suggests: "Use a small absolute floor tied to a plausible v_max" instead
- **Verdict**: Keep as-is for coaching (GPS noise is the real threat), but document as numerical guard. The √2 cap is not a problem in practice — compressions rarely contribute >40% speed increase.

---

## 2. Forward/Backward Passes

### Power-limited acceleration: P/(m·v·g)
- **All models confirm: Correct.** a = P/(m·v), convert to G: a_g = P/(m·v·g).
- 🔴 Codex: "P/(m*v*g) singular at low v — use v_min" — our code already has `MIN_SPEED_MPS` guard ✅

### ⚠️ BUG: normal_scale applied to power-limited acceleration
- 🔴 Codex: "Apply normal_scale to tire-force limits, not to P/(m*v*g). Power limit is drivetrain-limited, not normal-load-limited."
- 🔵 Claude: Same finding independently. "Engine thrust doesn't depend on tire normal force."
- **Location**: `velocity_profile.py:263-265` — vertical curvature `normal_scale` is applied *after* `min(accel_g, power_accel_g)`, so it affects both grip-limited AND power-limited branches.
- **Fix**: Apply `normal_scale` only to `accel_g` before the `min()`, not to the result.

### Drag handling
- **All confirm: Correct.** Forward: drag opposes motion (subtracts from accel). Backward: drag assists braking (adds to decel).
- 🔴 Codex: Gradient sign consistent with "positive uphill" convention ✅

### Track tripling
- **All confirm: Correct.** Standard approach for closed circuits. Extracting middle copy handles both forward (entry speed) and backward (braking into first corner) wrap-around.
- 🔴 Codex: "More rigorous: iterate on periodic array until convergence." Not needed for coaching-grade sim.

---

## 3. Lap Time Integration

### sum(2·ds / (v_i + v_{i+1}))
- Harmonic mean of endpoint speeds is the trapezoidal rule for dt = ds/v
- All models confirm: Sufficiently accurate for the 0.7m step size

---

## 4. Numerical Stability

### Issues identified (🔴 Codex)
| Risk | Status | Location |
|------|--------|----------|
| P/(m·v·g) singular at low v | ✅ Guarded | `MIN_SPEED_MPS` in condition |
| Negative radicand in sqrt | ✅ Guarded | `max(v_next_sq, 0.0)` |
| Denom near zero in cornering speed | ✅ Guarded | 50% floor + `denom > 1e-9` |
| NaN propagation | ✅ Guarded | `~np.isfinite(max_speed)` → top_speed |
| Noisy κ/κ_v causing speed chatter | ✅ Handled | Spline smoothing + rate limiter upstream |
| Large ds integration error | ✅ Acceptable | 0.7m step = ~1ms at 250 kph |
| **Seam continuity at lap wrap** | ⚠️ Unchecked | Curvature/gradient mismatch at tile boundary |

### Seam continuity note
- 🔴 Codex flags: "Ensure seam continuity before tripling (curvature/grade mismatch at lap wrap)"
- Track tripling uses `np.tile(abs_k, 3)` — this is discontinuous if the first and last curvature points differ
- **However**: For closed circuits, the track data should already be continuous at the wrap point (same start/finish location). This is a data quality concern, not a solver bug.

---

## 5. Accuracy Assessment

| Condition | Accuracy | Source |
|-----------|----------|--------|
| Well-calibrated, near-limit driver | ±1-3% lap time | 🔴 Codex, 🟡 Gemini |
| Simple mu setup | ±3-8% | 🔴 Codex |
| Corner-by-corner speed gaps | ±2-5 kph at apex | 🔵 Claude |

### Main accuracy limiters (ranked)
1. Racing line differences (point-mass vs actual driven line)
2. Transient dynamics (weight transfer, yaw rate)
3. Combined-slip detail (friction ellipse is approximation)
4. GPS curvature noise propagation

---

## 6. Actionable Findings

### Bug to Fix
| # | Finding | Source | File | Line | Effort |
|---|---------|--------|------|------|--------|
| **V1** | **normal_scale applied to power-limited accel** | 🔴🔵 Both | `velocity_profile.py` | 263-265 | Low |

### Improvements
| # | Finding | Source | Effort | Impact |
|---|---------|--------|--------|--------|
| V2 | Document 50% denom floor as numerical guard (not physics) | 🔴🔵 Both | Trivial | Clarity |
| V3 | Verify seam continuity at track wrap for tiled data | 🔴 Codex | Low | Edge case |

---

## References
- Kapania et al. 2016, "Path tracking of autonomous vehicles at the limit of handling"
- TUMFTM `global_racetrajectory_optimization` (nonlinear tire, accel ellipse)
- Braghin et al. 2008, "Race Driver Model" (vertical curvature correction)
