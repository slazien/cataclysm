# AMP Track Data Parity Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Bring Atlanta Motorsports Park data in `track_db.py` to full parity with Barber Motorsports Park — fixing broken metadata, adding all 16 fully-annotated corners, rebuilding satellite-verified landmarks, and adding a registry alias.

**Architecture:** Single-file data rewrite of the AMP section in `cataclysm/track_db.py` (lines 305-365), plus test updates in `tests/test_track_db.py`. No logic changes — only curated track data and corresponding test assertions.

**Tech Stack:** Python dataclasses (OfficialCorner, Landmark, TrackLayout), pytest

---

### Task 1: Update AMP Tests First (Red Phase)

**Files:**
- Modify: `tests/test_track_db.py` — class `TestAtlantaMotorsportsPark` (lines 221-274)

**Step 1: Rewrite TestAtlantaMotorsportsPark to assert parity**

Replace the entire `TestAtlantaMotorsportsPark` class (lines 221-274) with tests that assert the target state:

```python
class TestAtlantaMotorsportsPark:
    def test_lookup_by_name(self) -> None:
        layout = lookup_track("Atlanta Motorsports Park")
        assert layout is not None
        assert layout.name == "Atlanta Motorsports Park"

    def test_lookup_case_insensitive(self) -> None:
        layout = lookup_track("atlanta motorsports park")
        assert layout is not None

    def test_lookup_csv_alias(self) -> None:
        """RaceChrono CSV metadata reports 'AMP Full' as the track name."""
        layout = lookup_track("AMP Full")
        assert layout is not None
        assert layout.name == "Atlanta Motorsports Park"

    def test_has_sixteen_corners(self) -> None:
        assert len(ATLANTA_MOTORSPORTS_PARK.corners) == 16

    def test_corner_numbering(self) -> None:
        numbers = [c.number for c in ATLANTA_MOTORSPORTS_PARK.corners]
        assert numbers == list(range(1, 17))

    def test_fractions_monotonic(self) -> None:
        fractions = [c.fraction for c in ATLANTA_MOTORSPORTS_PARK.corners]
        for i in range(1, len(fractions)):
            assert fractions[i] > fractions[i - 1]

    def test_fractions_in_range(self) -> None:
        for c in ATLANTA_MOTORSPORTS_PARK.corners:
            assert 0.0 < c.fraction < 1.0

    def test_gps_metadata_corrected(self) -> None:
        """Center coords verified from real GPS telemetry centroid."""
        assert ATLANTA_MOTORSPORTS_PARK.center_lat == pytest.approx(34.435, abs=0.01)
        assert ATLANTA_MOTORSPORTS_PARK.center_lon == pytest.approx(-84.178, abs=0.01)

    def test_track_length_corrected(self) -> None:
        """Median lap distance from 10 telemetry laps."""
        assert ATLANTA_MOTORSPORTS_PARK.length_m == pytest.approx(2935.0, abs=10.0)

    def test_elevation_range(self) -> None:
        assert ATLANTA_MOTORSPORTS_PARK.elevation_range_m == pytest.approx(30.0, abs=2.0)

    def test_landmarks_present(self) -> None:
        assert len(ATLANTA_MOTORSPORTS_PARK.landmarks) >= 17

    def test_landmarks_sorted(self) -> None:
        distances = [lm.distance_m for lm in ATLANTA_MOTORSPORTS_PARK.landmarks]
        for i in range(1, len(distances)):
            assert distances[i] >= distances[i - 1]

    def test_landmarks_in_range(self) -> None:
        length = ATLANTA_MOTORSPORTS_PARK.length_m
        assert length is not None
        for lm in ATLANTA_MOTORSPORTS_PARK.landmarks:
            assert 0.0 <= lm.distance_m < length

    def test_in_all_tracks(self) -> None:
        tracks = get_all_tracks()
        assert any(t.name == "Atlanta Motorsports Park" for t in tracks)

    def test_country(self) -> None:
        assert ATLANTA_MOTORSPORTS_PARK.country == "US"

    def test_all_corners_have_direction(self) -> None:
        for c in ATLANTA_MOTORSPORTS_PARK.corners:
            assert c.direction in ("left", "right"), f"T{c.number} missing direction"

    def test_all_corners_have_corner_type(self) -> None:
        for c in ATLANTA_MOTORSPORTS_PARK.corners:
            assert c.corner_type is not None, f"T{c.number} missing corner_type"

    def test_all_corners_have_elevation_trend(self) -> None:
        for c in ATLANTA_MOTORSPORTS_PARK.corners:
            assert c.elevation_trend is not None, f"T{c.number} missing elevation_trend"

    def test_all_corners_have_coaching_notes(self) -> None:
        for c in ATLANTA_MOTORSPORTS_PARK.corners:
            assert c.coaching_notes is not None, f"T{c.number} missing coaching_notes"
            assert len(c.coaching_notes) > 10, f"T{c.number} coaching_notes too short"


class TestAMPEnrichedData:
    """Tests that specific AMP corners have expected curated values."""

    def _get_corner(self, number: int) -> OfficialCorner:
        matches = [c for c in ATLANTA_MOTORSPORTS_PARK.corners if c.number == number]
        assert len(matches) == 1
        return matches[0]

    def test_t1_downhill_hairpin(self) -> None:
        c = self._get_corner(1)
        assert c.direction == "right"
        assert c.corner_type == "hairpin"
        assert c.elevation_trend == "downhill"
        assert c.camber == "off-camber"

    def test_t4_carousel(self) -> None:
        c = self._get_corner(4)
        assert c.direction == "right"
        assert "carousel" in c.name.lower() or "carousel" in (c.coaching_notes or "").lower()

    def test_t5_blind_braking(self) -> None:
        c = self._get_corner(5)
        assert c.direction == "left"
        assert c.blind is True

    def test_t11_compression(self) -> None:
        c = self._get_corner(11)
        assert c.elevation_trend == "compression"

    def test_t14_eau_rouge(self) -> None:
        c = self._get_corner(14)
        assert "eau rouge" in c.name.lower() or "eau rouge" in (c.coaching_notes or "").lower()

    def test_t16_blind_final(self) -> None:
        c = self._get_corner(16)
        assert c.blind is True
        assert c.direction == "right"

    def test_has_character_annotations(self) -> None:
        """At least some fast corners should have character annotations."""
        char_count = sum(
            1 for c in ATLANTA_MOTORSPORTS_PARK.corners if c.character is not None
        )
        assert char_count >= 4, "Need character annotations on fast kinks/esses"

    def test_landmarks_have_brake_boards(self) -> None:
        brake_boards = [
            lm
            for lm in ATLANTA_MOTORSPORTS_PARK.landmarks
            if lm.landmark_type == LandmarkType.brake_board
        ]
        assert len(brake_boards) >= 3
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_track_db.py::TestAtlantaMotorsportsPark -v`
Expected: Multiple FAILs (16 corners != 12, wrong coords, missing fields, etc.)

Run: `pytest tests/test_track_db.py::TestAMPEnrichedData -v`
Expected: Multiple FAILs (no direction, no coaching_notes, etc.)

**Step 3: Commit the failing tests**

```bash
git add tests/test_track_db.py
git commit -m "test: add AMP parity tests (red phase)

Tests assert full metadata parity with Barber: 16 corners with
direction/type/elevation/camber/coaching_notes, corrected GPS center,
track length, elevation range, and registry alias."
```

---

### Task 2: Rewrite AMP Landmarks with Satellite-Verified Data

**Files:**
- Modify: `cataclysm/track_db.py` lines 305-336 (landmarks section)

**Step 1: Build a GPS projection script to verify landmark distances**

Use the telemetry data to project landmark positions. Run this to derive distances:

```python
# Script to project GPS landmarks onto telemetry track line
# Run from project root with venv active
import numpy as np
from cataclysm.parser import parse_racechrono_csv
from cataclysm.engine import process_session

csv = 'data/session/atlanta_motorsports_park/session_20251214_155803_amp_full_v3.csv'
parsed = parse_racechrono_csv(csv)
processed = process_session(parsed.data)
best = processed.resampled_laps[processed.best_lap]

lat = best['lat'].values
lon = best['lon'].values
dist = best['lap_distance_m'].values

def project_gps(target_lat, target_lon):
    """Find closest point on track line to a GPS coordinate."""
    dlat = lat - target_lat
    dlon = lon - target_lon
    d2 = dlat**2 + dlon**2
    idx = np.argmin(d2)
    return dist[idx]

# Project each landmark GPS coordinate identified from satellite imagery
# (Replace with actual coordinates from Google Maps satellite view)
landmarks = {
    "S/F gantry": (34.4332, -84.1763),     # timing structure on front straight
    "pit entry": (34.4329, -84.1759),       # right side of track before T1
    "T1 brake zone": (34.4324, -84.1756),   # before the hairpin
    # ... etc for each landmark
}

for name, (lt, ln) in landmarks.items():
    d = project_gps(lt, ln)
    print(f"{name}: {d:.0f}m")
```

Use this script interactively to derive precise distances for each landmark. The satellite imagery provides GPS coordinates; the script projects them onto the actual track line.

**Step 2: Replace the AMP landmarks section**

Replace lines 305-336 in `track_db.py` with satellite-verified landmarks. The new section should:
- Start with a verification comment block matching Barber's format
- Include 17-20 landmarks organized by track section
- Use distances derived from the GPS projection script
- Cover all LandmarkType categories present in Barber (brake_board, structure, barrier, road, curbing, natural)

Template (fill distances from projection script):

```python
# ---------------------------------------------------------------------------
# Atlanta Motorsports Park visual landmarks
# ---------------------------------------------------------------------------
# Verified against Google Maps satellite imagery (2026-03) using GPS-to-track-
# distance projection from real telemetry data (XXXX GPS points, XXXX.Xm lap).
# Supplemented with public track guides:
#   - Xtreme Xperience AMP driving tips (Cal DeNyse)
#   - Kartclass AMP track review
#   - Official AMP turn number map
#   - RacingCircuits.info / Wikipedia facility documentation
#
# Distances derived by projecting satellite-identified GPS coordinates onto the
# actual telemetry track line.  Most landmarks have <15m projection error.

_AMP_LANDMARKS: list[Landmark] = [
    # --- Start/Finish area ---
    Landmark("S/F gantry", XXX, LandmarkType.structure, description="Timing gantry"),
    Landmark("pit entry", XXX, LandmarkType.road, description="Pit lane on right"),
    # --- T1 Downhill Hairpin ---
    Landmark("T1 brake board", XXX, LandmarkType.brake_board),
    # --- T3-T4 Carousel & Hilltop ---
    Landmark("carousel apex curb", XXX, LandmarkType.curbing),
    Landmark("hilltop crest", XXX, LandmarkType.natural, description="Highest point on track"),
    # --- T5 Downhill Hairpin ---
    Landmark("T5 3 board", XXX, LandmarkType.brake_board),
    Landmark("T5 2 board", XXX, LandmarkType.brake_board),
    Landmark("T5 1 board", XXX, LandmarkType.brake_board),
    Landmark("T5 gravel trap", XXX, LandmarkType.barrier, description="Runoff on outside"),
    # --- T6-T7 Back straight approach ---
    Landmark("pit exit merge", XXX, LandmarkType.road, description="Merge from left"),
    # --- T7-T9 Bridge section ---
    Landmark("pedestrian bridge", XXX, LandmarkType.structure, description="Span near T8"),
    Landmark("T9 apex curb", XXX, LandmarkType.curbing),
    # --- T10-T11 ---
    Landmark("T10 brake board", XXX, LandmarkType.brake_board),
    Landmark("The Dip compression", XXX, LandmarkType.natural, description="Car compresses"),
    # --- T12-T15 Eau Rouge complex ---
    Landmark("Eau Rouge entry curb", XXX, LandmarkType.curbing),
    Landmark("Eau Rouge crest", XXX, LandmarkType.natural, description="Elevation change"),
    # --- T16 Final & return ---
    Landmark("T16 apex curb", XXX, LandmarkType.curbing),
    Landmark("victory lane", XXX, LandmarkType.structure, description="Near front straight"),
]
```

**Step 3: Run landmark-specific tests**

Run: `pytest tests/test_track_db.py::TestAtlantaMotorsportsPark::test_landmarks_present -v`
Run: `pytest tests/test_track_db.py::TestAtlantaMotorsportsPark::test_landmarks_sorted -v`
Run: `pytest tests/test_track_db.py::TestAtlantaMotorsportsPark::test_landmarks_in_range -v`

**Step 4: Commit landmarks**

```bash
git add cataclysm/track_db.py
git commit -m "feat: rebuild AMP landmarks with satellite-verified distances

Distances derived by projecting satellite-identified GPS coordinates
onto actual telemetry track line (best lap: XXXX GPS points, XXXXm).
Replaces approximate positions with <15m-accuracy references."
```

---

### Task 3: Rewrite AMP TrackLayout with 16 Fully-Annotated Corners

**Files:**
- Modify: `cataclysm/track_db.py` lines 338-359 (TrackLayout + corners)

**Step 1: Replace the ATLANTA_MOTORSPORTS_PARK definition**

Replace lines 338-359 with full metadata. Every corner gets: `direction`, `corner_type`, `elevation_trend`, `camber` (where not default positive), `blind` (where True), `character` (for flat-out kinks/esses), and `coaching_notes`.

Corner data sources:
- **Fractions**: from telemetry heading-rate + speed-trace analysis (Task 2 script)
- **Direction**: from heading-rate sign (positive = left, negative = right)
- **Elevation**: from altitude trace (uphill/downhill/crest/compression)
- **Corner type**: from heading-rate magnitude + corner length
- **Coaching notes**: from Xtreme Xperience guide, Kartclass review, general track craft
- **Character**: "flat" for kinks at >60mph, "lift" for minor braking events

Fix metadata:
- `center_lat`: 34.4349 (from GPS centroid)
- `center_lon`: -84.1781 (from GPS centroid)
- `length_m`: 2935.0 (median of 10 telemetry laps)
- `elevation_range_m`: 30.0 (from GPS altitude: 403-433m)

```python
ATLANTA_MOTORSPORTS_PARK = TrackLayout(
    name="Atlanta Motorsports Park",
    landmarks=_AMP_LANDMARKS,
    center_lat=34.4349,
    center_lon=-84.1781,
    country="US",
    length_m=2935.0,
    elevation_range_m=30.0,
    corners=[
        OfficialCorner(
            1,
            "Downhill Hairpin",
            0.059,
            direction="right",
            corner_type="hairpin",
            elevation_trend="downhill",
            camber="off-camber",
            coaching_notes=(
                "Most dangerous turn on track. Heavy braking from top speed into "
                "downhill off-camber right. Don't overdrive — grip drops fast."
            ),
        ),
        OfficialCorner(
            2,
            "Blind Left",
            0.180,
            character="lift",
            direction="left",
            corner_type="kink",
            elevation_trend="uphill",
            camber="positive",
            blind=True,
            coaching_notes="Completely blind minor left. Brief lift at most. Trust the line.",
        ),
        OfficialCorner(
            3,
            "Carousel Entry",
            0.206,
            direction="right",
            corner_type="sweeper",
            elevation_trend="uphill",
            camber="positive",
            coaching_notes="Entry to the carousel complex. Braking while climbing — uphill helps.",
        ),
        OfficialCorner(
            4,
            "The Carousel",
            0.237,
            direction="right",
            corner_type="sweeper",
            elevation_trend="crest",
            camber="positive",
            coaching_notes=(
                "Long constant-radius right. Single steering angle — more throttle "
                "pushes you wide, less throttle tightens the line."
            ),
        ),
        OfficialCorner(
            5,
            "Downhill Hairpin",
            0.353,
            direction="left",
            corner_type="hairpin",
            elevation_trend="downhill",
            camber="off-camber",
            blind=True,
            coaching_notes=(
                "Blind braking zone with countdown boards (3, 2, 1). "
                "Downhill increases stopping distance. Commit to brake markers."
            ),
        ),
        OfficialCorner(
            6,
            "Uphill Right Kink",
            0.373,
            character="lift",
            direction="right",
            corner_type="kink",
            elevation_trend="uphill",
            camber="positive",
            coaching_notes="Quick direction change exiting T5. Brief lift, not heavy braking.",
        ),
        OfficialCorner(
            7,
            "Back Straight Entry",
            0.498,
            direction="right",
            corner_type="sweeper",
            elevation_trend="flat",
            camber="positive",
            coaching_notes=(
                "Second hardest corner behind T3. Slowest point on track — "
                "leads onto the long back straight. Sacrifice entry for exit speed."
            ),
        ),
        OfficialCorner(
            8,
            "Right Kink",
            0.508,
            character="flat",
            direction="right",
            corner_type="kink",
            elevation_trend="flat",
            camber="positive",
            coaching_notes="Flat out. Continuation of T7 arc onto back straight.",
        ),
        OfficialCorner(
            9,
            "Downhill Left Sweeper",
            0.559,
            direction="left",
            corner_type="sweeper",
            elevation_trend="downhill",
            camber="positive",
            coaching_notes="Long sweeping left, downhill. Smooth steering — don't upset the car.",
        ),
        OfficialCorner(
            10,
            "Hard Left Uphill",
            0.610,
            direction="left",
            corner_type="hairpin",
            elevation_trend="uphill",
            camber="positive",
            coaching_notes=(
                "Common section for early turn-in. Delay entry — uphill adds grip. "
                "Positive camber rewards patience."
            ),
        ),
        OfficialCorner(
            11,
            "The Dip",
            0.643,
            direction="right",
            corner_type="sweeper",
            elevation_trend="compression",
            coaching_notes=(
                "Car compresses through the dip, giving extra grip. "
                "Trust the grip and begin accelerating through the compression."
            ),
        ),
        OfficialCorner(
            12,
            "Downhill Left Kink",
            0.661,
            character="lift",
            direction="left",
            corner_type="kink",
            elevation_trend="downhill",
            coaching_notes="Quick left, downhill. Brief lift — transition into Eau Rouge complex.",
        ),
        OfficialCorner(
            13,
            "Eau Rouge Entry",
            0.712,
            character="flat",
            direction="left",
            corner_type="esses",
            elevation_trend="uphill",
            camber="positive",
            coaching_notes=(
                "Start of the Eau Rouge tribute. Flat out — do NOT lift. "
                "Uphill entry, smooth steering through the esses."
            ),
        ),
        OfficialCorner(
            14,
            "Eau Rouge Mid",
            0.814,
            character="flat",
            direction="right",
            corner_type="esses",
            elevation_trend="flat",
            camber="positive",
            coaching_notes=(
                "Long on-ramp style sweeper — continue accelerating. "
                "Balance throttle through multiple direction changes."
            ),
        ),
        OfficialCorner(
            15,
            "Eau Rouge Exit",
            0.898,
            character="flat",
            direction="left",
            corner_type="esses",
            elevation_trend="flat",
            camber="positive",
            coaching_notes="Exit of Eau Rouge complex. Stay flat, smooth transition to T16.",
        ),
        OfficialCorner(
            16,
            "Final Right",
            0.949,
            direction="right",
            corner_type="sweeper",
            elevation_trend="flat",
            camber="positive",
            blind=True,
            coaching_notes=(
                "Blind quick right before start/finish. Keep your line and hit your marks. "
                "Exit speed onto the main straight is critical."
            ),
        ),
    ],
)
```

**Step 2: Run corner tests**

Run: `pytest tests/test_track_db.py::TestAtlantaMotorsportsPark -v`
Run: `pytest tests/test_track_db.py::TestAMPEnrichedData -v`
Expected: Most tests PASS (landmarks may still need distance adjustments)

**Step 3: Commit corners**

```bash
git add cataclysm/track_db.py
git commit -m "feat: add 16 fully-annotated AMP corners with coaching metadata

All corners have direction, corner_type, elevation_trend, camber,
blind flags, character annotations, and coaching_notes. Corrected
GPS center (was 6km off), track length (was 280m off), and added
elevation_range_m. Data sourced from telemetry analysis + public guides."
```

---

### Task 4: Add Registry Alias for "AMP Full"

**Files:**
- Modify: `cataclysm/track_db.py` line 362-365 (registry dict)

**Step 1: Add the alias**

Add `"amp full": ATLANTA_MOTORSPORTS_PARK` to `_TRACK_REGISTRY`:

```python
_TRACK_REGISTRY: dict[str, TrackLayout] = {
    "barber motorsports park": BARBER_MOTORSPORTS_PARK,
    "atlanta motorsports park": ATLANTA_MOTORSPORTS_PARK,
    "amp full": ATLANTA_MOTORSPORTS_PARK,
}
```

**Step 2: Run alias test**

Run: `pytest tests/test_track_db.py::TestAtlantaMotorsportsPark::test_lookup_csv_alias -v`
Expected: PASS

**Step 3: Commit**

```bash
git add cataclysm/track_db.py
git commit -m "feat: add 'amp full' registry alias for AMP track

RaceChrono CSV metadata reports 'AMP Full' as the track name.
Without this alias, name-based lookup fails when GPS detection
also fails (GPS center was previously wrong by 6km)."
```

---

### Task 5: Run Full Quality Gates

**Files:**
- Check: `cataclysm/track_db.py`, `tests/test_track_db.py`

**Step 1: Run ruff check**

Run: `ruff check cataclysm/track_db.py tests/test_track_db.py`
Expected: 0 errors. Fix any issues.

**Step 2: Run ruff format**

Run: `ruff format cataclysm/track_db.py tests/test_track_db.py`

**Step 3: Run mypy**

Run: `mypy cataclysm/track_db.py tests/test_track_db.py`
Expected: 0 errors

**Step 4: Run full test suite**

Run: `pytest tests/test_track_db.py -v`
Expected: All tests PASS

Run: `pytest tests/ -v --timeout=120`
Expected: No regressions in other test files

**Step 5: Commit any quality fixes**

```bash
git add -A
git commit -m "chore: fix lint/format/type issues in AMP track data"
```

---

### Task 6: Verify End-to-End Integration

**Step 1: Verify track detection works with corrected coordinates**

```python
from cataclysm.parser import parse_racechrono_csv
from cataclysm.track_match import detect_track

csv = 'data/session/atlanta_motorsports_park/session_20251214_155803_amp_full_v3.csv'
parsed = parse_racechrono_csv(csv)
match = detect_track(parsed.data)
assert match is not None
assert match.layout.name == "Atlanta Motorsports Park"
assert match.distance_m < 1000  # should be very close now
print(f"Match: {match.layout.name}, distance: {match.distance_m:.0f}m, confidence: {match.confidence:.2f}")
```

**Step 2: Verify coaching pipeline includes corner metadata**

```python
from cataclysm.track_db import lookup_track

amp = lookup_track("AMP Full")
assert amp is not None
assert len(amp.corners) == 16
for c in amp.corners:
    assert c.direction is not None
    assert c.coaching_notes is not None
print("All 16 corners have full metadata")
```

**Step 3: Final commit and push**

```bash
git push
```
