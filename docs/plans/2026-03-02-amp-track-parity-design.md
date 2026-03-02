# AMP Track Data Parity Design

**Date:** 2026-03-02
**Goal:** Bring Atlanta Motorsports Park (AMP) track data in `track_db.py` to full parity with Barber Motorsports Park.

## Problem

The existing AMP entry has critical data errors and missing metadata:

- **GPS coordinates wrong by ~6km** — `detect_track()` cannot match AMP sessions (exceeds 5km threshold)
- **Track length off by ~280m** (3220m listed vs 2935m actual from telemetry)
- **12 corners instead of 16** — missing T13-T16 (Eau Rouge complex + final turn)
- **Zero coaching metadata** on any corner — no direction, corner_type, elevation, camber, blind, or coaching_notes
- **Landmark distances based on wrong track length** — all positions incorrect
- **No "amp full" registry alias** — CSV metadata track name doesn't match any registry key
- **Missing `elevation_range_m`**

## Approach: Satellite-Verified GPS Projection

Same methodology used for Barber:
1. Parse real AMP telemetry (4 sessions, best session: 122,623 GPS points, 10 valid laps)
2. Extract best-lap resampled data (Lap 6: 2932m, 97.75s)
3. Project satellite-identified landmark GPS coordinates onto the telemetry track line
4. Cross-reference with public track guides for corner metadata

## Data Sources

- **Telemetry:** `session_20251214_155803_amp_full_v3.csv` — 10 valid laps, GPS accuracy 0.31m, 15.6 satellites mean
- **Xtreme Xperience AMP driving tips** — Cal DeNyse instructor notes for T1, T4, T6, T10, T11, T14, T16
- **Kartclass AMP track review** — blind corners, brake countdown boards, elevation features
- **Official AMP turn number map PDF** — 16 numbered turns
- **RacingCircuits.info** — 1.835mi (2.953km) full circuit, Tilke design, Eau Rouge + Carousel tributes
- **Wikipedia** — 16 turns, 141ft (43m) elevation changes, Hermann Tilke design

## Section 1: Fix TrackLayout Metadata

| Field | Current (wrong) | Corrected |
|---|---|---|
| `center_lat` | 34.4218 | **34.4349** (GPS centroid) |
| `center_lon` | -84.1173 | **-84.1781** (GPS centroid) |
| `length_m` | 3220.0 | **2935.0** (median of 10 laps) |
| `elevation_range_m` | missing | **30.0** (29.8m from GPS altitude) |

## Section 2: 16 OfficialCorners with Full Metadata

All 16 corners from official track map, each with: `direction`, `corner_type`, `elevation_trend`, `camber`, `blind`, `coaching_notes`, `character` (where applicable).

Turn fractions derived from telemetry speed-trace minima and heading-rate analysis:

| Turn | Name | Frac | Dir | Type | Elevation | Camber | Blind | Char |
|---|---|---|---|---|---|---|---|---|
| T1 | Downhill Hairpin | 0.059 | right | hairpin | downhill | off-camber | - | - |
| T2 | Blind Left | 0.180 | left | kink | uphill | positive | blind | lift |
| T3 | Carousel Entry | 0.206 | right | sweeper | uphill | positive | - | - |
| T4 | The Carousel | 0.237 | right | sweeper | crest | positive | - | - |
| T5 | Downhill Hairpin | 0.353 | left | hairpin | downhill | off-camber | blind | - |
| T6 | Uphill Right | 0.373 | right | kink | uphill | positive | - | lift |
| T7 | Back Straight Entry | 0.498 | right | sweeper | flat | positive | - | - |
| T8 | Right Kink | 0.508 | right | kink | flat | positive | - | flat |
| T9 | Downhill Left | 0.559 | left | sweeper | downhill | positive | - | - |
| T10 | Hard Left Uphill | 0.610 | left | hairpin | uphill | positive | - | - |
| T11 | The Dip | 0.643 | right | sweeper | compression | positive | - | - |
| T12 | Downhill Left | 0.661 | left | kink | downhill | positive | - | lift |
| T13 | Eau Rouge Entry | 0.712 | left | esses | uphill | positive | - | flat |
| T14 | Eau Rouge Mid | 0.814 | right | esses | flat | positive | - | flat |
| T15 | Eau Rouge Exit | 0.898 | left | esses | flat | positive | - | flat |
| T16 | Final Right | 0.949 | right | sweeper | flat | positive | blind | - |

## Section 3: Satellite-Verified Landmarks

Rebuild `_AMP_LANDMARKS` with distances projected from GPS coordinates onto telemetry track line. Target: <15m projection error, matching Barber methodology.

Planned landmarks (~17-20 entries) organized by track section:
- S/F area: timing gantry, pit buildings
- T1 area: brake board, pit entry
- T3-T4: carousel curbing, hilltop crest
- T5: countdown boards (3, 2, 1), gravel trap
- Back straight: pit exit merge
- T7-T9: bridge, chicane curbs
- T10-T11: brake board, dip compression
- T12-T14: Eau Rouge curbing
- T15-T16: final curbs, victory lane

## Section 4: Verification Comments

Match Barber's provenance format:
```
# Verified against Google Maps satellite imagery (2026-03) using GPS-to-track-
# distance projection from real telemetry data (XXXX GPS points, XXXXm lap).
# Supplemented with public track guides:
#   - Xtreme Xperience AMP driving tips (Cal DeNyse)
#   - Kartclass AMP track review
#   - Official AMP turn number map
#   - RacingCircuits.info / Wikipedia facility documentation
```

## Section 5: Registry Alias

Add `"amp full"` key to `_TRACK_REGISTRY` pointing to `ATLANTA_MOTORSPORTS_PARK`, since RaceChrono CSV metadata reports track name as "AMP Full".

## Parity Verification

After implementation, verify:
1. `detect_track()` matches AMP sessions (centroid within 5km)
2. All 16 corners have complete metadata (same field coverage as Barber)
3. Landmark count >= 17 (Barber has 21)
4. All existing tests pass
5. Coaching prompt includes AMP corner-specific context (elevation, camber, tips)

## Files Changed

- `cataclysm/track_db.py` — primary changes (AMP section rewrite)
- `tests/test_track_db.py` — verify AMP parity assertions
