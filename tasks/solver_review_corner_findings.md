# Solver Review: Corner Detection & Speed Gap — Multi-Model Findings

> Task 1.3 from `docs/plans/2026-03-08-solver-review-multi-model.md`

## Models Used
- 🟡 Gemini 2.5 Pro — Industry practice & academic references
- 🔵 Claude Opus 4 — Implementation review

---

## 1. Apex Window (±30%)

### Verdict: Appropriate ✅
- 🟡 Gemini: "A very appropriate and robust choice for an automated algorithm."
- Adaptive window (% of corner length) is superior to fixed-size window
- The `min 20m total` width is a crucial safeguard for very short corners
- MoTeC i2 Pro relies on manually defined sectors — our automated approach is comparable to MoTeC's "Track Report" auto-segmentation
- **No change needed**

---

## 2. Heading Rate Threshold (1 deg/m)

### Verdict: Solid default ✅
- 🟡 Gemini: Too low (<0.5) flags straight-line corrections. Too high (>2.0) misses long sweepers.
- 1 deg/m is a good balance for most tracks
- **Recommendation**: Could be per-track configurable, but not a priority

---

## 3. Brake Point Detection

### Verdict: Reasonable, could be more robust
- 🟡 Gemini: "Deceleration onset can be triggered by slight throttle lifts, bumps, or aero effects."
- **Recommendation**: Define brake point as first data point where longitudinal G drops below a threshold (e.g., -0.2G or -2.0 m/s²), not just any deceleration.
- Note: Our code uses 150m search for actual vs 200m for optimal — this is valid since optimal may have different braking strategy.

---

## 4. Chicane/Linked Corner Handling

### Verdict: Excellent ✅
- 🟡 Gemini: "Your `linked_corners` module with speed-based linkage and Curvature Variation Index is excellent and sophisticated."
- "More advanced than simply merging corners based on distance"
- **However**: This module is **dead code** — not wired into the pipeline. Should be connected.

---

## 5. GPS Noise Impact (0.5m RaceBox)

### Key Concern
- 🟡 Gemini: "You **must** apply a low-pass filter to raw position/speed data before any analysis."
- Suggests Butterworth filter (2nd-4th order, 1-3 Hz cutoff) as standard in motorsport
- A 0.5m position error over 0.1s can create significant speed/heading spikes
- **Assessment**: Our spline smoothing in `compute_curvature()` serves this purpose for curvature. Speed data from RaceBox comes pre-filtered at the device level (Kalman filter on GNSS). But heading rate for corner detection may benefit from additional smoothing.

---

## 6. Merge Gap (30m)

### Verdict: Reasonable ✅
- Prevents multi-apex corners (e.g., Road America Carousel) from being split
- Good backup for joining chicanes alongside `linked_corners`
- Could be per-track configurable but not a priority

---

## 7. Trapezoidal Time Integration

### Verdict: Perfectly sufficient ✅
- 🟡 Gemini: "The accuracy gained by more complex methods is negligible and would be completely overshadowed by GPS noise."
- At our 0.7m step size and 25Hz GPS, this is more than adequate

---

## 8. Comparison to MoTeC i2 Pro

### Key difference
- 🟡 Gemini: "The key difference isn't the initial detection algorithm but the lack of a manual review and refinement loop."
- MoTeC workflow: auto-detect → manual sector adjustment → maths channels for min(speed)
- Our workflow: auto-detect → automated analysis (no human-in-loop)
- For a coaching product, the fully automated approach is appropriate — users aren't data engineers

---

## 9. Actionable Findings

### Issues to Address
| # | Finding | Source | File | Effort | Impact |
|---|---------|--------|------|--------|--------|
| **CR1** | **Wire linked_corners into pipeline** | 🟡 Gemini + Phase 0 audit | `pipeline.py` | Medium | Feature gap |
| CR2 | Brake point detection: use G-threshold (e.g., -0.2G) instead of just onset | 🟡 Gemini | `corners.py` or `optimal_comparison.py` | Low | Robustness |

### Nice-to-haves
| # | Finding | Source | Effort |
|---|---------|--------|--------|
| CR3 | Per-track configurable heading rate threshold | 🟡 Gemini | Low |
| CR4 | Pre-filter heading rate data for corner detection | 🟡 Gemini | Low |

---

## References
- SAE 2011-01-0268: "A Method for the Automatic-Detection of Track Sections for Motorsport Applications"
- Mauch et al. 2018: "Data-driven virtual race track mapping and corner analysis"
- Cossalter et al. 2011: "Characterization of the Cornering Phase" (corner phase definitions)
- MoTeC i2 Pro: Track Report auto-segmentation, manual sector refinement
