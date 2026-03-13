# Per-Corner Braking Calibration (C+B) Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the physics-optimal brake points corner-specific instead of a flat global scalar, so the model matches what the driver's best laps actually demonstrate at each corner.

**Architecture:** Two stacked changes: (C) Include the best lap's braking telemetry in grip calibration — braking G doesn't have the self-reference problem that cornering does because braking happens *before* the corner, not through it. (B) Compute per-corner braking G (p95 of |longitudinal_g| in each corner's braking zone) and feed a per-distance `decel_array` into the backward pass, mirroring how `mu_array` already works for cornering grip. The `_available_accel()` friction circle function gains an optional per-point decel override.

**Tech Stack:** Python 3.11+, numpy, dataclasses, pytest

---

## File Structure

| Action | File | Responsibility |
|--------|------|---------------|
| Modify | `cataclysm/grip_calibration.py` | New `calibrate_per_corner_braking_g()` function |
| Modify | `cataclysm/velocity_profile.py` | `_available_accel()` + `_backward_pass()` accept per-point decel; `compute_optimal_profile()` accepts `decel_array` |
| Modify | `backend/api/services/pipeline.py` | (C) include best lap in braking calibration; (B) build decel_array and pass to solver |
| Modify | `tests/test_grip_calibration.py` | Tests for `calibrate_per_corner_braking_g()` |
| Modify | `tests/test_velocity_profile.py` | Tests for decel_array in backward pass |
| Modify | `tests/test_pipeline_calibration.py` or relevant pipeline test | Tests for best-lap inclusion + decel_array wiring |

---

## Chunk 1: Per-Corner Braking Calibration Function

### Task 1: `calibrate_per_corner_braking_g()` in grip_calibration.py

Mirror `calibrate_per_corner_grip()` (lines 257-315) but for braking G in the braking zone preceding each corner.

**Files:**
- Modify: `cataclysm/grip_calibration.py` (add new function after `calibrate_per_corner_grip`)
- Test: `tests/test_grip_calibration.py`

- [ ] **Step 1: Write the failing test for basic per-corner braking G extraction**

```python
class TestCalibratePerCornerBrakingG:
    """Tests for calibrate_per_corner_braking_g()."""

    def test_extracts_braking_g_in_braking_zone(self) -> None:
        """Extract p95 of |longitudinal_g| from the braking zone before each corner."""
        rng = np.random.default_rng(42)
        n = 1000
        distance_m = np.linspace(0, 2000, n)
        # Pure braking zone for corner 1: 100m-200m, lonG ~ -1.2 ± noise
        longitudinal_g = rng.normal(-0.3, 0.1, n)  # background mild braking
        brake_zone_mask = (distance_m >= 100) & (distance_m <= 200)
        longitudinal_g[brake_zone_mask] = rng.normal(-1.2, 0.05, brake_zone_mask.sum())

        corners = [
            Corner(
                number=1,
                entry_distance_m=200.0,
                exit_distance_m=350.0,
                apex_distance_m=275.0,
                min_speed_mps=20.0,
                brake_point_m=100.0,
                peak_brake_g=1.25,
                throttle_commit_m=320.0,
            ),
        ]

        from cataclysm.grip_calibration import calibrate_per_corner_braking_g

        result = calibrate_per_corner_braking_g(longitudinal_g, distance_m, corners)
        assert 1 in result
        # p95 of |lonG| where lonG ~ N(-1.2, 0.05) should be ~1.28
        assert result[1] == pytest.approx(1.2, abs=0.15)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /mnt/d/OneDrive/Dokumenty/vscode/cataclysm && source .venv/bin/activate && pytest tests/test_grip_calibration.py::TestCalibratePerCornerBrakingG::test_extracts_braking_g_in_braking_zone -v`
Expected: FAIL with `ImportError: cannot import name 'calibrate_per_corner_braking_g'`

- [ ] **Step 3: Implement `calibrate_per_corner_braking_g()`**

Add to `cataclysm/grip_calibration.py` after `calibrate_per_corner_grip()` (after line 315):

```python
def calibrate_per_corner_braking_g(
    longitudinal_g: np.ndarray,
    distance_m: np.ndarray,
    corners: list[Corner],
    *,
    percentile: float = 95.0,
    min_points: int = 10,
    braking_zone_margin_m: float = 200.0,
) -> dict[int, float]:
    """Extract per-corner braking G from the braking zone preceding each corner.

    For each corner, the braking zone is defined as
    [brake_point_m, entry_distance_m] if brake_point_m is known, otherwise
    [entry_distance_m - braking_zone_margin_m, entry_distance_m].

    Only points where longitudinal_g < -0.2G (actual braking) are included.

    Parameters
    ----------
    longitudinal_g
        Array of longitudinal acceleration (G). Negative = braking.
    distance_m
        Array of distance values (m), same length as *longitudinal_g*.
    corners
        List of detected corners with brake_point_m and entry_distance_m.
    percentile
        Percentile to extract from |longitudinal_g| in each zone (default 95.0).
    min_points
        Minimum braking data points in a zone to include it.
    braking_zone_margin_m
        Fallback zone length before entry when brake_point_m is unknown.

    Returns
    -------
    dict[int, float]
        Mapping of corner_number -> braking_g (positive).
        Corners with insufficient braking data are omitted.
    """
    if len(corners) == 0:
        return {}

    result: dict[int, float] = {}

    for corner in corners:
        # Define braking zone boundaries
        zone_end = corner.entry_distance_m
        if corner.brake_point_m is not None:
            zone_start = corner.brake_point_m
        else:
            zone_start = zone_end - braking_zone_margin_m

        # Select points in the braking zone that are actually braking
        zone_mask = (
            (distance_m >= zone_start)
            & (distance_m <= zone_end)
            & (longitudinal_g < -0.2)
        )
        n_points = int(zone_mask.sum())

        if n_points < min_points:
            continue

        braking_g = float(np.percentile(np.abs(longitudinal_g[zone_mask]), percentile))
        result[corner.number] = braking_g

    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_grip_calibration.py::TestCalibratePerCornerBrakingG::test_extracts_braking_g_in_braking_zone -v`
Expected: PASS

- [ ] **Step 5: Write test for corner with no brake_point_m (fallback zone)**

```python
    def test_fallback_zone_when_no_brake_point(self) -> None:
        """Uses entry_distance_m - margin when brake_point_m is None."""
        rng = np.random.default_rng(42)
        n = 1000
        distance_m = np.linspace(0, 2000, n)
        longitudinal_g = rng.normal(-0.1, 0.05, n)  # background
        # Braking zone 200m before entry at 500m → [300, 500]
        mask = (distance_m >= 300) & (distance_m <= 500)
        longitudinal_g[mask] = rng.normal(-1.0, 0.05, mask.sum())

        corners = [
            Corner(
                number=1,
                entry_distance_m=500.0,
                exit_distance_m=650.0,
                apex_distance_m=575.0,
                min_speed_mps=20.0,
                brake_point_m=None,
                peak_brake_g=None,
                throttle_commit_m=None,
            ),
        ]

        result = calibrate_per_corner_braking_g(longitudinal_g, distance_m, corners)
        assert 1 in result
        assert result[1] == pytest.approx(1.0, abs=0.15)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/test_grip_calibration.py::TestCalibratePerCornerBrakingG::test_fallback_zone_when_no_brake_point -v`
Expected: PASS

- [ ] **Step 7: Write test for insufficient data (corner skipped)**

```python
    def test_insufficient_data_skipped(self) -> None:
        """Corners with too few braking points are excluded."""
        distance_m = np.linspace(0, 500, 50)
        longitudinal_g = np.full(50, -0.1)  # barely braking, below -0.2 threshold

        corners = [
            Corner(
                number=1,
                entry_distance_m=200.0,
                exit_distance_m=350.0,
                apex_distance_m=275.0,
                min_speed_mps=20.0,
                brake_point_m=100.0,
                peak_brake_g=None,
                throttle_commit_m=None,
            ),
        ]

        result = calibrate_per_corner_braking_g(longitudinal_g, distance_m, corners)
        assert result == {}
```

- [ ] **Step 8: Run all per-corner braking tests**

Run: `pytest tests/test_grip_calibration.py::TestCalibratePerCornerBrakingG -v`
Expected: all PASS

- [ ] **Step 9: Run quality gates**

```bash
cd /mnt/d/OneDrive/Dokumenty/vscode/cataclysm && source .venv/bin/activate
ruff format cataclysm/grip_calibration.py tests/test_grip_calibration.py
ruff check cataclysm/grip_calibration.py tests/test_grip_calibration.py
dmypy run -- cataclysm/
pytest tests/test_grip_calibration.py -v -n auto
```

- [ ] **Step 10: Commit**

```bash
git add cataclysm/grip_calibration.py tests/test_grip_calibration.py
git commit -m "feat: add calibrate_per_corner_braking_g() for per-corner brake G extraction"
```

---

## Chunk 2: Per-Point Decel in the Velocity Solver

### Task 2: Refactor `_available_accel()` to accept optional per-point decel

**Files:**
- Modify: `cataclysm/velocity_profile.py:227-251` (`_available_accel`)
- Modify: `cataclysm/velocity_profile.py:300-338` (`_backward_pass`)
- Test: `tests/test_velocity_profile.py`

- [ ] **Step 1: Write the failing test for `_backward_pass` with `decel_array`**

```python
class TestBackwardPassDecelArray:
    """Tests for _backward_pass with per-point decel_array."""

    def test_decel_array_overrides_scalar(self) -> None:
        """When decel_array is provided, backward pass uses per-point values."""
        n = 100
        step_m = 1.0
        abs_k = np.zeros(n)
        max_speed = np.full(n, 40.0)
        # Low corner speed at point 70 forces braking
        max_speed[70] = 15.0

        params_low_decel = VehicleParams(
            mu=1.0, max_accel_g=0.5, max_decel_g=0.5, max_lateral_g=1.0
        )
        # decel_array with 1.5G everywhere — should brake much later than 0.5G scalar
        decel_array = np.full(n, 1.5)

        v_scalar = _backward_pass(max_speed, step_m, params_low_decel, abs_k)
        v_array = _backward_pass(
            max_speed, step_m, params_low_decel, abs_k, decel_array=decel_array
        )

        # With higher decel, the car can brake later → speed stays high longer
        # before the slow point. Check that speed at point 50 is higher with array.
        assert v_array[50] > v_scalar[50]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_velocity_profile.py::TestBackwardPassDecelArray::test_decel_array_overrides_scalar -v`
Expected: FAIL with `TypeError: _backward_pass() got an unexpected keyword argument 'decel_array'`

- [ ] **Step 3: Add `decel_g_override` parameter to `_available_accel()`**

Modify `_available_accel` (line 227) to accept an optional override:

```python
def _available_accel(
    speed: float,
    lateral_g_used: float,
    params: VehicleParams,
    direction: str,
    *,
    decel_g_override: float | None = None,
) -> float:
    """Compute available longitudinal G from the friction circle.

    Given current speed and lateral G being used, the remaining longitudinal
    budget follows from the generalised friction circle:

        (lat/max_lat)^p + (lon/max_lon)^p <= 1

    Solving for lon:
        lon = max_lon * (1 - (lat/max_lat)^p) ^ (1/p)

    When *decel_g_override* is provided and direction is "decel", it replaces
    ``params.max_decel_g`` as the longitudinal ceiling.
    """
    if direction == "decel" and decel_g_override is not None:
        max_lon_g = decel_g_override
    else:
        max_lon_g = params.max_accel_g if direction == "accel" else params.max_decel_g
    exp = params.friction_circle_exponent

    lateral_fraction = (abs(lateral_g_used) / params.max_lateral_g) ** exp
    # Clamp to [0, 1] — if lateral exceeds max, no longitudinal budget remains
    lateral_fraction = min(lateral_fraction, 1.0)

    available: float = max_lon_g * (1.0 - lateral_fraction) ** (1.0 / exp)
    return max(available, 0.0)
```

- [ ] **Step 4: Add `decel_array` parameter to `_backward_pass()`**

Modify `_backward_pass` (line 300) signature and loop:

```python
def _backward_pass(
    max_speed: np.ndarray,
    step_m: float,
    params: VehicleParams,
    abs_curvature: np.ndarray,
    gradient_sin: np.ndarray | None = None,
    vertical_curvature: np.ndarray | None = None,
    decel_array: np.ndarray | None = None,
) -> np.ndarray:
    """Backward integration: decelerate from each point respecting traction limits.

    If *decel_array* is provided, each point uses the per-distance braking G
    instead of the scalar ``params.max_decel_g``.  This mirrors how mu_array
    overrides the scalar mu for cornering.
    """
    n = len(max_speed)
    v = np.empty(n, dtype=np.float64)
    v[-1] = max_speed[-1]

    for i in range(n - 2, -1, -1):
        v_next = v[i + 1]
        avg_k = 0.5 * (abs_curvature[i + 1] + abs_curvature[i])
        lateral_g = v_next**2 * avg_k / G
        decel_override = float(decel_array[i]) if decel_array is not None else None
        decel_g = _available_accel(
            v_next, lateral_g, params, "decel", decel_g_override=decel_override
        )
        # Vertical curvature scales traction via normal force
        if vertical_curvature is not None:
            kv = float(vertical_curvature[i])
            normal_scale = max(1.0 + v_next**2 * kv / G, 0.1)
            decel_g *= normal_scale
        drag_g = params.drag_coefficient * v_next**2 / G
        gradient_g = float(gradient_sin[i]) if gradient_sin is not None else 0.0
        effective_decel_g = decel_g + drag_g + gradient_g
        v_prev_sq = v_next**2 + 2.0 * effective_decel_g * G * step_m
        v_prev = np.sqrt(max(v_prev_sq, 0.0))
        v[i] = min(v_prev, max_speed[i])

    return v
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_velocity_profile.py::TestBackwardPassDecelArray::test_decel_array_overrides_scalar -v`
Expected: PASS

- [ ] **Step 6: Write test that decel_array=None preserves original behavior**

```python
    def test_none_decel_array_matches_scalar(self) -> None:
        """With decel_array=None, backward pass is identical to before."""
        n = 100
        step_m = 1.0
        abs_k = np.full(n, 0.001)
        max_speed = np.full(n, 40.0)
        max_speed[70] = 15.0

        params = VehicleParams(
            mu=1.0, max_accel_g=0.5, max_decel_g=1.0, max_lateral_g=1.0
        )

        v_without = _backward_pass(max_speed, step_m, params, abs_k)
        v_with_none = _backward_pass(
            max_speed, step_m, params, abs_k, decel_array=None
        )

        np.testing.assert_array_equal(v_without, v_with_none)
```

- [ ] **Step 7: Run test**

Run: `pytest tests/test_velocity_profile.py::TestBackwardPassDecelArray::test_none_decel_array_matches_scalar -v`
Expected: PASS

- [ ] **Step 8: Write test for per-corner variation (high-decel zone brakes later)**

```python
    def test_high_decel_zone_brakes_later(self) -> None:
        """A corner with higher decel_array values should have a later brake point."""
        n = 200
        step_m = 1.0
        abs_k = np.zeros(n)
        max_speed = np.full(n, 50.0)
        max_speed[150] = 10.0  # hard corner

        params = VehicleParams(
            mu=1.0, max_accel_g=0.5, max_decel_g=0.8, max_lateral_g=1.0
        )

        # Uniform decel at scalar value
        v_uniform = _backward_pass(max_speed, step_m, params, abs_k)

        # Higher decel in the zone before the corner [100-150]
        decel_arr = np.full(n, 0.8)
        decel_arr[100:150] = 1.5

        v_boosted = _backward_pass(
            max_speed, step_m, params, abs_k, decel_array=decel_arr
        )

        # With higher braking in [100-150], speed at point 130 should be higher
        # (car can maintain speed longer before braking)
        assert v_boosted[130] > v_uniform[130]
        # But outside the boosted zone (point 50), speeds should be similar
        # (within floating point tolerance, since the backward pass propagates)
        assert v_boosted[50] == pytest.approx(v_uniform[50], abs=0.5)
```

- [ ] **Step 9: Run all decel_array tests**

Run: `pytest tests/test_velocity_profile.py::TestBackwardPassDecelArray -v`
Expected: all PASS

- [ ] **Step 10: Run full velocity profile test suite to verify no regressions**

Run: `pytest tests/test_velocity_profile.py -v -n auto`
Expected: all PASS

- [ ] **Step 11: Run quality gates**

```bash
ruff format cataclysm/velocity_profile.py tests/test_velocity_profile.py
ruff check cataclysm/velocity_profile.py tests/test_velocity_profile.py
dmypy run -- cataclysm/
```

- [ ] **Step 12: Commit**

```bash
git add cataclysm/velocity_profile.py tests/test_velocity_profile.py
git commit -m "feat: _backward_pass accepts per-point decel_array for corner-specific braking"
```

---

### Task 3: Thread `decel_array` through `compute_optimal_profile()`

**Files:**
- Modify: `cataclysm/velocity_profile.py:405-512` (`compute_optimal_profile`)
- Test: `tests/test_velocity_profile.py`

- [ ] **Step 1: Write the failing test**

```python
class TestOptimalProfileDecelArray:
    """Tests for compute_optimal_profile with decel_array."""

    def test_decel_array_produces_different_brake_points(self) -> None:
        """A higher decel_array should push brake points later."""
        from cataclysm.curvature import CurvatureResult

        n = 500
        distance = np.linspace(0, 1000, n)
        curvature = np.zeros(n)
        # Add a corner at 600m
        curvature[280:320] = 0.01  # ~10m radius corner

        cr = CurvatureResult(
            distance_m=distance,
            curvature=curvature,
            abs_curvature=np.abs(curvature),
        )
        params = VehicleParams(
            mu=1.0, max_accel_g=0.5, max_decel_g=0.8, max_lateral_g=1.0
        )

        result_scalar = compute_optimal_profile(cr, params, closed_circuit=False)

        # Higher decel everywhere
        decel_arr = np.full(n, 1.5)
        result_array = compute_optimal_profile(
            cr, params, closed_circuit=False, decel_array=decel_arr
        )

        # With higher braking, lap time should be lower (can brake later, carry speed)
        assert result_array.lap_time_s < result_scalar.lap_time_s
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_velocity_profile.py::TestOptimalProfileDecelArray::test_decel_array_produces_different_brake_points -v`
Expected: FAIL with `TypeError: compute_optimal_profile() got an unexpected keyword argument 'decel_array'`

- [ ] **Step 3: Add `decel_array` kwarg to `compute_optimal_profile()`**

Modify the signature (line 405) and pass it through to `_backward_pass`:

```python
def compute_optimal_profile(
    curvature_result: CurvatureResult,
    params: VehicleParams | None = None,
    *,
    closed_circuit: bool = True,
    gradient_sin: np.ndarray | None = None,
    mu_array: np.ndarray | None = None,
    vertical_curvature: np.ndarray | None = None,
    decel_array: np.ndarray | None = None,
) -> OptimalProfile:
```

In the closed_circuit branch (line 466), tile the decel_array:
```python
        decel_3x = np.tile(decel_array, 3) if decel_array is not None else None
```

Pass to backward_pass calls:
```python
        backward_3x = _backward_pass(
            max_speed_3x, step_m, params, abs_k_3x, gradient_3x, kv_3x,
            decel_array=decel_3x,
        )
```

And in the open-circuit else branch:
```python
        backward = _backward_pass(
            max_corner_speed, step_m, params, abs_k, gradient_sin,
            vertical_curvature, decel_array=decel_array,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_velocity_profile.py::TestOptimalProfileDecelArray -v`
Expected: PASS

- [ ] **Step 5: Run full test suite**

Run: `pytest tests/test_velocity_profile.py -v -n auto`
Expected: all PASS

- [ ] **Step 6: Run quality gates**

```bash
ruff format cataclysm/velocity_profile.py tests/test_velocity_profile.py
ruff check cataclysm/velocity_profile.py tests/test_velocity_profile.py
dmypy run -- cataclysm/
```

- [ ] **Step 7: Commit**

```bash
git add cataclysm/velocity_profile.py tests/test_velocity_profile.py
git commit -m "feat: compute_optimal_profile accepts decel_array for per-corner braking"
```

---

## Chunk 3: Pipeline Wiring — Best Lap Inclusion + Decel Array

### Task 4: (C) Include best lap's braking data in calibration

The current `_collect_independent_calibration_telemetry()` excludes the best lap (`lap_num != target_lap`). For braking this exclusion is unnecessary because braking G doesn't suffer from self-reference: braking happens before the corner, so using the best lap's brake data doesn't circularly inflate the cornering-speed prediction. The fix is to create a separate collection function for braking that includes all laps.

**Files:**
- Modify: `backend/api/services/pipeline.py` (add `_collect_braking_calibration_telemetry`)
- Test: create or modify test file for pipeline calibration

- [ ] **Step 1: Write the failing test**

```python
def test_braking_calibration_includes_best_lap() -> None:
    """Braking calibration should include the best lap unlike cornering calibration."""
    from unittest.mock import MagicMock
    import pandas as pd

    session_data = MagicMock()
    session_data.coaching_laps = [3, 5, 7]
    session_data.processed.best_lap = 5
    session_data.processed.resampled_laps = {
        3: pd.DataFrame({
            "lateral_g": np.random.default_rng(1).normal(0, 0.5, 100),
            "longitudinal_g": np.random.default_rng(1).normal(-0.8, 0.2, 100),
            "lap_distance_m": np.linspace(0, 2000, 100),
        }),
        5: pd.DataFrame({
            "lateral_g": np.random.default_rng(2).normal(0, 0.5, 100),
            "longitudinal_g": np.random.default_rng(2).normal(-1.0, 0.2, 100),
            "lap_distance_m": np.linspace(0, 2000, 100),
        }),
        7: pd.DataFrame({
            "lateral_g": np.random.default_rng(3).normal(0, 0.5, 100),
            "longitudinal_g": np.random.default_rng(3).normal(-0.7, 0.2, 100),
            "lap_distance_m": np.linspace(0, 2000, 100),
        }),
    }

    from backend.api.services.pipeline import _collect_braking_calibration_telemetry

    result = _collect_braking_calibration_telemetry(session_data)
    assert result is not None
    lon_g, dist_m, used_laps = result
    # Best lap (5) should be INCLUDED
    assert 5 in used_laps
    assert len(used_laps) == 3
```

- [ ] **Step 2: Run test to verify it fails**

Expected: FAIL with `ImportError: cannot import name '_collect_braking_calibration_telemetry'`

- [ ] **Step 3: Implement `_collect_braking_calibration_telemetry()`**

Add to `backend/api/services/pipeline.py` after `_collect_independent_calibration_telemetry`:

```python
def _collect_braking_calibration_telemetry(
    session_data: SessionData,
) -> tuple[np.ndarray, np.ndarray, list[int]] | None:
    """Return braking telemetry from ALL coaching laps including the best lap.

    Unlike cornering calibration, braking G does not suffer from self-reference:
    braking happens before the corner entry, so using the best lap's braking data
    doesn't circularly inflate the cornering-speed prediction that we're evaluating
    the driver against.

    Returns (longitudinal_g, distance_m, used_laps) or None if no data.
    """
    lon_segments: list[np.ndarray] = []
    dist_segments: list[np.ndarray] = []
    used_laps: list[int] = []

    for lap_num in session_data.coaching_laps:
        lap_df = session_data.processed.resampled_laps.get(lap_num)
        if lap_df is None:
            continue
        if "longitudinal_g" not in lap_df.columns or "lap_distance_m" not in lap_df.columns:
            continue

        lon_g = lap_df["longitudinal_g"].to_numpy()
        dist_m = lap_df["lap_distance_m"].to_numpy()

        finite_mask = np.isfinite(lon_g) & np.isfinite(dist_m)
        lon_g = lon_g[finite_mask]
        dist_m = dist_m[finite_mask]
        if len(lon_g) == 0:
            continue

        lon_segments.append(lon_g)
        dist_segments.append(dist_m)
        used_laps.append(lap_num)

    if not lon_segments:
        return None

    return np.concatenate(lon_segments), np.concatenate(dist_segments), used_laps
```

- [ ] **Step 4: Run test to verify it passes**

Expected: PASS

- [ ] **Step 5: Quality gates + commit**

```bash
ruff format backend/api/services/pipeline.py
ruff check backend/api/services/pipeline.py
dmypy run -- backend/
git add backend/api/services/pipeline.py tests/test_pipeline_braking.py
git commit -m "feat(C): collect braking telemetry from all laps including best lap"
```

---

### Task 5: (B) Build `_build_decel_array()` and wire into the solver call

Mirror `_build_mu_array()` pattern: inside each corner's braking zone, use `max(global_decel, per_corner_decel)`. Outside, use the global scalar.

**Files:**
- Modify: `backend/api/services/pipeline.py` (add `_build_decel_array`, modify `_compute()`)
- Test: pipeline test file

- [ ] **Step 1: Write the failing test for `_build_decel_array`**

```python
def test_build_decel_array_uses_max_of_global_and_per_corner() -> None:
    """Per-corner decel only raises above global, never lowers."""
    from backend.api.services.pipeline import _build_decel_array
    from cataclysm.corners import Corner

    distance_m = np.linspace(0, 2000, 1000)
    corners = [
        Corner(
            number=1, entry_distance_m=200.0, exit_distance_m=350.0,
            apex_distance_m=275.0, min_speed_mps=20.0,
            brake_point_m=100.0, peak_brake_g=1.3, throttle_commit_m=320.0,
        ),
        Corner(
            number=2, entry_distance_m=800.0, exit_distance_m=950.0,
            apex_distance_m=875.0, min_speed_mps=25.0,
            brake_point_m=700.0, peak_brake_g=0.8, throttle_commit_m=920.0,
        ),
    ]
    per_corner_decel = {1: 1.3, 2: 0.7}  # corner 2 lower than global
    global_decel = 1.0

    result = _build_decel_array(distance_m, corners, per_corner_decel, global_decel)

    # Outside corners: global
    assert result[0] == pytest.approx(1.0)
    # Corner 1 brake zone [100-200]: max(1.0, 1.3) = 1.3
    idx_150 = np.searchsorted(distance_m, 150.0)
    assert result[idx_150] == pytest.approx(1.3)
    # Corner 2 brake zone [700-800]: max(1.0, 0.7) = 1.0 (global wins)
    idx_750 = np.searchsorted(distance_m, 750.0)
    assert result[idx_750] == pytest.approx(1.0)
```

- [ ] **Step 2: Run test to verify it fails**

Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement `_build_decel_array()`**

Add to `backend/api/services/pipeline.py` after `_build_mu_array`:

```python
def _build_decel_array(
    distance_m: np.ndarray,
    corners: list[Corner],
    per_corner_decel: dict[int, float],
    global_decel: float,
) -> np.ndarray:
    """Build a per-point decel array from per-corner braking G estimates.

    Mirrors ``_build_mu_array`` pattern.  For points inside a corner's braking
    zone (brake_point_m to entry_distance_m), uses ``max(global, per_corner)``
    so that corners where the driver demonstrated above-average braking are
    predicted correctly without penalising corners where they were conservative.

    For points outside any braking zone, the global decel is used.
    """
    decel_arr = np.full(len(distance_m), global_decel, dtype=np.float64)
    for corner in corners:
        if corner.number not in per_corner_decel:
            continue
        corner_decel = max(global_decel, per_corner_decel[corner.number])
        # Braking zone: from brake_point to entry
        zone_start = corner.brake_point_m if corner.brake_point_m is not None else (
            corner.entry_distance_m - 200.0
        )
        zone_end = corner.entry_distance_m
        mask = (distance_m >= zone_start) & (distance_m <= zone_end)
        decel_arr[mask] = corner_decel
    return decel_arr
```

- [ ] **Step 4: Run test to verify it passes**

Expected: PASS

- [ ] **Step 5: Wire `decel_array` into `_compute()` inside `get_optimal_profile_data`**

Modify the `_compute()` inner function in `get_optimal_profile_data` (around line 1489) to build and pass `decel_array`. Add this block after the `mu_array` construction (after line 1526):

```python
        # Build per-corner decel array using ALL coaching laps (including best lap).
        # Unlike cornering grip, braking G doesn't have the self-reference problem
        # because braking happens before the corner entry.
        decel_array: np.ndarray | None = None
        if session_data.corners and calibrated_vp is not None:
            braking_data = _collect_braking_calibration_telemetry(session_data)
            if braking_data is not None:
                lon_g_all, dist_m_all, braking_laps = braking_data
                per_corner_decel = calibrate_per_corner_braking_g(
                    lon_g_all, dist_m_all, session_data.corners,
                )
                if per_corner_decel:
                    decel_array = _build_decel_array(
                        curvature_result.distance_m,
                        session_data.corners,
                        per_corner_decel,
                        calibrated_vp.max_decel_g,
                    )
                    logger.debug(
                        "Per-corner decel array built for sid=%s: %d corners, "
                        "global_decel=%.3f",
                        session_id,
                        len(per_corner_decel),
                        calibrated_vp.max_decel_g,
                    )
```

Then update the `compute_optimal_profile` call (line 1552) to pass `decel_array`:

```python
        optimal = compute_optimal_profile(
            curvature_result,
            params=calibrated_vp,
            gradient_sin=gradient_sin,
            mu_array=mu_array,
            vertical_curvature=vert_curvature,
            decel_array=decel_array,
        )
```

- [ ] **Step 6: Add import of `calibrate_per_corner_braking_g` to pipeline.py**

At the top of `pipeline.py`, update the grip_calibration import:

```python
from cataclysm.grip_calibration import (
    apply_calibration_to_params,
    calibrate_grip_from_telemetry,
    calibrate_per_corner_braking_g,
    calibrate_per_corner_grip,
)
```

- [ ] **Step 7: Run quality gates**

```bash
ruff format backend/api/services/pipeline.py
ruff check backend/api/services/pipeline.py
dmypy run -- backend/ cataclysm/
pytest tests/ backend/tests/ -v -n auto
```

- [ ] **Step 8: Commit**

```bash
git add backend/api/services/pipeline.py cataclysm/grip_calibration.py
git commit -m "feat(B): build per-corner decel_array and pass to velocity solver"
```

---

## Chunk 4: Cache Invalidation + Smoke Test

### Task 6: Verify cache invalidation handles decel changes

The physics cache key is `(track_slug, "profile", profile_id, calibrated_mu_2dp)`. The decel_array is derived from telemetry data (per-corner p95 of braking G), which changes when:
1. Equipment changes (different tire compound → different mu_cap)
2. Session data changes (reprocessing)

Both already invalidate the cache via the existing `profile_id` and `calibrated_mu_str` key components. The decel_array is recomputed fresh inside `_compute()` on every cache miss. **No cache key changes needed** — the decel_array is a function of the session telemetry + calibrated params, both of which are already captured.

**Files:**
- Modify: `tests/test_velocity_profile.py` (add regression test)
- No changes to pipeline cache logic

- [ ] **Step 1: Write a regression test confirming decel_array backward compat**

```python
    def test_decel_array_backward_compatible_with_existing_tests(self) -> None:
        """All existing _backward_pass call sites work unchanged (no decel_array)."""
        n = 50
        step_m = 1.0
        abs_k = np.full(n, 0.002)
        max_speed = np.full(n, 30.0)
        max_speed[25] = 10.0
        params = VehicleParams(
            mu=1.0, max_accel_g=0.5, max_decel_g=1.0, max_lateral_g=1.0
        )

        # This call should work without decel_array (backward compat)
        v = _backward_pass(max_speed, step_m, params, abs_k)
        assert len(v) == n
        assert v[25] == pytest.approx(10.0)
        # Speed before the slow point should be >= 10 (braking from higher)
        assert v[20] >= 10.0
```

- [ ] **Step 2: Run test**

Expected: PASS

- [ ] **Step 3: Run full test suite across all modules**

```bash
pytest tests/ backend/tests/ -v -n auto
```

Expected: all PASS

- [ ] **Step 4: Quality gates**

```bash
ruff format cataclysm/ tests/ backend/
ruff check cataclysm/ tests/ backend/
dmypy run -- cataclysm/ backend/
cd /mnt/d/OneDrive/Dokumenty/vscode/cataclysm/frontend && npx tsc --noEmit
```

- [ ] **Step 5: Final commit**

```bash
git add tests/test_velocity_profile.py
git commit -m "test: add backward-compat regression tests for decel_array"
```

---

## Summary of Changes

| Component | Change | Risk |
|-----------|--------|------|
| `grip_calibration.py` | New `calibrate_per_corner_braking_g()` | Low — new function, no existing behavior changed |
| `velocity_profile.py` | `_available_accel()` gains `decel_g_override` kwarg | Low — default=None preserves existing behavior |
| `velocity_profile.py` | `_backward_pass()` gains `decel_array` kwarg | Low — default=None preserves existing behavior |
| `velocity_profile.py` | `compute_optimal_profile()` gains `decel_array` kwarg | Low — default=None preserves existing behavior |
| `pipeline.py` | New `_collect_braking_calibration_telemetry()` | Low — new function |
| `pipeline.py` | New `_build_decel_array()` | Low — new function |
| `pipeline.py` | `_compute()` builds + passes decel_array | Medium — changes solver output for sessions with multiple laps |
| Cache | No key changes needed | None — decel is recomputed on every cache miss |

**Expected behavioral change:** Brake points move later (closer to corner) at corners where the driver's telemetry shows higher-than-average braking G. The T5 example at Barber should shift from ~3-board to closer to the 2-board, matching the coaching text.
