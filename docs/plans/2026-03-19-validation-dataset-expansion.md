# Validation Dataset Expansion — Data Acquisition Plan

**Goal:** Expand physics validation from 42 entries / 3 tracks to 100+ entries / 6+ tracks with higher-quality, professionally-sourced ground truth. Fix critical dataset imbalances (AWD=0, street=2, FWD=4, Barber=58%). Enable per-corner validation beyond total-lap-time comparison.

**Prerequisite:** Physics Tier 1+2 improvements should land first — better model accuracy reduces noise when validating against new data sources. But track reference work (Phase 1) can proceed in parallel.

**Related docs:**
- `docs/plans/2026-03-18-physics-validation-framework.md` — Phase 2 Items 3-4 (OptimumLap, Published Lap Times)
- `docs/physics-validation-methodology-review-2026-03-19.md` — Dataset imbalance analysis, expansion priorities
- `docs/physics-engine-improvement-research-2026-03-19.md` — Phase 3 Item 8

---

## Current State

| Dimension | Current | Target |
|-----------|---------|--------|
| Total entries | 42 | 100+ |
| Tracks | 3 (Barber 58%, AMP, Roebling) | 6+ tracks, each ≥10 entries |
| Street tires | n=2 | ≥8 |
| FWD cars | n=4 (1 model: Civic Type R) | ≥10 (3+ models) |
| AWD cars | n=0 | ≥5 |
| High downforce (explicit CL·A) | n=0 | ≥5 |
| High hp/t (>350) | n=3 | ≥8 |
| Professional driver data | n=0 (all amateur/club) | ≥20 (C&D, MotorTrend) |
| Per-corner validated | n=0 | ≥5 sessions |

### Current Data Sources
- Forum posts: gr86.org, rennlist.com, mustang6g.com, camaro6.com, trackmustangsonline.com
- Aggregators: lapmeta.com, fastestlaps.com, laptrophy.com
- Community: jst-performance.com, nasamidsouth.com
- Quality: variable — unknown driver skill, tire condition, weather, sometimes guessed tires

---

## Phase 1 — New Track References (Highest Leverage)

Each new track reference unlocks an entire ecosystem of published lap times. Priority order by data availability × diversity.

### 1A: VIR (Virginia International Raceway) — Full Course

**Why #1 priority:** Unlocks Car and Driver Lightning Lap — the single best validated lap time dataset in existence. ~200+ cars, professional drivers, consistent methodology, published tire specs, controlled conditions. Annual since 2008.

**Track specs:** 3.27 mi / 5.26 km, 18 turns, elevation change ~100 ft

**How to get GPS trace:**
1. **Reddit r/CarTrackDays** — post asking for a RaceChrono/Harry's LapTimer session at VIR Full Course. Offer credit in the app.
2. **VIR HPDE Facebook groups** — "VIR Track Enthusiasts", "NASA Mid-Atlantic"
3. **RaceChrono community** — racechrono.com forum, search for VIR traces
4. **SCCA/NASA Mid-South timing data** — race results have GPS-based sector times
5. **TrackAddict / Harry's LapTimer exports** — search forums for CSV/GPX exports
6. **Direct outreach** — email VIR's driving experiences dept; they run their own HPDE and may share reference data
7. **Fallback: synthetic** — build from satellite imagery + elevation data (lower accuracy, last resort)

**Minimum viable trace requirements:**
- Full Course layout (not North or South only)
- GPS ≥10 Hz (RaceChrono default)
- Clean hot lap (no traffic, no off-track)
- Any car is fine — we just need the racing line geometry

**Unlocked data (Car and Driver Lightning Lap):**

| Car | Time | Tires | Year | Key value |
|-----|------|-------|------|-----------|
| Subaru BRZ tS | 3:11.1 | PS4S | 2025 | Street tire baseline |
| Civic Type R FL5 | 2:55.6 | PS4S | 2023 | FWD benchmark |
| GR Corolla | 3:00.4 | PS4S | 2023 | AWD benchmark! |
| BMW M2 G87 | 2:56.9 | PS Cup 2 | 2024 | Mid-range sports |
| Ford Mustang Dark Horse | 2:51.2 | PS Cup 2 | 2024 | Muscle car |
| Corvette C8 Z51 | 2:46.7 | PS4S | 2023 | American sports |
| Nissan Z Nismo | 2:54.3 | Dunlop SP 050 | 2024 | New entry |
| Porsche Cayman GT4 RS | 2:38.6 | PS Cup 2 | 2023 | Mid-engine track |
| Corvette C8 Z06 | 2:38.6 | Z07 pkg | 2023 | High performance |
| Porsche 911 GT3 RS 992 | 2:35.5 | Cup 2 R | 2023 | Track weapon |
| BMW M4 CSL | 2:45.3 | Cup 2 | 2023 | High-downforce |
| Toyota GR Supra | 2:53.0 | PS4S | 2023 | Known car in our DB |
| Hyundai Elantra N | 3:03.5 | PS4S | 2023 | FWD, known car |
| Subaru WRX | 3:07.0 | PS4S | 2023 | AWD! |
| Audi RS3 | 2:56.9 | PS Cup 2 | 2024 | AWD! |
| Mercedes-AMG C63 S E | 2:49.1 | PS Cup 2 | 2024 | Hybrid, heavy, AWD! |

**C&D dataset fixes our critical gaps:** AWD (GR Corolla, WRX, RS3, AMG C63 S E), FWD diversity (Elantra N, Civic), street tires (all PS4S entries), high-downforce (GT3 RS, CSL), professional drivers (100% of entries).

**Expected yield:** 30-50 new validation entries from C&D alone, plus community VIR lap times from forums.

**Effort:** 1-2 days to build track reference once GPS trace obtained. Acquiring the trace is the bottleneck.

---

### 1B: Laguna Seca (WeatherTech Raceway)

**Why #2:** MotorTrend Best Driver's Car testing ground, massive community dataset, iconic track with unique features (Corkscrew = extreme elevation change, tests vertical curvature model).

**Track specs:** 2.238 mi / 3.602 km, 11 turns, elevation change 180 ft

**How to get GPS trace:**
1. Same channels as VIR — Reddit, RaceChrono forum, SCCA SFR
2. **iRacing/sim community** — Laguna Seca laser-scanned for iRacing; community GPS traces more common
3. **Mazda Raceway driving experiences** — they run experiences on the track

**Unlocked data:**
- MotorTrend Best Driver's Car (annual, ~12 cars/year, pro drivers)
- MotorTrend Hot Lap (Randy Pobst, dozens of cars)
- Massive community dataset (one of the most-driven tracks in the US)
- Strong representation of Japanese sports cars (Miata, GR86, NSX)

**Expected yield:** 20-40 new entries.

**Effort:** 1-2 days for track reference.

---

### 1C: Road Atlanta

**Why #3:** Major IMSA venue, strong HPDE community, different character from our current tracks (high-speed, flowing, significant elevation change). We already have Atlanta Motorsports Park (AMP, the small track) — Road Atlanta is the large, professionally-maintained circuit.

**Track specs:** 2.54 mi / 4.088 km, 12 turns, elevation change 75 ft

**Unlocked data:**
- IMSA timing data (pro)
- Massive NASA/SCCA Southeast community data
- Petit Le Mans supporting race data

**Expected yield:** 15-25 new entries.

**Effort:** 1-2 days.

---

### 1D: COTA (Circuit of the Americas) — Stretch Goal

**Why:** Only F1-grade circuit in the US, excellent published data, tests the model on a very different track profile (long straights + complex multi-apex corners). Expensive to run HPDEs at, so community data is sparser.

**Expected yield:** 10-15 entries.

---

## Phase 2 — Gold-Standard Published Data Sources

These are the databases to mine once we have track references.

### 2A: Car and Driver Lightning Lap (VIR)

**Quality:** Gold standard. Professional drivers, controlled methodology, published tire specs, same track every year.

**URL:** caranddriver.com/features/a23319884/lightning-lap-times-every-car-every-lap-time/

**Integration approach:**
1. Scrape/transcribe the full historical table (2008-2025)
2. For each entry: map car → `vehicle_db` key, tire → `tire_db` key, extract time
3. Add `source: "Car and Driver Lightning Lap {year}"` and `mod_level: stock` or `light`
4. Professional driver adjustment: C&D drivers at ~95-98% of physics limit → expect ratio ~0.95-0.98 (vs our amateur data at 0.80-0.95)

**Volume:** ~200 unique car+tire entries across all years. Many cars repeated year-over-year (same car, newer tires = excellent isolation test).

**Key diagnostic value:**
- Same car + different years = tire evolution tracking
- Same year + different cars = model breadth validation
- All with professional drivers = removes driver skill variance

### 2B: MotorTrend Hot Lap / Best Driver's Car (Laguna Seca)

**Quality:** Professional (Randy Pobst for Hot Lap). Consistent methodology. Less tire info than C&D.

**URL:** motortrend.com hot lap leaderboard

**Integration approach:** Similar to C&D. May need to research tire specs independently for some entries.

**Volume:** 50-80 entries (Hot Lap has been running since ~2010).

### 2C: FastestLaps.com (All Tracks)

**Quality:** Variable — aggregates from multiple sources. Useful for bulk expansion once we filter for quality.

**Already partially used:** BMW M2 and 911 GT3 entries in current dataset cite fastestlaps.com.

**Integration approach:**
1. For each track we support: query all available lap times
2. Filter for entries with known tire specs (many entries lack tire info — skip those)
3. Cross-reference with other sources for credibility
4. Tag `source_quality: aggregated` vs `source_quality: primary`

**Volume:** 10-30 additional entries per track we already support. More for VIR/Laguna once added.

**Key value:** Fills gaps in underrepresented categories without needing new track references.

### 2D: Grassroots Motorsports $2000 Challenge

**Quality:** Well-documented, budget-focused. Tire specs always published (relevant to our street/endurance categories). Tests at Gainesville Raceway and other venues.

**Key value:** Street tire and budget tire data — exactly our weakest category.

### 2E: Sport Auto Supertest (Nürburgring) — Future/Stretch

**Quality:** Highest in the world for variety. Hundreds of cars, professional drivers, detailed sector times.

**Blocked by:** 20.8 km track reference is extremely complex. Corner detection alone would be ~150+ corners. Not practical near-term.

**When to revisit:** If we expand to European tracks or get significant user demand for Nordschleife.

---

## Phase 3 — Per-Corner Telemetry Validation

Total lap time validation can hide compensating errors (fast on straights, slow in corners). Per-corner validation is strictly more valuable.

### 3A: Own Telemetry Sessions

**Approach:**
1. Identify 2-3 users with known cars + tires who run at our supported tracks
2. Ask for their RaceChrono CSV + best lap details
3. We have both their actual telemetry AND our optimal prediction
4. Compare per-corner: apex speed, braking distance, corner entry speed, exit speed
5. This validates the solver segment-by-segment, not just total time

**Target:** 5 sessions minimum across 2+ tracks, 2+ tire categories.

**How to source:**
- Engaged users from staging analytics (opt-in)
- Reddit r/CarTrackDays — offer free coaching report in exchange for telemetry sharing permission
- NASA/SCCA chapter partnerships

### 3B: Published Telemetry Comparison

Some YouTube channels and blogs publish detailed telemetry screenshots/overlays (Speed Academy, Engineering Explained, Savagegeese track tests). These can provide apex speed datapoints even without the raw CSV.

### 3C: Instructor Blind Review (from validation framework Phase 3)

Already planned in `2026-03-18-physics-validation-framework.md` Item 5. Cross-reference: instructor coaching notes vs our physics-optimal recommendations. Validates not just the solver but the coaching interpretation layer.

---

## Phase 4 — Cross-Solver Validation

### 4A: OptimumLap

Already planned in validation framework Phase 2 Item 3. Run same car specs through OptimumLap (free, industry-standard). Target: <3% difference.

### 4B: LapSim / ChassisSim

Commercial tools. If we can get trial access, running the same comparison would provide additional confidence. Lower priority than OptimumLap (which is free).

---

## Dataset Quality Standards

Every new entry in `data/realworld_comparison.csv` must have:

| Field | Required | Notes |
|-------|----------|-------|
| `car` | Yes | Must map to a `vehicle_db` entry |
| `track` | Yes | Must have a canonical track reference NPZ |
| `real_time_s` | Yes | Best lap time from source |
| `tire_model` | Yes | Specific tire name, not just category |
| `tire_category` | Yes | One of: street, endurance_200tw, super_200tw, 100tw, r_compound, slick |
| `mu` | Yes | From `tire_db` per-tire mu, or category default |
| `mod_level` | Yes | stock / light / heavy |
| `source` | Yes | URL or citation |
| `source_quality` | Recommended | `professional` / `primary` / `aggregated` / `community` |
| `driver_level` | Recommended | `pro` / `advanced_club` / `intermediate` / `unknown` |
| `notes` | Recommended | Anything relevant: weather, session conditions, tire age |

**Professional driver entries** (C&D, MotorTrend) should be tagged `driver_level: pro` — the expected ratio range is different (~0.95-0.98 vs ~0.80-0.95 for amateurs). Analysis should segment by driver level.

---

## Imbalance Fix Targets

### AWD (current: 0 entries)
**Via VIR/C&D Lightning Lap:** GR Corolla, Subaru WRX, Audi RS3, Mercedes-AMG C63 S E Performance
**Via community:** Golf R, Audi TT RS, Nissan GT-R (all common HPDE cars)
**Target:** ≥8 AWD entries

### FWD (current: 4 entries, 1 model)
**Via VIR/C&D:** Elantra N, Civic Type R (already have), Integra Type S
**Via community:** Veloster N (already have 1 at Roebling), Mini JCW, Focus ST/RS (if FWD variant)
**Target:** ≥10 FWD entries, ≥3 models

### Street Tires (current: 2 entries)
**Via VIR/C&D:** Nearly all Lightning Lap entries use Michelin PS4S = endurance/street boundary
**Via community:** Add more stock-tire entries from lapmeta/fastestlaps
**Target:** ≥8 street entries

### High Downforce (current: 0 explicit)
**Via VIR/C&D:** 911 GT3 RS (large wing), BMW M4 CSL, Corvette Z06 Z07
**Via community:** Viper ACR, McLaren 570S
**Target:** ≥5 entries with known CL·A values

---

## Implementation Priority

| Phase | Item | Effort | Entries Added | Blocked By |
|-------|------|--------|---------------|------------|
| 1A | VIR track reference | 1-2 days + GPS trace | 30-50 (C&D) | GPS trace acquisition |
| 2C | FastestLaps mining for existing tracks | 1 day | 10-20 | Nothing |
| 2A | C&D Lightning Lap transcription | 1 day | 30-50 | VIR track ref (1A) |
| 1B | Laguna Seca track reference | 1-2 days + GPS trace | 20-40 (MT) | GPS trace acquisition |
| 2B | MotorTrend Hot Lap transcription | 1 day | 20-30 | Laguna ref (1B) |
| 1C | Road Atlanta track reference | 1-2 days + GPS trace | 15-25 | GPS trace acquisition |
| 3A | Own telemetry validation | 2-4 weeks | 5-10 (per-corner) | User outreach |
| 4A | OptimumLap cross-validation | 1 day/track | N/A (cross-val) | OptimumLap download |
| 2D | Grassroots Motorsports | 1 day | 5-10 | Track refs for their venues |
| 1D | COTA track reference | 1-2 days + GPS trace | 10-15 | GPS trace acquisition |

### Quick Win (No New Track Reference Needed)

**Phase 2C — FastestLaps.com mining** can start immediately for Barber, AMP, and Roebling. Expected: 10-20 new entries that fill category gaps (especially FWD, street, AWD) with zero infrastructure work.

### Highest-ROI Investment

**Phase 1A (VIR) + Phase 2A (C&D)** together add 30-50 entries of the highest quality data available anywhere, fix all major imbalance gaps, and give us professional-driver baseline data. This is the single highest-value investment in validation quality.

---

## Validation Script Changes Needed

1. **Add `source_quality` column** to `data/realworld_comparison.csv` and script
2. **Add `driver_level` column** — segment analysis by pro vs amateur
3. **Per-driver-level acceptance criteria:**
   - Pro: expect ratio 0.95-1.00 (they extract ~95-98% of physics limit)
   - Advanced club: expect ratio 0.85-0.97
   - Unknown: current criteria (0.60-1.05)
4. **Add per-source breakdown** to validation output (are C&D entries systematically different from community entries?)
5. **Bootstrap CIs per segment** — already recommended in methodology review, becomes meaningful at n>50

---

## Success Criteria

| Metric | Current (n=42) | After Phase 1+2 (n=100+) |
|--------|:---:|:---:|
| Entries | 42 | ≥100 |
| Tracks | 3 | ≥5 |
| Mean ratio 95% CI width | ±0.012 | ±0.006 |
| AWD entries | 0 | ≥5 |
| FWD entries | 4 | ≥10 |
| Street tire entries | 2 | ≥8 |
| Professional driver entries | 0 | ≥20 |
| Per-corner validated sessions | 0 | ≥5 |
| Cross-solver validated | No | Yes (OptimumLap) |
