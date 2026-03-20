# Track Banking Implementation Plan

**Date**: 2026-03-20
**Branch**: `temp/physics-val-improvements` (continue)
**Prerequisite**: Banking angle data for at least Barber, AMP, Roebling

---

## Architecture: mu_array approach (zero solver changes)

Banking increases effective grip: for small angles, `mu_eff = mu + tan(φ)`.

The solver already accepts a per-point `mu_array`. Banking is injected by
boosting mu at banked sections. No changes to `velocity_profile.py` needed.

---

## Implementation Steps

### Step 1: Add `banking_deg` to TrackReference + NPZ

**File**: `cataclysm/track_reference.py`

- Add `banking_deg: np.ndarray | None` field to `TrackReference` dataclass
- In `get_track_reference()`: load `data.get("banking_deg", None)`
- In `_save_reference()`: save if not None (same pattern as `elevation_m`)
- Backward compatible: existing NPZ files without banking_deg load as None

### Step 2: Add banking data to track_db

**File**: `cataclysm/track_db.py`

Option A: Per-corner banking in `TrackLayout.corners` entries
Option B: A separate `TRACK_BANKING` dict mapping track_slug → list of (start_m, end_m, banking_deg)

Prefer **Option B** — banking is a track property, not a corner property. Corners don't cover
the entire track (straights have banking too, e.g., pit straight camber).

```python
# track_slug → list of (start_fraction, end_fraction, banking_deg)
# Fractions are 0-1 of track length. Banking between entries is linearly interpolated.
TRACK_BANKING: dict[str, list[tuple[float, float, float]]] = {
    "barber_motorsports_park": [
        (0.05, 0.15, 4.0),   # T1-T2 sweeper — notably banked
        (0.28, 0.32, 2.0),   # T5 hairpin — slight banking
        ...
    ],
}
```

### Step 3: Build banking array in track_reference build

**File**: `cataclysm/track_reference.py`

When building a track reference, if `TRACK_BANKING` has data for the track,
interpolate banking angles onto the distance array and store in NPZ.

### Step 4: Apply banking in pipeline

**File**: `backend/api/services/pipeline.py`

In `_compute()` (around line 1553-1607), after building `mu_array`:

```python
# Apply track banking to mu_array
if ref.banking_deg is not None:
    banking_rad = np.radians(ref.banking_deg)
    banking_mu_boost = np.tan(banking_rad)
    if mu_array is None:
        mu_array = np.full(len(curvature_result.distance_m), calibrated_vp.mu)
    mu_array = mu_array + banking_mu_boost
```

### Step 5: Apply banking in validation scripts

**Files**: `scripts/physics_realworld_comparison.py`, `scripts/physics_benchmark_validation.py`

Same pattern — load banking from track reference, compute mu boost, pass as mu_array.

### Step 6: Validate

Run `physics_realworld_comparison.py --strict --compare data/physics_baseline.json`.

Expected: Barber mean should drop from 1.018 toward 1.00. Exceedances should decrease.

---

## Data Requirements

For each track, need banking angles at key sections. Sources (priority order):
1. iRacing/rFactor laser scan data (community-published)
2. Telemetry estimation: lateral_G_measured vs mu × curvature × speed
3. Onboard video analysis
4. Default: 0° (flat) — no worse than current

Conservative approach: start with 2-3° uniform banking in corners as a rough
approximation, validate, then refine per-corner.

---

## Risk Assessment

- **Low risk** for solver: no changes to velocity_profile.py
- **Medium risk** for data: bad banking estimates could make things worse
- **Mitigation**: validate incrementally, can easily revert by setting banking_deg=None
