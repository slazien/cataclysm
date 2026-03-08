# Solver Review: Curvature Computation — Multi-Model Findings

> Task 1.4 from `docs/plans/2026-03-08-solver-review-multi-model.md`

## Models Used
- 🟡 Gemini 2.5 Pro — Academic literature & GPS signal processing
- 🔵 Claude Opus 4 — Implementation code review

---

## 1. Coordinate Projection

### Finding: Already correct ✅
- Our `_latlon_to_local_xy()` applies `cos(mean_lat_rad)` correction to longitude
- This is effectively a **Local Tangent Plane (ENU)** approximation
- At racetrack scale (2-5km), residual error is sub-centimeter — no need for UTM
- 🟡 Gemini initially flagged equirectangular concern, but our implementation already handles it

---

## 2. Spline Smoothing

### Assessment: Acceptable, tuning-dependent
- 🟡 Gemini: "Your spline approach can be highly effective, but its performance is critically dependent on tuning `s`."
- Current: `s = n * step_m * DEFAULT_SMOOTHING_FACTOR_PER_POINT`
- A Kalman filter would be "more optimal" (Gemini) but significantly more complex
- 🟡 Gemini: The smoothing factor should be validated by comparing spline output with GPS + IMU data if available

---

## 3. Post-processing Pipeline

### Rate limiter (0.02 1/m²)
- 🟡 Gemini: "This value seems very high for a physical limit and likely serves more as a filter for data processing artifacts."
- Physical analysis: A gentle transition from straight (κ=0) to 100m radius (κ=0.01) over 50m = dκ/ds of 0.0002 1/m². Our limit of 0.02 is 100× higher.
- **Conclusion**: This is a **noise-spike suppressor**, not a physics constraint. It only activates on severe GPS glitches. Correctly calibrated for 0.5m GPS noise.

### Savitzky-Golay filter
- 🟡 Gemini: "Not strictly redundant [with spline], but its necessity may indicate a sub-optimal choice for the spline's smoothing factor."
- Our code applies SavGol conditionally (`savgol_window > 0`), default is 0 (off). So in practice it's a tuning knob, not a core part of the pipeline.

### Physical clamp (0.33 1/m ≈ 3m radius)
- 🟡 Gemini: "The tightest hairpins on major racetracks (e.g., Monaco's Fairmont) have a centerline radius of 10-15 meters."
- The clamp's real purpose is preventing numerical divergence from degenerate spline points
- Value is correct as a safety net — no real track features approach this limit

---

## 4. Clothoid Fitting (dead code)

### Assessment: Better for canonical reference, worse for actual laps
- 🟡 Gemini: "For creating a canonical reference track model, clothoid fitting is superior. For analyzing the actual path a driver took on a specific lap, your spline-based approach is more faithful."
- **Recommendation**: Keep clothoid as dead code for now. If we ever build a "track geometry model" separate from driver-specific curvature, clothoid fitting would be appropriate. Not a priority for coaching.

---

## 5. Multi-lap Averaging

### Finding: Partially addressed, room for improvement
- Our `average_lap_coordinates()` uses a **common reference origin** (first lap's first point) — good
- Averages in **distance domain** via interpolation — reduces ambiguity vs 2D averaging
- 🟡 Gemini: "Averaging raw GPS coordinates without alignment is a significant source of error" → suggests ICP alignment
- **However**: Distance-domain averaging is better than raw 2D averaging. Different racing lines at the same distance can blur apexes by ~1-2m laterally, but GPS noise is 0.5m, so averaging N laps still reduces noise by √N.
- **Verdict**: Current approach is acceptable for coaching. ICP alignment would be a nice-to-have for sub-metre accuracy.

---

## 6. GPS Curvature Error Bounds

### Key insight from literature (🟡 Gemini):
- "Curvature is based on the second derivative of position. Differentiation amplifies noise."
- Position error ε → curvature error proportional to d²ε/ds²
- With 0.5m GPS noise and our smoothing pipeline, expect ±5-10% curvature error at sharp corners, ±20-30% at gentle curves
- Gold standard: GPS + IMU fusion via Kalman filter (beyond current scope)

---

## 7. Actionable Findings

### Critical Bugs: None found

### Material Improvements
| # | Finding | Source | File | Effort | Impact |
|---|---------|--------|------|--------|--------|
| C1 | Document rate limiter as noise guard, not physics | 🟡 Gemini | `curvature.py` | Trivial | Clarity |
| C2 | Consider ICP lap alignment before averaging | 🟡 Gemini | `curvature_averaging.py` | Medium | ~1-2m apex accuracy |

### Nice-to-haves
| # | Finding | Source | Effort | Impact |
|---|---------|--------|--------|--------|
| C3 | Tune spline `s` to potentially eliminate SavGol need | 🟡 Gemini | Medium | Code simplification |
| C4 | Clothoid for canonical track reference (future) | 🟡 Gemini | High | Better track geometry |

---

## References
- Godha & Cannon, "Vehicle-motion estimation using a GPS/IMU integrated system"
- GNSS-based trajectory analysis accuracy (2018 IPIN Conference)
- Consensus: raw GPS position insufficient for reliable curvature without filtering or sensor fusion
