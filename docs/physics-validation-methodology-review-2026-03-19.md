# Physics Engine Validation Methodology Review

**Date:** 2026-03-19
**Providers:** Codex (gpt-5.3-codex), Gemini (gemini-2.5-pro), Claude (opus-4.6)
**Method:** 2 rounds of research per provider + independent statistical analysis
**Scope:** Validate current methodology, identify improvements, recommend implementation

---

## Executive Summary

The current physics validation methodology is **fundamentally sound** but has significant gaps that limit diagnostic power and confidence. The mean ratio (0.9995) and std (0.034) place us at the **Tier A/B boundary** (Engineering Screening / Setup Optimization level). To reach **Tier C (Coaching Quality)**, we need std ≤ 0.025, which requires both physics improvements AND better validation tooling.

**Key finding:** The mu-correlated bias (r = -0.538) is a **known and expected artifact** of point-mass QSS solvers, confirmed by all 3 providers. It's not a bug — it's a fundamental limitation of the model class that can be partially corrected with compound-specific grip utilization factors.

---

## Part 1: Current Methodology Assessment

### What's Working Well

| Aspect | Status | Evidence |
|--------|--------|----------|
| Real-world ground truth | ✅ Strong | 33 curated entries from verifiable sources |
| Core metric (efficiency ratio) | ✅ Standard | Used by OptimumLap, ChassisSim, and academic papers |
| Per-category breakdown | ✅ Good | 6 tire categories tracked |
| Acceptance criteria | ✅ Reasonable | Mean/std/exceedance gates catch regressions |
| Baseline comparison | ✅ Automated | `--compare` flag with 10% relative threshold |
| Normality verified | ✅ | Shapiro-Wilk p=0.49 — ratios are normally distributed |

### Critical Gaps

| Gap | Severity | Impact |
|-----|----------|--------|
| **Single scalar validation** | HIGH | A "correct" lap time can hide compensating errors (fast on straights, slow in corners) |
| **Dataset imbalance** | HIGH | Barber=58%, 1 street tire, 0 AWD, only 1 FWD model |
| **No error decomposition** | HIGH | Can't tell if errors come from tire model, aero, power, or track geometry |
| **No bootstrap CIs** | MEDIUM | Mean CI is [0.987, 1.011] — wider than acceptance criteria window |
| **No residual diagnostics** | MEDIUM | Proportional bias (r=0.422) and mu-correlation (r=-0.538) undetected until manual analysis |
| **No influential point detection** | MEDIUM | Mustang GT S550 @ Barber (Cook's d=0.54) silently distorts the dataset |
| **No sensitivity analysis** | LOW | Don't know which parameters matter most — limits physics improvement prioritization |

### Statistical Profile (Current Baseline)

```
Overall (n=33):
  Mean ratio:           0.9995 (CI: [0.987, 1.011])
  Std ratio:            0.034  (CI: [0.027, 0.045])
  RMSE:                 3.204s
  MAE:                  2.500s
  MAPE:                 2.66%
  Exceedances >5%:      3

Calibration regression (pred vs real):
  Slope:                1.092  (ideal: 1.000)
  Intercept:           -8.656s (ideal: 0.000s)
  R²:                   0.925

Bland-Altman:
  Bias:                 0.063s
  95% LoA:             [-6.22, 6.34]s
  Proportional bias:    r=0.422 (near-significant, p=0.07)

Heteroscedasticity (Breusch-Pagan):
  vs real_time:         p=0.452 (NO — error variance is constant)
  vs mu:                p=0.732 (NO)

Key correlations with ratio:
  mu:                   r=-0.538 (p=0.001) ***
  weight_kg:            r=-0.428 (p=0.013) *
  power_hp:             r=-0.271 (p=0.127) n.s.
  power_to_weight:      r=-0.169 (p=0.346) n.s.

Multivariate (ratio ~ mu + hp + weight):
  R² = 0.449, Adj R² = 0.392
  mu:        β=-0.119 (p=0.001) *** ← dominant predictor
  weight_kg: β=-0.000092 (p=0.015) *
  hp:        β=+0.000056 (p=0.283) n.s.

Influential points (Cook's distance):
  Mustang GT S550 @ Barber [endurance]: d=0.537 (threshold=0.121) ← MASSIVE outlier
  Mustang GT S550 @ Roebling [r_compound]: d=0.184

IQR outliers:
  Mustang GT S550 @ Roebling [r_compound]: ratio=0.932
  Mustang GT S550 @ Roebling [r_compound]: ratio=0.909
```

---

## Part 2: Recommended Metrics (Consensus: 3/3 Providers)

### Tier 1 — Implement Immediately

These require NO new data, only script changes.

| Metric | Formula | Purpose |
|--------|---------|---------|
| **RMSE** | `√(mean((pred-real)²))` | Overall prediction quality in seconds |
| **MAE** | `mean(|pred-real|)` | Average absolute error, less sensitive to outliers |
| **MAPE** | `mean(|pred-real|/real)×100` | Scale-independent percentage error |
| **Bland-Altman bias + LoA** | `mean(diff) ± 1.96*std(diff)` | Agreement analysis with limits |
| **Bootstrap 95% CIs** | BCa, 10k resamples | Confidence bounds for mean, std, per-category |
| **Calibration slope/intercept** | `linregress(real, pred)` | Systematic over/under-prediction pattern |
| **Residual correlations** | `pearsonr(ratio, [mu, weight, power, real_time])` | Detect systematic model biases |
| **Cook's distance** | OLS influence diagnostics | Flag entries that distort statistics |
| **IQR outlier detection** | Q1-1.5×IQR, Q3+1.5×IQR | Identify statistical outliers |
| **P90/P95 absolute error** | Percentile of |pred-real| | Tail risk in seconds |

### Tier 2 — Implement After Tier 1

| Metric | Purpose | Requires |
|--------|---------|----------|
| **Grip band breakdown** | Low/Mid/High mu analysis | Grouping logic only |
| **Power-to-weight bands** | Performance class analysis | Car specs (already have) |
| **Per-track with CIs** | Track-specific bias detection | Bootstrap per group |
| **Per-car analysis** | Identify problematic car models | Already computed |
| **Fast-vs-slow lap split** | Detect speed-range bias | Median split |
| **Breusch-Pagan test** | Formal heteroscedasticity check | statsmodels |

### Tier 3 — Future Enhancement

| Metric | Purpose | Requires |
|--------|---------|----------|
| **Sensitivity analysis** | Parameter importance ranking | Multiple solver runs per entry |
| **Performance-limiting factor breakdown** | % brake-limited / corner-limited / power-limited per lap | Solver internals access |
| **Leave-One-Track-Out CV** | Track generalization test | ≥4 tracks |
| **Monte Carlo uncertainty propagation** | Prediction intervals, not just point estimates | Parameter distributions |

---

## Part 3: Dataset Segmentation Strategy

### Recommended Segmentation (Consensus)

**Primary dimensions (minimum n≥5 per cell for reporting):**

1. **Grip Band** (3 levels, all providers agree)
   - Low: street + endurance_200tw → n=12, mean=1.018
   - Mid: super_200tw + 100tw → n=14, mean=0.999
   - High: r_compound + slick → n=7, mean=0.969

2. **Per-Track** (critical given 3.4% spread)
   - Barber: n=19, mean=1.011
   - Roebling: n=8, mean=0.977
   - Atlanta: n=6, mean=0.992

3. **Power-to-Weight** (3 bands)
   - Low <200 hp/t: n=9, mean=1.015
   - Mid 200-350: n=21, mean=0.992
   - High >350: n=3, mean=1.006 (too few!)

**Secondary dimensions (report when n≥5, roll up otherwise):**

4. **Drivetrain**: FWD (n=4, mean=1.018) vs RWD (n=29, mean=0.997) — FWD too sparse

5. **Fast-vs-Slow**: Fast (<95.9s, n=16, mean=0.991) vs Slow (≥95.9s, n=17, mean=1.008)

### Current Dataset Imbalance Issues

| Dimension | Problem | Minimum Target |
|-----------|---------|----------------|
| Tracks | 58% Barber | ≥5 tracks, each ≥10 entries |
| Street tires | n=1 | ≥5 entries |
| FWD cars | n=4 (1 model) | ≥8 entries (2+ models) |
| AWD cars | n=0 | ≥5 entries |
| High hp/t | n=3 | ≥5 entries |
| High-downforce | n=0 explicit | ≥3 entries |

### Dataset Expansion Priority (Gemini recommendation, Codex agrees)

**Most diagnostic value per added entry:**
1. **Same car + track, different tires** → directly tests tire model (isolates mu effect)
2. **Same track, different cars** → tests vehicle model breadth
3. **Same car, different tracks** → tests track geometry/solver robustness

**Practical target:** Expand from 33 → 60-80 entries across ≥5 tracks to meaningfully narrow CIs. Per Gemini: n=132 needed to halve CI width.

---

## Part 4: Understanding the Mu-Correlated Bias

### Consensus Finding (3/3 providers, 2 rounds)

The mu-correlated bias is **expected and well-documented** for point-mass QSS solvers. It arises from multiple compounding effects:

| Effect | Contribution | Scales with mu? | Correctable? |
|--------|-------------|-----------------|--------------|
| **Load transfer saturation** | 2-5% | YES (quadratic with G) | Partially (LLTD factor) |
| **Driver grip utilization gap** | 2-5% | YES (higher mu = narrower peak) | YES (per-compound factor) |
| **Tire thermal degradation** | 0.5-3% | YES (more heat at higher grip) | YES (phenomenological penalty) |
| **Tire transient response** | 1-4% | YES (higher forces = larger gaps) | Partially (jerk limit) |
| **Friction non-uniformity** | 1-3% | Moderate | NO (track-specific) |

### Why High-Mu Predictions Are Too Fast

The point-mass model assumes:
1. **100% of theoretical grip is available at all times** — real drivers achieve 85-98% depending on tire type
2. **Instantaneous force changes** — real tires have relaxation length (~0.5m), costing time in transitions
3. **Constant friction across the lap** — real high-grip tires lose 3-5% grip through thermal cycling
4. **Single-point load distribution** — real 4-tire load transfer saturates the loaded side (non-linear grip loss)

These effects **compound multiplicatively** and each one is MORE significant at higher grip levels, creating the monotonic mu-ratio correlation we observe.

### Published Support

- **Heilmeier (2022, TUM dissertation)**: QSS solver achieved +0.51% error on F1 at Shanghai — but this was with extensive parameter tuning
- **Biniewicz & Pyrz (VSD 2023)**: Introduced semi-empirical g-g based on measured rider utilization to correct QSS over-optimism
- **ChassisSim documentation**: Recommends "grip factor" 0.85-0.95 for club racing correlation
- **Codex R2 finding**: "Utilization gap grows with peak grip — theoretical g-g envelope > human-achievable envelope"

### Recommended Correction: Compound-Specific Effective Mu

```
mu_effective = mu_nominal × U_compound
```

Where `U_compound` is a per-category utilization factor accounting for the combined effects of thermal degradation, transient losses, and friction utilization. This is NOT a "driver skill" factor — it represents the gap between laboratory peak mu and achievable track-average mu.

Initial estimates (from Tier 2/3 research synthesis + our own data):

| Category | Current mean ratio | Implied U_compound | Proposed U_compound |
|----------|-------------------|-------------------|---------------------|
| street | 1.041 | ~0.96 | 0.98 |
| endurance_200tw | 1.016 | ~0.98 | 0.97 |
| super_200tw | 1.003 | ~0.997 | 0.96 |
| 100tw | 0.984 | ~1.016 | 0.95 |
| r_compound | 0.958 | ~1.044 | 0.93 |
| slick | 0.984 | ~1.016 | 0.92 |

**Note:** 100tw and slick show mean ratios <1.0, suggesting the solver is ALREADY faster than reality for these — U_compound correction would make this worse. This indicates the mu assignments for these categories may already be slightly too high, OR the correction needs to be mu-slope-based rather than purely per-compound.

---

## Part 5: Acceptance Criteria Tiers

### Consensus Framework (Codex + Gemini synthesis)

| Tier | Use Case | Mean Bias | Std | 95% LoA | MAPE | Per-Category Bias |
|------|----------|-----------|-----|---------|------|-------------------|
| **A: Screening** | Quick "what-if" | ±1.5% | ≤5% | ±10% | ≤5% | ±3% |
| **B: Setup** | Equipment decisions | ±1.0% | ≤3.0% | ±6% | ≤3% | ±2% |
| **C: Coaching** | Driver development | ±0.5% | ≤2.5% | ±5% | ≤1.5% | ±1% |
| **D: Engineering** | Component design | ±0.25% | ≤1.5% | ±3% | ≤1% | ±0.5% |

**Current status:** Mean bias ±0.05% (excellent), Std 3.4% (Tier A/B boundary), MAPE 2.66% (Tier B).

**Target:** Tier C (Coaching Quality) — requires reducing std from 3.4% to ≤2.5%.

### Coaching-Specific Criteria (Codex R2)

For "where did I lose time?" coaching, the key requirements are:
- **Lap-time MAE ≤ 1.0-1.5%** (post-calibration) — currently 2.66%, needs improvement
- **Compound-specific bias ≤ 0.5%** — currently up to 4.1% (street), needs correction
- **Corner ranking stability** — the "Top 3 priority corners" must be consistent, not noisy
- **Coaches/drivers tolerate small systematic offset if stable; they reject noisy corner-level errors**

---

## Part 6: Proportional Bias Analysis

### Current Finding

Bland-Altman proportional bias r=0.422 (p=0.07, near-significant). The calibration regression slope is 1.092 (ideal: 1.000), meaning:
- **Fast cars** (GT3, Corvette Z06): predictions tend to be too fast (ratio < 1.0)
- **Slow cars** (Miata, GR86 on street tires): predictions tend to be too slow (ratio > 1.0)

### Root Cause (Codex R2 + own analysis)

This is **confounded with mu**. Fast cars tend to have high-mu tires; slow cars tend to have low-mu tires. The multivariate regression confirms:
- mu: β=-0.119 (p=0.001) ← primary driver
- weight: β=-0.000092 (p=0.015) ← secondary

The proportional bias is likely an artifact of the mu-correlated bias, not a separate phenomenon.

### Recommendation

**Do NOT add a regression calibration layer.** Instead:
1. Fix the underlying mu-utilization correction (Part 4)
2. Re-evaluate proportional bias after correction
3. If proportional bias persists, it indicates a genuine speed-regime deficiency (aero/thermal/transient)

---

## Part 7: Professional Validation Practices

### The Professional Validation Pyramid

Professional simulators (iRacing, rFactor Pro, ACC) use a 3-tier validation hierarchy:

1. **Component validation** (base): Tire model vs force-moment rig data, engine vs dyno, aero vs wind tunnel/CFD
2. **Maneuver validation** (middle): Coast-down for CdA, skidpad for mu, straight-line for power
3. **Full lap telemetry overlay** (top): Speed trace RMSE, G-G diagram correlation, driver subjective feedback

**We operate at tier 3 only (full lap comparison)**, which is appropriate for our model class (point-mass) but limits diagnostic depth.

### What We Can Learn

| Practice | Applicable to us? | Implementation |
|----------|-------------------|----------------|
| Telemetry overlay | YES (we have user sessions) | Compare solver speed profile vs user's fastest lap |
| Grip factor calibration | YES (ChassisSim approach) | Our grip calibration already does this |
| Track laser scan | NO (we use GPS) | Not needed for coaching-grade accuracy |
| Component rig testing | NO | Unnecessary for point-mass model class |
| Driver-in-the-loop | PARTIALLY | User feedback on "does optimal feel achievable?" |

### Published QSS Solver Accuracy Benchmarks

| Source | Model Type | Accuracy | Notes |
|--------|-----------|----------|-------|
| Heilmeier (2022) | QSS, F1 | +0.51% | Shanghai qualifying, extensively tuned |
| OptimumLap | Point-mass QSS | ±0.5-1.5% | When well-calibrated (claimed) |
| ChassisSim | Multi-body | <1% | After grip factor correlation |
| Herrington et al. (2019) | QSS, FSAE | 0.7% mean | Segment discrepancies in tight corners |
| **Our solver** | **Point-mass QSS** | **0.05% mean, 3.4% std** | **Mean is excellent; std needs improvement** |

**Assessment:** Our mean accuracy is competitive with professional tools. Our std (3.4%) is higher, primarily due to the mu-correlated bias. Correcting the mu-utilization gap should bring std to ~2.5%, putting us at coaching-grade quality.

---

## Part 8: Implementation Recommendations

### Phase 1: Validation Script Enhancement (Priority: IMMEDIATE)

Enhance `scripts/physics_realworld_comparison.py` to add:

1. **Extended metrics**: RMSE, MAE, MAPE, Bland-Altman bias+LoA, calibration slope/intercept
2. **Bootstrap CIs**: BCa 95% for mean, std, and per-category means
3. **Residual diagnostics**: Correlations with mu, weight, power; Breusch-Pagan test
4. **Influence detection**: Cook's distance with flagging
5. **Multi-dimensional segmentation**: Grip bands, power bands, per-track, fast/slow split
6. **Outlier detection**: IQR method with reporting
7. **Rich JSON output**: All metrics saved to baseline for regression tracking
8. **Summary table**: Human-readable report with tier assessment

### Phase 2: Dataset Expansion (Priority: HIGH, Ongoing)

1. **Add 2+ tracks** (target: Road Atlanta, VIR, or similar with public lap time databases)
2. **Add FWD/AWD entries** (target: Golf GTI, WRX, Focus RS)
3. **Add more street tire entries** (target: ≥5)
4. **Same-car-different-tire entries** where possible (e.g., GR86 on street vs A052 vs slick at same track)
5. **Target n≥60** for first meaningful CI improvement

### Phase 3: Advanced Diagnostics (Priority: MEDIUM)

1. **Sensitivity analysis**: Run solver with ±5% perturbation on each parameter, rank by lap time impact
2. **Performance-limiting factor breakdown**: Track % brake-limited / corner-limited / power-limited
3. **Leave-One-Track-Out cross-validation**: When ≥4 tracks available
4. **Telemetry comparison**: For selected user sessions, overlay solver speed profile vs actual

---

## Part 9: What NOT to Implement

Based on provider consensus and our dataset constraints:

| Approach | Why Not |
|----------|---------|
| **Mixed-effects model** | n=33 with 3 tracks and 12 cars is too sparse (Codex R2: "fragile", "avoid ambitious random-slope structures") |
| **Sobol sensitivity analysis** | Requires thousands of solver runs; Morris screening is sufficient for our parameter count |
| **Polynomial mu correction** | Risk of overfitting with n=33; per-compound factor is more robust (Codex R2) |
| **Regression calibration layer** | Masks physics deficiencies; fix the underlying model instead |
| **Full Monte Carlo UQ** | Premature — fix known biases first, then quantify remaining uncertainty |

---

## Part 10: Expected Impact

### After Validation Enhancement (Phase 1)

- **No change to accuracy** — these are measurement improvements, not physics changes
- **Much better diagnostic power** — will clearly show WHERE errors come from
- **Automated regression detection** across multiple dimensions (not just mean/std)
- **Confidence-aware reporting** — CIs prevent false confidence in small-n categories

### After Physics Corrections (mu-utilization + Tier 1 improvements)

| Metric | Current | Expected After |
|--------|---------|---------------|
| Mean ratio | 0.9995 | 0.985–0.995 |
| Std ratio | 0.034 | 0.020–0.028 |
| MAPE | 2.66% | 1.5–2.0% |
| Max category bias | 4.1% (street) | ≤2% |
| Exceedances >5% | 3 | 0–1 |
| Tier | A/B boundary | **B/C boundary** |

### After Dataset Expansion (n≥60)

- Bootstrap CI width reduced by ~40%
- Per-category conclusions statistically meaningful (n≥10 per category)
- Track generalization testable (≥4 tracks)
- FWD/AWD bias quantifiable

---

## Sources

### Academic Literature
- Heilmeier (2022), TUM dissertation — QSS LTS validation: https://mediatum.ub.tum.de/doc/1647512/1647512.pdf
- Biniewicz & Pyrz (VSD 2023) — QSS with rider constraints: https://doi.org/10.1080/00423114.2023.2170256
- Tucker et al. (VSD 2021) — QSS vs transient comparison: https://doi.org/10.1080/00423114.2021.1983181
- Christ et al. (VSD 2019) — Variable friction trajectories: https://doi.org/10.1080/00423114.2019.1704804
- Siegler/Deakin/Crolla — SAE 2000-01-3563: https://doi.org/10.4271/2000-01-3563
- Völkl/Muehlmeier/Winner — SAE 2013-01-0806: https://doi.org/10.4271/2013-01-0806
- Costa & Bortolussi — SAE 2016-36-0164: https://doi.org/10.4271/2016-36-0164
- Doyle et al. — SAE 2019-01-0163: https://doi.org/10.4271/2019-01-0163
- Bland & Altman on proportional bias: https://pubmed.ncbi.nlm.nih.gov/10501650/
- Milliken & Milliken — "Race Car Vehicle Dynamics" (canonical reference)

### Industry
- OptimumLap methodology: https://optimumg.com/product/optimumlap/
- ChassisSim grip factor documentation (0.85–0.95 range for club racing)
- rFpro simulation correlation: https://rfpro.com/nismo-adopts-rfpro-for-its-driver-in-the-loop-simulation/
- iRacing dynamic track updates: https://support.iracing.com/support/solutions/articles/31000178217
- FIA on ACC correlation: https://www.fia.com/news/data-key-paul-ricard-success-both-track-and-assetto-corsa-competizione

### Statistical Methods
- SciPy bootstrap BCa: https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html
- Breusch-Pagan test: https://www.statsmodels.org/v0.10.2/generated/statsmodels.stats.diagnostic.het_breuschpagan.html
- Mixed-effects sample sizes: https://pmc.ncbi.nlm.nih.gov/articles/PMC1955447/
