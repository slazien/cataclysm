# Track Profile Creation Guide

Comprehensive process for creating a fully detailed track metadata profile in `cataclysm/track_db.py`. This is the reference document for adding any new track to the system.

---

## What a Complete Track Profile Contains

A complete profile consists of **3 layers** that build on each other:

### Layer 1: TrackLayout (track-level metadata)
| Field | Type | Source | Example |
|-------|------|--------|---------|
| `name` | str | Official circuit name | `"Barber Motorsports Park"` |
| `center_lat` | float | GPS centroid from telemetry | `33.5302` |
| `center_lon` | float | GPS centroid from telemetry | `-86.6215` |
| `country` | str | Country code | `"US"` |
| `length_m` | float | Median lap distance from telemetry | `3662.4` |
| `elevation_range_m` | float | Max - min GPS altitude | `60.0` |
| `corners` | list[OfficialCorner] | See Layer 2 | |
| `landmarks` | list[Landmark] | See Layer 3 | |

### Layer 2: OfficialCorner (per-corner metadata)
| Field | Type | Required | Source | Values |
|-------|------|----------|--------|--------|
| `number` | int | Yes | Official track map | 1, 2, 3... |
| `name` | str | Yes | Track guide / common name | `"Charlotte's Web"` |
| `fraction` | float | Yes | Telemetry speed minimums | 0.0–1.0 |
| `lat` | float | No | GPS at apex | |
| `lon` | float | No | GPS at apex | |
| `character` | str | No | Telemetry analysis | `"flat"`, `"lift"`, `"brake"` |
| `direction` | str | Yes* | Track map / onboard video | `"left"`, `"right"` |
| `corner_type` | str | Yes* | Track guide / analysis | `"hairpin"`, `"sweeper"`, `"chicane"`, `"kink"`, `"esses"` |
| `elevation_trend` | str | Yes* | Telemetry altitude + topo | `"uphill"`, `"downhill"`, `"flat"`, `"crest"`, `"compression"` |
| `camber` | str | Yes* | Track guide / onboard video | `"positive"`, `"negative"`, `"off-camber"` |
| `blind` | bool | Yes* | Track guide / onboard video | `True` / `False` |
| `coaching_notes` | str | Yes* | Instructor knowledge | 1–2 sentences |

*Fields marked Yes* are required for a "complete" profile. Without them, coaching output is generic.

### Layer 3: Landmark (visual reference points)
| Field | Type | Required | Source | Example |
|-------|------|----------|--------|---------|
| `name` | str | Yes | Satellite imagery | `"T5 3 board"` |
| `distance_m` | float | Yes | GPS projection onto telemetry | `904.0` |
| `landmark_type` | LandmarkType | Yes | Visual classification | See types below |
| `lat` | float | No | Satellite / Google Maps | |
| `lon` | float | No | Satellite / Google Maps | |
| `description` | str | No | Context for coaching | `"Span near T7"` |

**LandmarkType values**: `brake_board`, `structure`, `barrier`, `road`, `curbing`, `natural`, `marshal`, `sign`

---

## Complete Process: Step by Step

### Phase 1: Gather Raw Data (telemetry + external sources)

#### 1.1 Obtain Telemetry Data
- Need at least one RaceChrono CSV v3 session at the track
- Prefer sessions with 5+ clean laps for statistical reliability
- Extract from the app: parse the CSV, get resampled lap data

#### 1.2 Compute Track-Level Metrics from Telemetry
```python
import numpy as np
from cataclysm.parser import parse_racechrono_csv
from cataclysm.engine import process_session

session = parse_racechrono_csv("path/to/session.csv")
processed = process_session(session)

# GPS centroid (used for track auto-detection)
all_lats = session.data["lat"].dropna()
all_lons = session.data["lon"].dropna()
center_lat = float(all_lats.mean())
center_lon = float(all_lons.mean())

# Lap length (median of clean laps)
lap_distances = [float(lap.resampled["lap_distance_m"].iloc[-1]) for lap in processed.laps]
length_m = float(np.median(lap_distances))

# Elevation range (from GPS altitude if available)
if "altitude_m" in session.data.columns:
    alts = session.data["altitude_m"].dropna()
    elevation_range_m = float(alts.max() - alts.min())
```

#### 1.3 Export Telemetry Trace for Map Overlay
Save the best lap's GPS trace for projection work later:
```python
best_lap = min(processed.laps, key=lambda l: l.summary.lap_time_s)
df = best_lap.resampled
np.savez("/tmp/track_trace.npz",
    dist=df["lap_distance_m"].to_numpy(),
    lat=df["lat"].to_numpy(),
    lon=df["lon"].to_numpy(),
)
```
Record: total GPS point count, total lap distance, which lap number.

#### 1.4 Collect External Source Materials
**Must-have sources:**
1. **Official track map** with corner numbering — usually on track website
2. **Google Maps satellite imagery** at maximum zoom (zoom 20–22 shows brake boards)
3. **Corner-by-corner track guide** from driving school or track day organization
   - racetrackdriving.com
   - Track-specific driving school guides (e.g., Porsche Experience, Skip Barber)
   - NA-Motorsports / Chris Ingle corner notes
   - Private instructor notes if available

**Nice-to-have sources:**
4. **Onboard video** from the track (YouTube, personal footage)
5. **ESRI satellite imagery** (sometimes higher resolution than Google in rural areas)
6. **Wikipedia / BhamWiki** or local wiki for facility info
7. **Topographic data** for elevation verification (USGS, OpenTopography)
8. **Track driving forum posts** (often have detailed corner descriptions)

### Phase 2: Determine Corner Fractions

#### 2.1 Identify Official Corner Numbering
- Use the official track map as the single source of truth for corner *numbers* and *names*
- Note: some tracks number differently across organizations. Pick one canonical numbering and document which source you used.

#### 2.2 Locate Apex Positions in Telemetry
Corner fractions are the **apex position as a fraction of total lap distance** (0.0–1.0).

**Primary method: Speed trace analysis**
```python
import matplotlib.pyplot as plt

df = best_lap.resampled
plt.figure(figsize=(20, 6))
plt.plot(df["lap_distance_m"], df["speed_mps"] * 3.6, linewidth=0.8)
plt.xlabel("Distance (m)")
plt.ylabel("Speed (km/h)")
plt.title("Speed trace — identify speed minimums at corners")
plt.grid(True, alpha=0.3)
plt.savefig("/tmp/speed_trace.png", dpi=150)
```

For each official corner:
1. Find the speed minimum in the telemetry that corresponds to that corner
2. Record the distance at the speed minimum
3. Compute fraction = distance / total_lap_distance

**Cross-reference with satellite imagery:**
- Plot the GPS trace on satellite imagery
- Visually confirm that the speed minimum location matches the physical corner apex

**Validation:**
- Fractions must be monotonically increasing (corners appear in order around the track)
- Adjacent fractions should have reasonable spacing (> 0.02 apart for real corners, < 0.01 suggests a single complex split too finely)
- Compare against any published lap guides that mention "X% of the way around the track"

#### 2.3 Determine Corner Character
For each corner, classify from telemetry:
- `"brake"` — significant deceleration before entry (> 0.3g braking)
- `"lift"` — brief speed reduction but no hard braking (< 0.3g)
- `"flat"` — no speed reduction (maintain or increase speed through)
- `None` — let the system auto-detect from KPIs

Look at the brake/throttle trace alongside the speed trace. Character is only set explicitly when it provides useful coaching context (e.g., marking a corner as "flat" tells the AI not to suggest braking).

### Phase 3: Fill Corner Coaching Metadata

For EVERY corner, fill these fields by combining track guides with telemetry analysis:

#### 3.1 Direction (`"left"` | `"right"`)
- Trivial from any track map
- Verify against GPS heading change in telemetry if unsure

#### 3.2 Corner Type
| Type | Description | Telemetry Signature |
|------|-------------|---------------------|
| `"hairpin"` | 90+ degree turn, lowest speeds | Deep V in speed trace |
| `"sweeper"` | Long-radius constant arc | Gradual speed dip, sustained |
| `"kink"` | Slight direction change, high speed | Barely visible in speed trace |
| `"chicane"` | Quick left-right or right-left | Two close speed dips |
| `"esses"` | Multiple linked curves | Oscillating speed trace |

#### 3.3 Elevation Trend
| Trend | Meaning | Effect on Driving |
|-------|---------|-------------------|
| `"uphill"` | Climbing through corner | Helps braking, shortens stopping distance |
| `"downhill"` | Descending through corner | Hurts braking, car feels lighter |
| `"flat"` | No significant elevation change | Neutral |
| `"crest"` | Goes over a hill peak | Car goes light, reduced grip |
| `"compression"` | Drops into a valley | Car gets loaded, extra grip |

**Sources for elevation:**
1. GPS altitude in telemetry (noisy but directional)
2. Topographic data / elevation APIs
3. Track guides almost always mention elevation changes
4. Onboard video shows crests and compressions clearly

#### 3.4 Camber
| Value | Meaning |
|-------|---------|
| `"positive"` | Track slopes toward the inside of the corner (helps grip) |
| `"negative"` | Track slopes away from the inside (fights grip) — rare |
| `"off-camber"` | Same as negative, more extreme — common in older tracks |

- Positive camber is the default — only explicitly set when it's `"off-camber"` or `"negative"` for coaching value.
- Source: track guides and onboard video. Not detectable from GPS/telemetry.

#### 3.5 Blind (`True`/`False`)
- A corner is blind when the driver cannot see the apex or exit on approach
- Source: track guides, onboard video, personal experience
- Default is `False` — only set `True` when explicitly blind

#### 3.6 Coaching Notes
Write 1–2 sentences of practical instructor-level advice. Guidelines:
- **Be actionable**: "Late apex to set up T2" not "This is a corner"
- **Reference physics**: "Downhill increases stopping distance" not just "Be careful"
- **Reference other corners when relevant**: "Exit speed sets up the back straight" creates context
- **Mention specific techniques**: "Trail brake to rotate", "Sacrifice entry for exit"
- **Flag dangers**: "Key overtaking spot", "Most dangerous turn on track"
- **Reference landmarks when applicable**: "Use brake boards", "Commit to reference points"

**Quality benchmark** — compare against Barber T5:
```
"Key overtaking spot. Use brake boards. Very late apex — corner tightens at exit."
```
This is concise, actionable, mentions a landmark cue, and flags a non-obvious characteristic (tightening exit).

### Phase 4: Create Landmark List

#### 4.1 Identify Landmarks from Satellite Imagery

Walk the track in Google Maps satellite view, section by section. Record everything a driver can see from the cockpit. Organize by track section.

**High-confidence satellite landmarks (visible at zoom 19+):**
- Timing gantries (S/F line structures)
- Pit buildings, garages
- Pedestrian bridges, overpasses
- Large buildings (museums, hospitality)
- Gravel traps, runoff areas
- Road junctions (pit entry, pit exit merge)
- Concrete barriers, tire walls
- Large signs (sponsor signs visible from satellite)

**Medium-confidence landmarks (need zoom 21–22, Google Maps only):**
- Individual brake boards (100m, 200m, 300m boards)
- Small signs
- Marshal posts

**Not visible from satellite (need track guides / onboard video):**
- Natural features: crests, compressions, banked entries, elevation changes
- Curbing (position visible from satellite but character isn't)

#### 4.2 Get GPS Coordinates of Each Landmark

For each identified landmark:
1. Right-click on Google Maps satellite at the **leading edge** of the landmark (the side the driver sees first on approach)
2. Copy the GPS coordinates
3. Record them with the landmark name

**Important**: Use the leading edge, not the center. A driver approaching a bridge sees the near side first — that's the reference point.

#### 4.3 Project GPS Coordinates onto Telemetry Trace

Use the perpendicular projection function to convert GPS → track distance:

```python
import numpy as np

# Load telemetry trace
d = np.load('/tmp/track_trace.npz')
dist, lat, lon = d['dist'], d['lat'], d['lon']

def project_to_track(plat: float, plon: float) -> tuple[float, float]:
    """Project a GPS point onto the track line.

    Returns (track_distance_m, off_track_error_m).
    """
    lat_center = float(np.mean(lat))
    m_per_deg_lat = 111320.0
    m_per_deg_lon = 111320.0 * np.cos(np.radians(lat_center))
    dx = (lon - plon) * m_per_deg_lon
    dy = (lat - plat) * m_per_deg_lat
    dists_m = np.sqrt(dx**2 + dy**2)
    nearest_idx = int(np.argmin(dists_m))
    return float(dist[nearest_idx]), float(dists_m[nearest_idx])
```

**Quality check**: The `off_track_error_m` should be small:
- < 5m for trackside structures (barriers, curbing)
- < 15m for nearby structures (buildings, bridges)
- < 30m for distant structures (large buildings visible from afar)
- > 50m means something is wrong (wrong landmark GPS, bad telemetry, wrong track section)

#### 4.4 Assign LandmarkType

| LandmarkType | Use for |
|-------------|---------|
| `brake_board` | Numbered distance boards before corners (100m, 200m, 300m) |
| `structure` | Buildings, bridges, gantries, timing equipment |
| `barrier` | Concrete walls, tire walls, gravel traps, runoff areas |
| `road` | Track features: pit entry/exit, merge points, access roads |
| `curbing` | Apex curbs, exit curbs, rumble strips |
| `natural` | Crests, compressions, banked entries, trees, elevation features |
| `marshal` | Marshal posts, flag stations |
| `sign` | Sponsor signs, distance signs, warning signs |

**Priority rule**: Brake boards > structures > signs for brake point references. The landmark system has a preference hierarchy (see `_BRAKE_PREFERRED_TYPES` in `landmarks.py`).

#### 4.5 Add Descriptions
Add a `description` string when the landmark name alone isn't enough context:
- "Garages on left" — helps the driver orient
- "Blind crest" — flags a safety-relevant feature
- "Span near T7" — connects to corner numbering
- "Car goes light" — describes the physical experience

Only add descriptions that add coaching value. Don't describe every landmark.

#### 4.6 Coverage Goals
Aim for **15–25 landmarks per track**. Distribution targets:
- 1–2 in the start/finish area (gantry, pit buildings)
- At least 1 per major braking zone (brake boards are ideal)
- 1–2 per major track section (buildings, bridges, barriers)
- Pit entry and pit exit are almost always useful landmarks
- Natural features (crests, compressions) at key elevation changes

Too few landmarks (< 10): the coaching system falls back to raw meter distances.
Too many landmarks (> 30): diminishing returns, harder to maintain.

### Phase 5: Assemble the Profile in track_db.py

#### 5.1 Code Structure
Follow this exact pattern (based on the Barber reference implementation):

```python
# ---------------------------------------------------------------------------
# {Track Name} visual landmarks
# ---------------------------------------------------------------------------
# Verification:
#   - GPS centroid from real telemetry: ({lat}, {lon})
#   - Median lap distance ({n} laps): {length}m
#   - Elevation range (GPS altitude): ~{range}m ({min}–{max}m ASL)
#   - Distances below projected from best-lap GPS onto satellite imagery
#   - Session: {filename} (best lap #{n})

_TRACK_LANDMARKS: list[Landmark] = [
    # --- Start/Finish area ---
    Landmark("S/F gantry", 0.0, LandmarkType.structure, description="..."),
    ...
    # --- T1-T4 Section Name ---
    ...
]

TRACK_CONSTANT = TrackLayout(
    name="Official Track Name",
    landmarks=_TRACK_LANDMARKS,
    center_lat=...,
    center_lon=...,
    country="US",
    length_m=...,
    elevation_range_m=...,
    corners=[
        OfficialCorner(
            1,
            "Corner Name",
            0.05,
            direction="left",
            corner_type="sweeper",
            elevation_trend="downhill",
            camber="positive",
            coaching_notes="Actionable coaching tip.",
        ),
        ...
    ],
)
```

#### 5.2 Register in Track Registry
Add the track to `_TRACK_REGISTRY`:
```python
_TRACK_REGISTRY: dict[str, TrackLayout] = {
    ...
    "new track name": NEW_TRACK_CONSTANT,
    # Add aliases if RaceChrono uses different names:
    "alternate name": NEW_TRACK_CONSTANT,
}
```

**Important**: Registry keys are normalized (lowercased, stripped). Add all known name variants that RaceChrono might use.

#### 5.3 Comment Block
Always include a verification comment block above the landmarks list documenting:
- GPS centroid coordinates
- Median lap distance and number of laps
- Elevation range
- Source session filename
- Methods used for landmark distance derivation

### Phase 6: Validation

#### 6.1 Code Quality
```bash
ruff check cataclysm/track_db.py
ruff format cataclysm/track_db.py
mypy cataclysm/track_db.py
pytest tests/ -k track -v
```

#### 6.2 Fraction Sanity Checks
- All fractions between 0.0 and 1.0
- Fractions are monotonically increasing
- No two corners have the same fraction
- Spacing is reasonable (no two corners within 0.01 fraction of each other unless they're a tight complex)

#### 6.3 Landmark Distance Checks
- All distances between 0.0 and `length_m`
- Distances are roughly increasing (landmarks are listed in track order)
- Distances near corner apexes should be near `fraction * length_m`
- No duplicate distances (suggests copy-paste errors)

#### 6.4 Coaching Integration Test
Upload a session at the new track and verify:
1. Track auto-detection works (GPS centroid matches within 5km)
2. Corner numbering matches official numbering
3. Coaching report references landmark names instead of raw meters
4. Corner metadata (elevation, camber, blind) appears in coaching output

---

## Downstream Systems That Consume Track Metadata

Understanding what uses each field helps prioritize what to fill in:

| Field | Used By | Impact If Missing |
|-------|---------|-------------------|
| `center_lat/lon` | `track_match.py` GPS detection | Track won't auto-detect, falls back to name |
| `length_m` | Displayed in UI | Minor — cosmetic |
| `elevation_range_m` | Displayed in UI, coaching context | Minor |
| `fraction` | `track_db.py:locate_official_corners()` | **Critical** — corners placed at wrong positions |
| `direction` | `coaching.py` corner analysis section | Generic coaching without turn direction |
| `corner_type` | `coaching.py` line 382–383 | Missing "Type: sweeper" in coaching prompt |
| `elevation_trend` | `coaching.py` line 379–381 | Missing elevation guidance |
| `camber` | `coaching.py` line 386–387 | Missing camber warning (only shown for off-camber) |
| `blind` | `coaching.py` line 384 | Missing blind corner warning |
| `coaching_notes` | `coaching.py` line 388–389 | Missing "Coach tip:" in prompt — biggest quality loss |
| `character` | `Corner.character` → coaching prompt | Generic corner handling advice |
| Landmarks | `landmarks.py` → `coaching.py` | **Raw meter distances in coaching output** instead of "at the 200m board" |

**Priority**: `fraction` > `coaching_notes` > `direction`/`corner_type` > `elevation_trend` > landmarks > `camber`/`blind`

---

## Time Estimates and Workflow

| Phase | Time | Parallelizable |
|-------|------|----------------|
| 1. Gather telemetry data | 5 min | Start here |
| 2. Corner fractions from speed trace | 15–30 min | After Phase 1 |
| 3. Corner coaching metadata | 30–60 min | After Phase 2, use parallel web research |
| 4. Landmark identification + projection | 30–60 min | Can run in parallel with Phase 3 |
| 5. Assembly in track_db.py | 15 min | After Phases 2–4 |
| 6. Validation | 10 min | After Phase 5 |

**Total: ~2–3 hours for a complete profile** (can be less with good source materials).

**Optimization tips:**
- Use parallel agents: one for web research (track guides, corner descriptions), one for telemetry analysis (speed trace, fractions, elevations), one for satellite imagery (landmark GPS coordinates)
- If a prior session exists at the track, most of Phase 1 is already done
- Track guides are the highest-value source — find one good guide and it fills 80% of the corner metadata

---

## Quality Tiers

Not every track needs the full Barber-level treatment. Here's a tiered approach:

### Tier 1: Skeleton (minimum viable)
- `name`, `center_lat`, `center_lon`, `length_m`
- Corner numbers, names, fractions
- No coaching metadata, no landmarks
- **Result**: Correct corner numbering but generic coaching

### Tier 2: Coaching-Ready
- Everything in Tier 1 plus:
- Corner `direction`, `corner_type`, `coaching_notes`
- Basic landmarks (S/F gantry, pit entry/exit, 3–5 key structures)
- **Result**: Good coaching output with some landmark references

### Tier 3: Complete (Barber-level)
- Everything in Tier 2 plus:
- Corner `elevation_trend`, `camber`, `blind`
- Full landmark coverage (15–25 landmarks)
- Verification comment block with data sources
- `elevation_range_m`
- **Result**: Premium coaching with full spatial context

**Upgrade path**: Always start with Tier 1 (fractions are critical), then upgrade to Tier 2 (coaching notes add the most value per effort), then Tier 3 (landmarks and physical characteristics).

---

## Checklist for New Track Profile

- [ ] Telemetry session available with 5+ clean laps
- [ ] GPS centroid computed
- [ ] Median lap distance computed
- [ ] Official corner map obtained (corner numbers + names)
- [ ] Corner fractions derived from speed trace minimums
- [ ] Fractions validated (monotonic, reasonable spacing)
- [ ] Corner directions filled (all corners)
- [ ] Corner types filled (all corners)
- [ ] Elevation trends filled (all corners)
- [ ] Camber noted for off-camber corners
- [ ] Blind corners flagged
- [ ] Coaching notes written (all corners)
- [ ] Landmarks identified from satellite imagery (15–25)
- [ ] Landmark GPS coordinates collected
- [ ] Landmark distances projected onto telemetry
- [ ] Projection errors checked (< 15m for most)
- [ ] LandmarkTypes assigned
- [ ] Descriptions added where useful
- [ ] Code assembled in track_db.py
- [ ] Track registered in `_TRACK_REGISTRY` with aliases
- [ ] Verification comment block added
- [ ] ruff check + format passes
- [ ] mypy passes
- [ ] Tests pass
- [ ] End-to-end coaching test with real session

---

## Lessons Learned from Past Tracks

### Barber Motorsports Park (reference implementation)
- **What went well**: Porsche Experience corner guide was an excellent primary source, covered elevation, camber, and coaching tips for all 16 corners. Telemetry overlay approach (project GPS onto track line) was the most accurate method for landmark distances.
- **What was hard**: Individual brake boards are only 1m wide — need Google Maps zoom 21+ (ESRI maxes at 19). Leaflet map had container sizing issues with Playwright automation.
- **Key insight**: "Perpendicular projection from landmark GPS onto the telemetry track line" is a mathematically precise operation. Don't try to trace along the track manually.

### Atlanta Motorsports Park
- **Originally a Tier 1 skeleton** — corner fractions were rough estimates without telemetry validation.
- **Upgraded to Tier 3** after real telemetry data became available (session from Dec 2024).
- **Key insight**: Real telemetry-derived fractions differed significantly from map estimates. Fractions from speed trace minimums are always more accurate than geometric map analysis.
- **Name aliasing**: RaceChrono stored sessions as "AMP Full" — needed an alias in the registry.

### General Lessons
- Track guides from driving schools are 10x more valuable than Wikipedia for coaching metadata
- Elevation is the hardest field to verify without topographic data or onboard video
- Camber is almost impossible to determine from satellite imagery — always needs track guides or personal experience
- `character` field ("flat"/"lift"/"brake") should only be set for clear-cut cases — let the system auto-detect for ambiguous corners
- Start/finish gantry at distance 0.0 is a universal landmark — always include it
