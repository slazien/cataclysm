# Solver Review: Tire Grip Model — Multi-Model Findings

> Task 1.1 from `docs/plans/2026-03-08-solver-review-multi-model.md`

## Models Used
- 🟡 Gemini 2.5 Pro — Academic literature cross-reference
- 🔴 Codex (gpt-5.3-codex) — Formula validation + web research
- 🔵 Claude Opus 4 — Implementation assessment

---

## 1. Grip Calibration (p95, 0.3G filter, 3-regime split)

### Consensus (all models agree)
- **p95 is correct and well-justified.** Standard practice in motorsport data analysis. p99 catches transient curb/weight-transfer spikes; p90 includes sub-limit cornering. p95 provides statistically stable peak capability.
- **0.3G minimum lateral filter is justified.** Excludes gentle sweeper data that dilutes the distribution. MoTeC i2 Pro's "Friction Circle" analysis uses similar low-G exclusion.

### Model-specific insights
- 🟡 Gemini: "Ensures you are only considering data where the tire is operating in the non-linear portion of its slip-angle-vs-force curve" — i.e., the filter targets the region where tires are near saturation.
- 🔵 Claude: The 0.3G threshold should arguably be **compound-dependent**. Slick tire drivers routinely corner at 0.5G+ even in "gentle" sections, making the 0.3G floor less effective at excluding sub-limit data for high-grip compounds. Consider: street=0.2G, endurance=0.3G, R-compound=0.4G, slick=0.5G.

### Potential Issues
- **Calibration ratchet** (🔵 Claude): `apply_calibration_to_params()` uses `max(base, observed)` — calibration can only raise grip, never lower it. If base params over-estimate (worn tires, incorrect compound selection), calibration won't correct downward. The `mu_cap` (category * 1.15) partially mitigates this.
- **No combined-slip filtering**: The 3-regime approach requires "pure" axes (cross-axis < 0.2G). Points in combined braking+cornering (trail braking) are excluded from calibration entirely. This is correct for envelope extraction but means the calibration doesn't validate the friction ellipse shape in combined regions.

---

## 2. Friction Ellipse

### Consensus
- **Formula is correct.** This is the standard generalised friction ellipse from Milliken & Milliken, *Race Car Vehicle Dynamics*, Ch. 2.
- **Exponent range 1.8–2.3 is physically valid.** Racing slicks → p ≈ 2.0–2.2 (blunted/squared). Street tires → p ≈ 1.6–1.8 (closer to diamond). The compound-specific exponent is a good refinement.

### Model-specific insights
- 🟡 Gemini: "A value of p=2.0 represents a perfect circle. Real tires rarely exhibit a perfectly circular friction envelope due to carcass construction and compound properties."
- 🔵 Claude: The exponent is category-wide, not tire-specific. Real friction ellipses vary by tire construction, not just compound. But for a coaching sim, category-level is appropriate.
- 🟡 Gemini: Ensure braking vs accel correctly switches `max_lon`. ✅ Our code does this — `_available_accel()` takes a `direction` parameter.

---

## 3. Load Sensitivity

### Consensus
- **The power-law formula is mathematically correct.** Jensen's inequality argument is sound: for n<1 on concave x^n, correction is always < 1.0.
- **dLT = mu * h_cg / track_w is a common simplification.** Correct for steady-state cornering at the limit.

### Model-specific insights
- 🟡 Gemini: Notes a "dimensional inconsistency" — the rigorous formula would be `dLT = lat_G * h_cg / (0.5 * track_w)`, i.e., a factor of 2 different. Our formula bundles this into the exponent tuning, so it's not a bug but should be documented.
- 🔵 Claude: Typical load sensitivity exponents in Pacejka Ch. 4 are 0.7–0.9. Should verify `CATEGORY_LOAD_SENSITIVITY_EXPONENT` values fall in this range.
- 🟡 Gemini: The parameter n is "difficult to measure without a tire testing rig and is often a key calibration parameter."

### Verified ✅
`CATEGORY_LOAD_SENSITIVITY_EXPONENT` values are all within Pacejka-recommended 0.7–0.9:

| Category | Exponent | Status |
|----------|----------|--------|
| STREET | 0.85 | ✅ In range |
| ENDURANCE_200TW | 0.82 | ✅ In range |
| SUPER_200TW | 0.82 | ✅ In range |
| TW_100 | 0.80 | ✅ In range |
| R_COMPOUND | 0.78 | ✅ In range |
| SLICK | 0.75 | ✅ In range |

Trend is physically correct: softer compounds (slicks) have lower exponents = more load sensitivity.

---

## 4. Compound Mu Defaults & Cap

### Current values
| Category | Default mu | Cap (×1.15) |
|----------|-----------|-------------|
| STREET | 0.85 | 0.98 |
| ENDURANCE_200TW | 1.00 | 1.15 |
| SUPER_200TW | 1.10 | 1.27 |
| TW_100 | 1.20 | 1.38 |
| R_COMPOUND | 1.35 | 1.55 |
| SLICK | 1.50 | 1.73 |

### Assessment
- 🟡 Gemini: These values are "in the right ballpark for a generic model."
- 🔵 Claude: The 1.15× cap is pragmatic but should be validated against real data. For some high-performance street tires (e.g., Michelin Pilot Sport 4S), mu can reach 0.95–1.0, close to the default. For some racing slicks, mu can be 1.4–1.6, which the cap handles well.

---

## 5. Overall Accuracy

### Consensus
- **±0.5–1.5% of real lap time** for a well-calibrated model (🟡 Gemini)
- **±1–3%** accounting for racing line differences (🔵 Claude)
- **Corner-by-corner speed gaps: ±2–5 kph at apex** (🔵 Claude)

### Main error sources (ranked)
1. Racing line differences (point-mass follows curvature center, not driven line)
2. Transient effects (weight transfer dynamics, brake temperature)
3. Tire model simplifications (no thermal, no combined slip validation)
4. GPS noise propagation through curvature estimation

---

## 6. Actionable Findings

### Critical Bugs: None found (but see G1)
All formulas are physically correct. No mathematical errors. However, one **logical issue** was identified.

### ⚠️ High-Priority Issue
| # | Finding | Source | File | Effort | Impact |
|---|---------|--------|------|--------|--------|
| **G1** | **Double-counting load sensitivity**: Calibrated `max_lateral_g` from telemetry already includes real load transfer effects. Applying the power-law correction on top may over-penalize grip. | 🔴 Codex | `velocity_profile.py:148-155` | Medium | **Potentially significant** — correction should only apply to default (non-calibrated) params, or be reduced for calibrated data |

### Material Improvements (>1% impact potential)
| # | Finding | Source | File | Effort |
|---|---------|--------|------|--------|
| G2 | Compound-dependent 0.3G lateral filter | 🔵 Claude | `grip_calibration.py` | Low |
| G3 | Document dLT factor-of-2 simplification | 🟡 Gemini | `velocity_profile.py` | Trivial |
| G4 | Verify load sensitivity exponents are 0.7–0.9 | 🔵🟡 Both | `equipment.py` | ✅ Done — all in range |
| G5 | Fixed G thresholds ignore aero/speed effects and banking | 🔴 Codex | `grip_calibration.py` | Medium |

### Nice-to-haves (<1% impact)
| # | Finding | Source | Effort |
|---|---------|--------|--------|
| G6 | Allow calibration to lower grip (not just raise) | 🔵 Claude | Medium |
| G7 | Tire-specific friction ellipse exponent (vs category) | 🔵 Claude | High (data needed) |
| G8 | GGGV surface (speed-dependent envelope) — code exists but dead | 🔴 Codex | Medium (wiring) |

### Codex-specific references (from web search)
- SAE J670 (2022 reaffirmed): Vehicle Dynamics Terminology — friction ellipse as combined-force boundary
- MFeval (MF 5.2/6.1/6.2): Combined force/slip parameterization
- TUMFTM `global_racetrajectory_optimization`: Nonlinear tire, accel ellipse, GGGV
- TUM-AVS `GGGVDiagrams`: Speed/vertical-accel dependent envelope concept
- MDPI Applied Sciences 15/22/12269: Load-sensitive friction + ellipse integration

---

## References
- Pacejka, H.B. *Tire and Vehicle Dynamics*, 3rd Ed., Ch. 4 (Magic Formula, combined slip)
- Milliken & Milliken, *Race Car Vehicle Dynamics*, Ch. 2 (friction ellipse, load sensitivity)
- SAE 2008-01-2953, "Lap Time Simulation as a Tool for Race Car Design"
- Kapania et al. 2016, "Path tracking of autonomous vehicles at the limit of handling"
- Lovato & Massaro 2022, "Practical lap time simulation"
