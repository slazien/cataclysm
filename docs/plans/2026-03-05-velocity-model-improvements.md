# Velocity Model Improvements — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Upgrade the forward-backward velocity profile solver from a flat-track constant-mu model to a state-of-the-art solver with data-driven grip calibration, elevation awareness, improved curvature quality, and linked corner analysis.

**Architecture:** The velocity solver (`cataclysm/velocity_profile.py`) is modified in layers: (1) a new `grip_calibration.py` module extracts observed G-G capabilities from telemetry and feeds them into `VehicleParams`, (2) the solver's forward/backward passes gain elevation gradient terms, (3) curvature computation gets a smoothing-spline upgrade, (4) a new `linked_corners.py` module groups adjacent corners and computes compound section metrics. Each layer is independently testable and backward-compatible.

**Tech Stack:** Python 3.11+, NumPy, SciPy (UnivariateSpline, savgol_filter, ConvexHull, DTW via scipy/tslearn), pandas, pytest. No new dependencies except possibly `tslearn` for DTW alignment (P7).

**Research reference:** `tasks/velocity_model_research.md`

---

## Task 1: Data-Driven Grip Calibration (P0 + P1)

**Goal:** Replace constant `mu=1.0` with three semi-axis values extracted from the driver's actual G-G data. This is the highest-impact improvement — fixes "faster than optimal" on every tricky corner.

**Files:**
- Create: `cataclysm/grip_calibration.py`
- Create: `tests/test_grip_calibration.py`
- Modify: `cataclysm/velocity_profile.py` — `VehicleParams` gets new field `calibrated: bool = False`
- Modify: `backend/api/services/pipeline.py:325-370` — auto-calibrate params from G-G data
- Modify: `cataclysm/equipment.py:199-244` — calibration overrides equipment defaults

### Detailed Design

The `grip_calibration.py` module:

```python
@dataclass
class CalibratedGrip:
    """Observed vehicle capability extracted from G-G data."""
    max_lateral_g: float      # 99th percentile |ay| when |ax| < 0.2g
    max_brake_g: float        # 99th percentile |ax| when ax < -0.2g, |ay| < 0.2g
    max_accel_g: float        # 99th percentile |ax| when ax > 0.2g, |ay| < 0.2g
    point_count: int          # number of data points used
    confidence: str           # "high" (>500 pts per axis), "medium" (100-500), "low" (<100)

def calibrate_grip_from_telemetry(
    lateral_g: np.ndarray,
    longitudinal_g: np.ndarray,
    *,
    percentile: float = 99.0,
    cross_axis_threshold: float = 0.2,
    min_points: int = 20,
) -> CalibratedGrip | None:
    """Extract 3-axis grip limits from observed G-G data.

    Uses the 99th percentile (not max) for robustness against GPS spikes.
    Filters to near-pure-axis conditions (other axis < 0.2g) to isolate
    each capability direction.

    Returns None if insufficient data points in any axis.
    """

def apply_calibration_to_params(
    base_params: VehicleParams,
    grip: CalibratedGrip,
) -> VehicleParams:
    """Override VehicleParams with calibrated grip values.

    Rules:
    - max_lateral_g = grip.max_lateral_g
    - max_decel_g = grip.max_brake_g
    - max_accel_g = grip.max_accel_g
    - mu = max(max_lateral_g, max_brake_g)  (overall friction envelope)
    - Sets calibrated=True flag
    - Preserves equipment-derived top_speed, aero, drag coefficients
    """
```

### Step 1: Write failing tests

Create `tests/test_grip_calibration.py` with tests:
1. `test_calibrate_from_clean_data` — synthetic G-G data with known max values
2. `test_calibrate_filters_cross_axis` — verifies cross-axis threshold filtering
3. `test_calibrate_returns_none_insufficient_data` — too few points
4. `test_calibrate_uses_percentile_not_max` — add outlier spike, verify it's ignored
5. `test_apply_calibration_overrides_params` — verify VehicleParams fields updated
6. `test_apply_calibration_preserves_equipment_fields` — aero/drag/top_speed kept
7. `test_confidence_levels` — verify high/medium/low classification

Run: `pytest tests/test_grip_calibration.py -v`
Expected: FAIL (module doesn't exist yet)

### Step 2: Implement grip_calibration.py

Create `cataclysm/grip_calibration.py` with the functions above.

Key implementation detail for `calibrate_grip_from_telemetry`:
```python
# Lateral: points where |longitudinal_g| < threshold
lat_mask = np.abs(longitudinal_g) < cross_axis_threshold
if lat_mask.sum() < min_points:
    return None
max_lat = float(np.percentile(np.abs(lateral_g[lat_mask]), percentile))

# Braking: points where longitudinal_g < -threshold AND |lateral_g| < threshold
brake_mask = (longitudinal_g < -cross_axis_threshold) & (np.abs(lateral_g) < cross_axis_threshold)
if brake_mask.sum() < min_points:
    return None
max_brake = float(np.percentile(np.abs(longitudinal_g[brake_mask]), percentile))

# Acceleration: points where longitudinal_g > threshold AND |lateral_g| < threshold
accel_mask = (longitudinal_g > cross_axis_threshold) & (np.abs(lateral_g) < cross_axis_threshold)
if accel_mask.sum() < min_points:
    return None
max_accel = float(np.percentile(longitudinal_g[accel_mask], percentile))
```

Run: `pytest tests/test_grip_calibration.py -v`
Expected: All PASS

### Step 3: Add `calibrated` flag to VehicleParams

In `cataclysm/velocity_profile.py`, add to the `VehicleParams` dataclass:
```python
calibrated: bool = False  # True when params came from observed G-G data
```

This is backward-compatible (default False).

### Step 4: Integrate calibration into pipeline

In `backend/api/services/pipeline.py`, modify `get_optimal_profile_data()` and `get_optimal_comparison_data()`:

After resolving equipment-based vehicle_params, calibrate from the best lap's G-G data:

```python
from cataclysm.grip_calibration import calibrate_grip_from_telemetry, apply_calibration_to_params

# After: vehicle_params = resolve_vehicle_params(session_id)
# Before: optimal = compute_optimal_profile(...)

# Auto-calibrate from observed G-G data
lat_g = best_lap_df["lateral_g"].to_numpy()
lon_g = best_lap_df["longitudinal_g"].to_numpy()
grip = calibrate_grip_from_telemetry(lat_g, lon_g)
if grip is not None:
    base = vehicle_params or default_vehicle_params()
    vehicle_params = apply_calibration_to_params(base, grip)
```

### Step 5: Run all tests

Run: `pytest tests/test_grip_calibration.py tests/test_velocity_profile.py tests/test_optimal_comparison.py backend/tests/test_pipeline.py -v`
Expected: All PASS

### Step 6: Quality gates + commit

```bash
ruff format cataclysm/grip_calibration.py tests/test_grip_calibration.py
ruff check cataclysm/ tests/ backend/
dmypy run -- cataclysm/ backend/
pytest tests/ backend/tests/ -v
git add cataclysm/grip_calibration.py tests/test_grip_calibration.py cataclysm/velocity_profile.py backend/api/services/pipeline.py
git commit -m "feat: data-driven grip calibration from observed G-G data (P0+P1)"
```

---

## Task 2: Elevation / Gradient Integration (P2)

**Goal:** Add `g*sin(theta)` to the forward/backward solver passes so uphills reduce acceleration and assist braking, and downhills do the opposite. Elevation data comes from the existing `elevation.py` module's smoothed altitude.

**Files:**
- Modify: `cataclysm/velocity_profile.py` — add elevation arrays to solver passes
- Modify: `cataclysm/curvature.py` — `CurvatureResult` gains optional `gradient_array`
- Create: `cataclysm/elevation_profile.py` — compute full-track gradient array from altitude
- Create: `tests/test_elevation_profile.py`
- Modify: `tests/test_velocity_profile.py` — add elevation-aware tests
- Modify: `backend/api/services/pipeline.py` — pass elevation to solver

### Detailed Design

New `elevation_profile.py`:
```python
def compute_gradient_array(
    altitude_m: np.ndarray,
    distance_m: np.ndarray,
    smooth_window_m: float = 50.0,
) -> np.ndarray:
    """Compute sin(theta) at each track point from smoothed altitude.

    Returns array of sin(theta) values. Positive = uphill, negative = downhill.
    Smoothing prevents GPS altitude noise from creating unrealistic gradients.
    """
```

Modify `VehicleParams` or `compute_optimal_profile` signature:
```python
def compute_optimal_profile(
    curvature_result: CurvatureResult,
    params: VehicleParams | None = None,
    *,
    closed_circuit: bool = True,
    gradient_sin: np.ndarray | None = None,  # NEW: sin(theta) per point
) -> OptimalProfile:
```

Modify `_forward_pass` and `_backward_pass` to accept and use gradient:
```python
# Forward pass (line ~186):
gradient_g = gradient_sin[i] if gradient_sin is not None else 0.0
net_accel_g = max(accel_g - drag_g - gradient_g, 0.0)

# Backward pass (line ~213):
gradient_g = gradient_sin[i] if gradient_sin is not None else 0.0
effective_decel_g = decel_g + drag_g + gradient_g
```

Also modify `_compute_max_cornering_speed` for normal force:
```python
if gradient_sin is not None:
    # cos(theta) reduces available grip on slopes
    cos_theta = np.sqrt(1.0 - gradient_sin**2)
    effective_mu = min(params.mu, params.max_lateral_g) * cos_theta
```

### Step 1: Write failing tests for elevation_profile.py

Create `tests/test_elevation_profile.py`:
1. `test_flat_track_zero_gradient` — constant altitude → all-zero gradient
2. `test_uphill_positive_gradient` — linearly increasing altitude → positive sin(theta)
3. `test_downhill_negative_gradient` — linearly decreasing altitude → negative sin(theta)
4. `test_smoothing_reduces_noise` — noisy altitude → smooth gradient
5. `test_steep_grade_values` — 10% grade → sin(theta) ≈ 0.0995

### Step 2: Implement elevation_profile.py

### Step 3: Add gradient tests to test_velocity_profile.py

1. `test_uphill_reduces_speed` — same track, uphill gradient → lower forward-pass speed
2. `test_downhill_increases_speed` — downhill → higher forward-pass speed
3. `test_none_gradient_backward_compatible` — gradient_sin=None → identical to current

### Step 4: Modify velocity_profile.py solver

Add `gradient_sin` parameter to `_forward_pass`, `_backward_pass`, `_compute_max_cornering_speed`, and `compute_optimal_profile`. Apply the physics changes.

### Step 5: Integrate into pipeline

In `backend/api/services/pipeline.py`, after computing curvature:
```python
from cataclysm.elevation_profile import compute_gradient_array

gradient_sin = None
if "altitude_m" in best_lap_df.columns:
    gradient_sin = compute_gradient_array(
        best_lap_df["altitude_m"].to_numpy(),
        best_lap_df["lap_distance_m"].to_numpy(),
    )

optimal = compute_optimal_profile(curvature_result, params=vehicle_params, gradient_sin=gradient_sin)
```

### Step 6: Quality gates + commit

```bash
ruff format cataclysm/elevation_profile.py tests/test_elevation_profile.py
ruff check cataclysm/ tests/ backend/
dmypy run -- cataclysm/ backend/
pytest tests/ backend/tests/ -v
git add cataclysm/elevation_profile.py tests/test_elevation_profile.py cataclysm/velocity_profile.py tests/test_velocity_profile.py backend/api/services/pipeline.py
git commit -m "feat: elevation-aware velocity solver with gradient integration (P2)"
```

---

## Task 3: Smoothing Spline Curvature Upgrade (P3)

**Goal:** Replace the current double-differentiation curvature with physics-constrained smoothing spline that computes curvature analytically from the spline, avoiding noise amplification.

**Files:**
- Modify: `cataclysm/curvature.py` — improve `compute_curvature()` with adaptive smoothing
- Modify: `tests/test_curvature.py` — add curvature quality tests
- No API changes needed — drop-in replacement

### Detailed Design

The current `compute_curvature` already uses `UnivariateSpline` with analytical derivatives. The improvements are:

1. **Adaptive smoothing factor**: Scale smoothing by track length and corner density rather than using a fixed factor. Tighter tracks need less smoothing to preserve corner detail.

2. **Curvature rate limiter**: Post-process curvature to limit `|d(kappa)/ds|` (jerk constraint). This prevents physically impossible curvature transitions that come from GPS noise.

3. **Curvature clamp**: Cap absolute curvature at a physical maximum (e.g., 1/3m = 0.33 for the tightest possible hairpin). GPS errors can produce curvatures >1.0 which are physically impossible.

```python
# Maximum physical curvature: radius = 3m → kappa = 0.33
MAX_PHYSICAL_CURVATURE = 0.33  # 1/m

# Maximum curvature rate of change (jerk limit)
MAX_CURVATURE_RATE = 0.02  # 1/m per meter of distance

def _limit_curvature_rate(
    curvature: np.ndarray,
    step_m: float,
    max_rate: float = MAX_CURVATURE_RATE,
) -> np.ndarray:
    """Forward-backward rate limiter on curvature (like a Savitzky-Golay but physics-based)."""
```

### Step 1: Add curvature quality tests

Add to `tests/test_curvature.py`:
1. `test_curvature_clamped_to_physical_max` — inject extreme curvature GPS noise
2. `test_curvature_rate_limited` — verify no curvature jumps > max_rate
3. `test_known_radius_accuracy` — circular arc of known radius → curvature ≈ 1/R

### Step 2: Implement improvements in curvature.py

### Step 3: Verify existing tests still pass

Run: `pytest tests/test_curvature.py tests/test_velocity_profile.py tests/test_optimal_comparison.py -v`

### Step 4: Quality gates + commit

```bash
ruff format cataclysm/curvature.py tests/test_curvature.py
ruff check cataclysm/ tests/
dmypy run -- cataclysm/
pytest tests/ backend/tests/ -v
git add cataclysm/curvature.py tests/test_curvature.py
git commit -m "feat: physics-constrained curvature with rate limiter and clamp (P3)"
```

---

## Task 4: Linked Corner Grouping (P4)

**Goal:** Detect when adjacent corners are "linked" (car never reaches straight-line speed between them) and compute compound section metrics. This fixes misleading per-corner metrics for chicanes and esses.

**Files:**
- Create: `cataclysm/linked_corners.py`
- Create: `tests/test_linked_corners.py`
- Modify: `cataclysm/corners.py` — `Corner` gains `linked_group_id: int | None = None`
- Modify: `backend/api/services/pipeline.py` — enrich corners with linkage
- Modify: `backend/api/routers/analysis.py` — expose linked group data

### Detailed Design

```python
@dataclass
class CornerGroup:
    """A group of linked corners that form a compound section."""
    group_id: int
    corner_numbers: list[int]
    entry_distance_m: float      # first corner's entry
    exit_distance_m: float       # last corner's exit
    section_type: str            # "chicane" | "esses" | "complex"

@dataclass
class LinkedCornerResult:
    """Result of linked corner analysis."""
    groups: list[CornerGroup]
    corner_to_group: dict[int, int]  # corner_number -> group_id

def detect_linked_corners(
    corners: list[Corner],
    optimal_speed: np.ndarray,
    distance_m: np.ndarray,
    *,
    link_threshold: float = 0.95,  # fraction of max straight speed
) -> LinkedCornerResult:
    """Detect linked corner groups from the velocity profile.

    Two corners are linked if max speed between them < threshold * v_max_straight.
    v_max_straight = max speed on the longest straight segment.
    """

def compute_curvature_variation_index(
    curvature: np.ndarray,
    entry_idx: int,
    exit_idx: int,
) -> float:
    """Curvature Variation Index (CVI) for classifying section complexity.

    CVI = std(curvature) / mean(|curvature|) within the section.
    High CVI = complex (chicane/esses). Low CVI = simple arc.
    """
```

### Step 1: Write failing tests

Create `tests/test_linked_corners.py`:
1. `test_isolated_corners_no_groups` — corners with full-speed straights between → empty groups
2. `test_two_linked_corners` — two corners with never-reached straight speed → one group
3. `test_three_corner_complex` — chicane pattern → single group of 3
4. `test_mixed_linked_and_isolated` — some linked, some not
5. `test_cvi_simple_arc` — single-radius arc → low CVI
6. `test_cvi_chicane` — alternating curvature → high CVI

### Step 2: Implement linked_corners.py

### Step 3: Add `linked_group_id` to Corner dataclass

### Step 4: Integrate into pipeline

After corner detection and optimal profile computation, run linked corner analysis and tag each corner.

### Step 5: Quality gates + commit

```bash
ruff format cataclysm/linked_corners.py tests/test_linked_corners.py
ruff check cataclysm/ tests/ backend/
dmypy run -- cataclysm/ backend/
pytest tests/ backend/tests/ -v
git add cataclysm/linked_corners.py tests/test_linked_corners.py cataclysm/corners.py backend/api/services/pipeline.py backend/api/routers/analysis.py
git commit -m "feat: linked corner detection and compound section metrics (P4)"
```

---

## Task 5: Per-Corner Mu Calibration (P5)

**Goal:** Instead of a single global mu, allow per-corner effective friction that implicitly captures banking, surface variation, and driver confidence differences.

**Files:**
- Modify: `cataclysm/grip_calibration.py` — add `calibrate_per_corner_grip()`
- Modify: `tests/test_grip_calibration.py` — add per-corner tests
- Modify: `cataclysm/velocity_profile.py` — accept per-point mu array
- Modify: `tests/test_velocity_profile.py` — per-point mu tests

### Detailed Design

```python
def calibrate_per_corner_grip(
    lateral_g: np.ndarray,
    distance_m: np.ndarray,
    corners: list[Corner],
    *,
    percentile: float = 99.0,
    min_points: int = 10,
) -> dict[int, float]:
    """Extract per-corner effective mu from observed lateral G.

    For each corner zone: mu_eff = percentile(|lateral_g|) / G

    Returns dict mapping corner_number -> mu_effective.
    Corners with too few points are excluded.
    """
```

Modify `_compute_max_cornering_speed` to accept an optional per-point mu array:
```python
def _compute_max_cornering_speed(
    abs_curvature: np.ndarray,
    params: VehicleParams,
    mu_array: np.ndarray | None = None,  # NEW: per-point mu override
) -> np.ndarray:
```

If `mu_array` is provided, use `mu_array[i]` instead of `params.mu` at each point. Points outside corner zones use the global mu.

### Step 1: Write failing tests

Add to `tests/test_grip_calibration.py`:
1. `test_per_corner_grip_extraction` — synthetic data with different lateral G per corner
2. `test_per_corner_grip_min_points_filter` — corners with too few points excluded

Add to `tests/test_velocity_profile.py`:
3. `test_per_point_mu_changes_cornering_speed` — higher mu → higher max cornering speed
4. `test_none_mu_array_backward_compatible` — mu_array=None identical to current

### Step 2: Implement per-corner calibration

### Step 3: Thread mu_array through the solver

### Step 4: Integrate into pipeline (build mu_array from per-corner calibration + global for straights)

### Step 5: Quality gates + commit

```bash
ruff format cataclysm/grip_calibration.py tests/test_grip_calibration.py cataclysm/velocity_profile.py tests/test_velocity_profile.py
ruff check cataclysm/ tests/ backend/
dmypy run -- cataclysm/ backend/
pytest tests/ backend/tests/ -v
git add cataclysm/grip_calibration.py tests/test_grip_calibration.py cataclysm/velocity_profile.py tests/test_velocity_profile.py backend/api/services/pipeline.py
git commit -m "feat: per-corner mu calibration from observed lateral G (P5)"
```

---

## Task 6: Banking / Camber Model (P6)

**Goal:** Apply banking corrections to available lateral grip at corners where the track profile specifies banking angles.

**Files:**
- Modify: `cataclysm/corners.py` — `Corner` gains `banking_deg: float | None = None`
- Modify: `cataclysm/track_db.py` — add banking data to `OfficialCorner`
- Create: `cataclysm/banking.py` — banking correction functions
- Create: `tests/test_banking.py`
- Modify: `cataclysm/velocity_profile.py` — apply banking to cornering speed limit

### Detailed Design

```python
# cataclysm/banking.py

def effective_mu_with_banking(
    mu: float,
    banking_deg: float,
) -> float:
    """Compute effective friction coefficient with banking.

    mu_eff = (mu + tan(theta)) / (1 - mu * tan(theta))

    Positive banking = banked toward corner center (more grip).
    Negative banking = off-camber (less grip).
    """

def apply_banking_to_mu_array(
    mu_array: np.ndarray,
    distance_m: np.ndarray,
    corners: list[Corner],
) -> np.ndarray:
    """Apply per-corner banking corrections to the mu array.

    For each corner with banking_deg set, adjust mu in that zone.
    Returns a copy of mu_array with corrections applied.
    """
```

### Step 1: Write failing tests

1. `test_zero_banking_no_change` — 0 deg banking → mu unchanged
2. `test_positive_banking_increases_mu` — 5 deg → mu_eff > mu
3. `test_negative_banking_decreases_mu` — -3 deg → mu_eff < mu
4. `test_banking_array_applied_to_corners_only` — non-corner zones unchanged

### Step 2: Implement banking.py

### Step 3: Add banking_deg to Corner and OfficialCorner

### Step 4: Integrate into solver (apply banking before/after per-corner mu)

### Step 5: Quality gates + commit

```bash
ruff format cataclysm/banking.py tests/test_banking.py
ruff check cataclysm/ tests/ backend/
dmypy run -- cataclysm/ backend/
pytest tests/ backend/tests/ -v
git add cataclysm/banking.py tests/test_banking.py cataclysm/corners.py cataclysm/track_db.py cataclysm/velocity_profile.py
git commit -m "feat: banking/camber corrections for effective lateral grip (P6)"
```

---

## Task 7: Multi-Lap Curvature Averaging (P7)

**Goal:** Average curvature across multiple laps to reduce GPS noise. 10 laps → 3.2x noise reduction.

**Files:**
- Create: `cataclysm/curvature_averaging.py`
- Create: `tests/test_curvature_averaging.py`
- Modify: `backend/api/services/pipeline.py` — use multi-lap averaged curvature

### Detailed Design

```python
def average_lap_coordinates(
    laps: dict[int, pd.DataFrame],
    step_m: float = 0.7,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Average XY coordinates across multiple laps in the distance domain.

    All laps are re-parameterized by distance. Coordinates at each distance
    point are averaged across laps. This reduces random GPS noise by sqrt(N).

    Returns (distance_m, avg_x, avg_y).
    """

def compute_averaged_curvature(
    laps: dict[int, pd.DataFrame],
    step_m: float = 0.7,
    smoothing: float | None = None,
) -> CurvatureResult:
    """Compute curvature from multi-lap averaged coordinates.

    Steps:
    1. Convert each lap's lat/lon to local XY
    2. Re-parameterize by distance
    3. Average XY at each distance point
    4. Fit smoothing spline to averaged track
    5. Compute curvature analytically
    """
```

### Step 1: Write failing tests

1. `test_single_lap_identical` — one lap → same as current curvature
2. `test_multi_lap_reduces_noise` — 10 noisy laps → smoother curvature
3. `test_curvature_preserves_shape` — circular arc with noise → curvature ≈ 1/R after averaging

### Step 2: Implement curvature_averaging.py

### Step 3: Integrate into pipeline (use all coaching laps for averaging)

### Step 4: Quality gates + commit

```bash
ruff format cataclysm/curvature_averaging.py tests/test_curvature_averaging.py
ruff check cataclysm/ tests/ backend/
dmypy run -- cataclysm/ backend/
pytest tests/ backend/tests/ -v
git add cataclysm/curvature_averaging.py tests/test_curvature_averaging.py backend/api/services/pipeline.py
git commit -m "feat: multi-lap curvature averaging for GPS noise reduction (P7)"
```

---

## Task 8: Full GGV Surface (P8)

**Goal:** Build speed-bucketed G-G envelopes that capture how the car's capabilities change with speed (power limitation at low speed, aero grip at high speed).

**Files:**
- Modify: `cataclysm/grip_calibration.py` — add `GGVSurface` class and builder
- Modify: `tests/test_grip_calibration.py` — add GGV tests
- Modify: `cataclysm/velocity_profile.py` — solver queries GGV surface at each speed

### Detailed Design

```python
@dataclass
class GGVSurface:
    """Speed-bucketed G-G envelope surface.

    speed_bins: array of speed bin centers (m/s)
    envelopes: for each speed bin, array of max combined-G per angular sector
    """
    speed_bins: np.ndarray           # shape (n_speed_bins,)
    envelopes: list[np.ndarray]      # each shape (n_sectors,), one per speed bin
    n_sectors: int = 36

def build_ggv_surface(
    speed_mps: np.ndarray,
    lateral_g: np.ndarray,
    longitudinal_g: np.ndarray,
    *,
    speed_bin_width: float = 5.0,    # m/s per bin (~11 mph)
    n_sectors: int = 36,
    percentile: float = 99.0,
) -> GGVSurface:
    """Build a GGV surface from telemetry data.

    At each speed bucket, builds a G-G envelope using angular sectors.
    Uses percentile (not max) for robustness.
    """

def query_ggv_max_g(
    surface: GGVSurface,
    speed: float,
    angle_rad: float,
) -> float:
    """Query the GGV surface for max available G at a given speed and direction.

    Interpolates between speed bins. Returns max combined G in the given direction.
    """
```

### Step 1: Write failing tests

1. `test_ggv_surface_from_synthetic_data` — known speed-dependent limits
2. `test_ggv_query_interpolates_between_bins` — speed between two bins
3. `test_ggv_power_limited_at_low_speed` — low speed bin has lower accel G
4. `test_ggv_aero_boost_at_high_speed` — high speed bin has higher lateral G

### Step 2: Implement GGV surface builder and query

### Step 3: Modify solver to use GGV surface (optional override to `_available_accel`)

### Step 4: Quality gates + commit

```bash
ruff format cataclysm/grip_calibration.py tests/test_grip_calibration.py cataclysm/velocity_profile.py
ruff check cataclysm/ tests/ backend/
dmypy run -- cataclysm/ backend/
pytest tests/ backend/tests/ -v
git add cataclysm/grip_calibration.py tests/test_grip_calibration.py cataclysm/velocity_profile.py
git commit -m "feat: speed-bucketed GGV surface for power/aero-aware grip (P8)"
```

---

## Task 9: Clothoid Spline Curvature (P9)

**Goal:** Fit piecewise clothoid (Euler spiral) segments to the track, producing curvature that is piecewise-linear by construction — physically correct for road/track design.

**Files:**
- Create: `cataclysm/clothoid_fitting.py`
- Create: `tests/test_clothoid_fitting.py`
- Modify: `cataclysm/curvature.py` — add `method="clothoid"` option

### Detailed Design

This is the most complex task. Clothoid fitting solves a scalar equation per segment (Bertolazzi & Frego 2013). The implementation:

1. Segment the track into approximately straight sections (|heading_rate| < threshold)
2. Between each pair of straight sections, fit a clothoid transition curve
3. The clothoid has linearly varying curvature by definition
4. Concatenate all segments to get the full curvature profile

```python
def fit_clothoid_segment(
    x0: float, y0: float, theta0: float,
    x1: float, y1: float, theta1: float,
) -> tuple[float, float, float]:
    """Fit a single clothoid segment between two points.

    Returns (kappa0, kappa1, arc_length) — the curvature at entry,
    curvature at exit, and arc length. Curvature varies linearly between.
    """

def compute_clothoid_curvature(
    x: np.ndarray,
    y: np.ndarray,
    distance_m: np.ndarray,
) -> np.ndarray:
    """Compute piecewise-clothoid curvature for a track.

    Steps:
    1. Compute heading at each point
    2. Identify segment boundaries (significant heading changes)
    3. Fit clothoid between consecutive boundaries
    4. Interpolate curvature at all distance points
    """
```

### Step 1: Write failing tests

1. `test_clothoid_straight_line` — straight segment → zero curvature
2. `test_clothoid_circular_arc` — constant-radius arc → constant curvature
3. `test_clothoid_transition` — straight-to-curve → linearly increasing curvature
4. `test_clothoid_produces_smoother_than_spline` — noisy GPS → lower curvature variance

### Step 2: Implement clothoid_fitting.py

### Step 3: Add `method="clothoid"` to compute_curvature

### Step 4: Quality gates + commit

```bash
ruff format cataclysm/clothoid_fitting.py tests/test_clothoid_fitting.py
ruff check cataclysm/ tests/
dmypy run -- cataclysm/
pytest tests/ -v
git add cataclysm/clothoid_fitting.py tests/test_clothoid_fitting.py cataclysm/curvature.py
git commit -m "feat: piecewise clothoid curvature fitting (P9)"
```

---

## Task 10: Tire Thermal Model (P10)

**Goal:** Simple first-lap warmup multiplier that reduces grip from 0.75 to 1.0 over the first lap, capturing the dominant thermal effect. **Extended with per-compound warmup rates** from tire-grip research (`tasks/tire_grip_model_integration_research.md`).

**Files:**
- Modify: `cataclysm/grip_calibration.py` — add `compute_warmup_factor()`
- Modify: `cataclysm/equipment.py` — add `warmup_laps` default per `TireCompoundCategory`
- Modify: `tests/test_grip_calibration.py` — add warmup tests

### Detailed Design

```python
def compute_warmup_factor(
    lap_number: int,
    *,
    cold_factor: float = 0.75,
    warmup_laps: float = 1.5,
) -> float:
    """Compute tire warmup multiplier for a given lap number.

    Lap 1: starts at cold_factor, ramps to 1.0 by end.
    Lap 2+: returns 1.0 (tires warm).

    The warmup is modeled as: factor = min(1.0, cold_factor + (1 - cold_factor) * lap / warmup_laps)
    """
```

**Per-compound warmup rates** (from tire-grip research):
- Street tires (400+ TW): `warmup_laps = 0.5` — warm up quickly
- 200TW Performance: `warmup_laps = 1.0`
- R-compound (40-100 TW): `warmup_laps = 1.5`
- Slick: `warmup_laps = 2.5` — need most warmup

Add a `warmup_laps` default per `TireCompoundCategory` in `equipment.py`, similar to the existing `_CATEGORY_ACCEL_G` table. When the user has an equipment profile with a known tire compound, use the compound-specific warmup rate instead of the generic default.

This is applied as a multiplier to the calibrated grip values for first-lap analysis.

### Step 1: Write failing tests

1. `test_warmup_factor_first_lap` — lap 1 → ~0.875 (midpoint of warmup)
2. `test_warmup_factor_second_lap` — lap 2 → 1.0
3. `test_warmup_factor_custom_cold` — custom cold_factor
4. `test_warmup_factor_compound_specific` — R-compound warmup_laps=1.5 vs street warmup_laps=0.5

### Step 2: Implement

### Step 3: Quality gates + commit

```bash
ruff format cataclysm/grip_calibration.py cataclysm/equipment.py tests/test_grip_calibration.py
ruff check cataclysm/ tests/
dmypy run -- cataclysm/
pytest tests/ -v
git add cataclysm/grip_calibration.py cataclysm/equipment.py tests/test_grip_calibration.py
git commit -m "feat: tire thermal warmup model with per-compound rates (P10)"
```

---

## Task 11: Tire Load Sensitivity (P11)

**Goal:** Model how tire friction decreases with increasing vertical load using a simple degressive formula. **Extended with per-compound load sensitivity exponents** from tire-grip research (`tasks/tire_grip_model_integration_research.md`).

**Files:**
- Modify: `cataclysm/grip_calibration.py` — add `load_sensitive_mu()`
- Modify: `cataclysm/equipment.py` — add `load_sensitivity_exponent` default per `TireCompoundCategory`
- Modify: `tests/test_grip_calibration.py` — add load sensitivity tests

### Detailed Design

```python
def load_sensitive_mu(
    mu_ref: float,
    fz_ref: float,
    fz_actual: float,
    sensitivity: float = -0.05,
) -> float:
    """Compute load-sensitive friction coefficient.

    mu(Fz) = mu_ref + sensitivity * (Fz_actual - Fz_ref)

    sensitivity is typically ~-0.05 per kN (mu decreases with load).
    """
```

**Per-compound load sensitivity** (from tire-grip research):

Power-law model: `Fy = mu_ref * Fz^n` where n < 1 makes grip degressive.

| Compound | Load sensitivity exponent (n) |
|----------|------------------------------|
| Street (400+ TW) | ~0.85 (less sensitive) |
| 200TW Performance | ~0.82 |
| R-compound (40-100 TW) | ~0.78 (more sensitive) |
| Slick | ~0.75 (most sensitive) |

Softer compounds have *higher* load sensitivity (lower n) because softer rubber deforms more under high contact pressure. Add `load_sensitivity_exponent` default per `TireCompoundCategory` in `equipment.py`.

**Also add per-compound friction circle shape** (from research):
- Street: p ≈ 1.8 (diamond-like, less combined grip)
- 200TW: p ≈ 2.0 (standard ellipse)
- R-compound: p ≈ 2.2 (more square, better combined grip)
- Slick: p ≈ 2.3 (most square)

Add `friction_circle_exponent` default per compound in `equipment_to_vehicle_params()`.

This is the lowest-priority item because most of the load sensitivity effect is already captured by the data-driven grip calibration (P0). It's primarily useful when we have vehicle weight data from the equipment system and want to model weight transfer effects explicitly.

### Step 1: Write failing tests

1. `test_load_sensitivity_higher_load_lower_mu` — more load → lower mu
2. `test_load_sensitivity_at_reference` — Fz = Fz_ref → mu = mu_ref
3. `test_load_sensitivity_clamped` — mu never goes below 0.1
4. `test_compound_specific_load_sensitivity` — R-compound (n=0.78) more sensitive than street (n=0.85)
5. `test_compound_friction_circle_exponent` — R-compound p=2.2 vs street p=1.8

### Step 2: Implement

### Step 3: Quality gates + commit

```bash
ruff format cataclysm/grip_calibration.py cataclysm/equipment.py tests/test_grip_calibration.py
ruff check cataclysm/ tests/
dmypy run -- cataclysm/
pytest tests/ -v
git add cataclysm/grip_calibration.py cataclysm/equipment.py tests/test_grip_calibration.py
git commit -m "feat: tire load sensitivity with per-compound exponents (P11)"
```

---

## Execution Order

Tasks are ordered by priority (P0 first) and dependency:

```
Task 1 (P0+P1: Grip calibration) ──── no dependencies
Task 2 (P2: Elevation)           ──── no dependencies (parallel with Task 1)
Task 3 (P3: Curvature upgrade)   ──── no dependencies (parallel with Task 1, 2)
Task 4 (P4: Linked corners)      ──── depends on Task 1 (needs optimal profile)
Task 5 (P5: Per-corner mu)       ──── depends on Task 1 (extends grip_calibration.py)
Task 6 (P6: Banking)             ──── depends on Task 5 (applies to mu_array)
Task 7 (P7: Multi-lap averaging) ──── depends on Task 3 (extends curvature module)
Task 8 (P8: GGV surface)         ──── depends on Task 1 (extends grip_calibration.py)
Task 9 (P9: Clothoid fitting)    ──── depends on Task 3 (extends curvature module)
Task 10 (P10: Thermal model)     ──── depends on Task 1 (extends grip_calibration.py)
Task 11 (P11: Load sensitivity)  ──── depends on Task 1 (extends grip_calibration.py)
```

**Parallelizable first wave:** Tasks 1, 2, 3 can all be done simultaneously.
**Second wave:** Tasks 4, 5, 7, 8 after Task 1/3 complete.
**Third wave:** Tasks 6, 9, 10, 11 after their dependencies.

---

## Frontend Changes (all tasks)

The frontend's `CornerSpeedGapPanel.tsx` and `CornerDetailPanel.tsx` will automatically benefit from improved model accuracy — no UI code changes needed. The speed gaps and time costs will simply be more accurate.

Optional frontend enhancements (not in scope for this plan):
- Show "calibrated" badge when grip is data-driven
- Display linked corner groups in the corner tab
- Show elevation profile overlay on the speed trace
- Display GGV surface visualization in the G-G diagram chart
