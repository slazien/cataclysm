# Physics Tier 2 — Regression Analysis & Improvement Research

**Date:** 2026-03-19
**Baseline:** Tier 1 results (commit `66f3c83` on staging)

---

## Part 1: Tier 1 Regression Analysis

### Summary

| Metric | Baseline | Tier 1 | Delta |
|--------|----------|--------|-------|
| mean_ratio | 0.9761 | 0.9691 | −0.0070 (worse) |
| std_ratio | 0.0501 | 0.0476 | −0.0025 (better) |
| exceedance >1.05 | 1 | 0 | −1 (better) |
| r_compound_mean | 0.9131 | 0.8910 | −0.0221 (worse) |

**Entries improved: 15 / Worsened: 18 / Total: 33**

The net mu change across the dataset was **+0.39** (20 entries received higher mu, 4 lower, 9 unchanged). Since the baseline mean was already below 1.0, adding grip made predictions faster → ratios moved further from 1.0.

### Per-Category Breakdown

| Category | n | Mean ratio | Gap from 1.0 |
|----------|---|------------|--------------|
| street | 1 | 1.027 | solver 2.7% too slow |
| endurance_200tw | 11 | 1.001 | essentially perfect |
| super_200tw | 11 | 0.981 | solver 1.9% too fast |
| 100tw | 3 | 0.947 | solver 5.3% too fast |
| slick | 3 | 0.917 | solver 8.3% too fast |
| r_compound | 4 | 0.891 | solver 10.9% too fast |

**Key pattern: bias scales monotonically with mu.** This is NOT a uniform offset — the solver becomes progressively more optimistic as tire grip increases.

### Top 5 Entries That Got Worse

| Car | Track | Tire | Old ratio | New ratio | Δ | Root cause |
|-----|-------|------|-----------|-----------|---|------------|
| GR86 (FR-S proxy) | Roebling | Nitto NT01 | 0.985 | 0.948 | +0.037 | NT01 recategorized super_200tw→100tw (+0.10 mu) |
| Cayman GT4 718 | Atlanta | Pirelli slick | 0.919 | 0.898 | +0.022 | per_tire_mu +0.05, CL·A downforce added |
| 911 GT3 992 | Barber | DH Slick | 0.952 | 0.931 | +0.021 | per_tire_mu +0.05, CL·A downforce stacked |
| Cayman GT4 718 | Barber | Cup 2 | 0.973 | 0.952 | +0.020 | per_tire_mu +0.05, CL·A downforce |
| Mustang GT S550 | Roebling | Hoosier A7 | 0.882 | 0.864 | +0.017 | per_tire_mu +0.07 (A7 1.42 vs default 1.35) |

### Top 5 Entries That Improved

| Car | Track | Tire | Old ratio | New ratio | Δ | Root cause |
|-----|-------|------|-----------|-----------|---|------------|
| C8 Z06 | Roebling | Trofeo R | 0.917 | 0.964 | −0.047 | Trofeo R mu 1.18 vs r_compound default 1.35 (−0.17) |
| GT350 | Roebling | SC3R | 0.886 | 0.929 | −0.043 | SC3R mu 1.20 vs r_compound default 1.35 (−0.15) |
| C8 Z06 | Barber | A052 | 1.040 | 1.021 | −0.019 | Was >1.0; per_tire_mu + CL·A pushed toward 1.0 |
| GR86 | Atlanta | RT660 | 1.020 | 0.998 | −0.018 | Was >1.0; per_tire_mu +0.05 pulled toward 1.0 |
| GR86 | Roebling | PS4 | 1.043 | 1.027 | −0.016 | Was >1.0; per_tire_mu +0.03 |

### R-Compound Category Deep Dive

R-compound went from 9 to 4 entries after recategorization (5 entries moved to slick/100tw). The remaining 4 are all Hoosier tires:

| Car | Tire | Old mu | New mu | Old ratio | New ratio |
|-----|------|--------|--------|-----------|-----------|
| Miata NA | Hoosier R7 | 1.35 | 1.38 | 0.938 | 0.932 |
| 911 GT3 991 | Hoosier R7 | 1.35 | 1.38 | 0.934 | 0.922 |
| Mustang S550 | Hoosier A7 | 1.35 | 1.42 | 0.882 | 0.864 |
| Mustang S550 | Hoosier R7 | 1.35 | 1.38 | 0.853 | 0.846 |

All 4 worsened. The Mustang entries at Roebling (ratios 0.846–0.864) represent a 12–15% gap that is too large for driver skill alone.

---

## Part 2: Root Cause of the Mu-Correlated Bias

Three compounding physics effects, all unmodeled or undermodeled, all operating in the same direction:

### 1. Load Transfer Factor-of-2 Approximation

**File:** `velocity_profile.py:146-161`

The code uses `dlt = effective_mu * cg_height / track_width`. The rigorous formula is `dlt = 2.0 * effective_mu * cg_height / (track_width)`. The comment at line 146-148 acknowledges this: *"Our simplified form folds this into the exponent tuning."*

For a Mustang GT (CG≈0.46m, track≈1.55m) at 1.35G:
- Correct dLT ≈ 0.80 → correction = 0.952
- Model dLT ≈ 0.40 → correction = 0.980
- **Difference: 2.8% effective mu**, translating to ~1.4% lap time

This disproportionately affects high-CG, high-mu cars — exactly the worst entries.

**Estimated contribution to r_compound gap: 2–4%**

### 2. Cornering Drag from Slip Angle (Unmodeled)

Tires at slip angle create induced drag: `Drag = Fy × sin(α)`. At r-compound peak slip (7–10°), this is 12–17% of lateral force. Currently zero in the solver.

Per-compound peak slip angles (from literature):
| Category | Peak slip | Induced drag fraction |
|----------|-----------|----------------------|
| Street | 4–6° | 7–10% |
| 200tw | 5–7° | 9–12% |
| 100tw | 6–8° | 10–14% |
| R-compound | 7–10° | 12–17% |
| Slick | 8–12° | 14–21% |

For a 60%-cornering track, this accounts for **1.5–4% of lap time** — and the effect scales with mu (larger slip angle at higher grip).

**Estimated contribution to r_compound gap: 2–3%**

### 3. R-Compound/Slick Mu Values May Be Too High

The Grassroots Motorsports R-comp tire test notes Hoosier tires "start at higher grip but degrade faster" — the peak published mu may overstate achievable average mu over a lap. The validation data suggests effective R_COMPOUND mu should be ~1.25–1.28, not 1.35.

**Estimated contribution to r_compound gap: 3–5%**

### Combined

These three mechanisms account for ~7–12% of the observed 10.9% r_compound gap.

---

## Part 3: Tier 2 Improvement Priorities

### Tier 2A — Implement First (High impact)

**T2A-1: Fix load transfer factor-of-2**
- Change line 161: `dlt = 2.0 * effective_mu * cg_height / track_width`
- Re-tune `CATEGORY_LOAD_SENSITIVITY_EXPONENT` values (current exponents calibrated against the simplified formula)
- Impact: 2–4% on r_compound, proportional effect on other categories
- Complexity: Easy (one line + re-tuning)
- Risk: Must re-tune exponents or lower-mu categories will overcorrect

**T2A-2: Cornering-induced drag from slip angle**
- Add `peak_slip_angle_deg: float = 7.0` to `VehicleParams`
- Add `CATEGORY_PEAK_SLIP_ANGLE_DEG` table to `equipment.py`
- In forward/backward passes: `cornering_drag_g = mu × sin(α) × (lateral_g / max_lateral_g)²`
- Impact: 1–3% on r_compound, scales with mu
- Complexity: Medium (new physics term in solver + category table)

**T2A-3: Recalibrate R-compound/slick category mu**
- Reduce `R_COMPOUND: 1.35 → 1.28`, `SLICK: 1.50 → 1.42`
- Re-run validation after T2A-1 and T2A-2 to determine correct values
- Impact: 3–5% on r_compound
- Complexity: Easy (config change)
- Risk: Must do AFTER T2A-1 and T2A-2 or we're compensating model errors with wrong mu

### Tier 2B — Implement Second (Medium impact)

**T2B-1: Driver skill factor**
- Add `grip_utilization: float = 1.0` to `VehicleParams`
- Applied as `effective_mu *= sqrt(grip_utilization)`
- Range: 0.85 (beginner) → 0.95 (advanced club) → 1.0 (pro)
- Impact on mean_ratio: Marginal for validation dataset (best-lap data from motivated drivers)
- Impact on coaching: High (explicit gap between user and optimal)
- Complexity: Easy

**T2B-2: Per-compound thermal penalty**
- Add `CATEGORY_THERMAL_PENALTY` table: r_compound=0.97, slick=0.96, others≈1.0
- Simple mu multiplier — phenomenological, not a real thermal model
- Complexity: Easy
- Calibrate AFTER T2A to avoid double-counting

### Tier 2C — Future (Low impact for current dataset)

- **Road banking from LIDAR lateral tilt** — <1% impact for Barber/Roebling/AMP
- **Full thermal tire model** — requires proprietary tire data
- **Per-track surface mu** — data unavailable; grip calibration already subsumes this

### Expected Outcome After Tier 2A

| Category | Current | After T2A estimate |
|----------|---------|-------------------|
| r_compound | 0.891 | 0.93–0.95 |
| slick | 0.917 | 0.95–0.97 |
| 100tw | 0.947 | 0.96–0.97 |
| super_200tw | 0.981 | 0.98–1.00 |
| endurance_200tw | 1.001 | 0.99–1.01 |
| **Overall mean** | **0.969** | **~0.975–0.985** |
| **std** | **0.048** | **~0.025–0.030** |

---

## Sources

- ChassisSim — Grip and Bump Factors for Lap Time Simulation (0.85–0.95 range for club racing)
- SAE 2017-01-9679 — Feasibility Study on Driver Model Based Lap Time
- Paradigm Shift Racing — Car Setup Science #2: Tires (slip angle, induced drag)
- Racing Car Dynamics — Weight Transfer guide (dLT = lat_G × h_cg / (0.5 × track_w))
- Grassroots Motorsports — R-comp tire test: Hoosier R7 vs Goodyear vs Yokohama
- Prisma Electronics — Effect of Track Temperature on Tire Degradation
- theRACINGLINE.net — Tyre Load Sensitivity reference
- ResearchGate — Circuit racing, track texture, temperature and rubber friction
