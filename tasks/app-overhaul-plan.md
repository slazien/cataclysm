# Cataclysm App Overhaul Plan

*Unified plan synthesizing the literature review (60+ sources), killer features research, competitive UX analysis, social features design, and current architecture into a single actionable roadmap.*

*March 2026 — Reconciled with social features P0-P3 implementation plans.*

---

## Table of Contents

1. [Strategic Vision](#1-strategic-vision)
2. [Phase 1: AI Coaching Revolution](#2-phase-1-ai-coaching-revolution)
3. [Phase 2: Knowledge Base Expansion](#3-phase-2-knowledge-base-expansion)
4. [Phase 3: New Visualizations & Features](#4-phase-3-new-visualizations--features)
5. [Phase 4: UX Overhaul](#5-phase-4-ux-overhaul)
6. [Phase 5: Social & Viral Features](#6-phase-5-social--viral-features)
7. [Phase 6: Advanced Analytics](#7-phase-6-advanced-analytics)
8. [Implementation Sequence](#8-implementation-sequence)
9. [Metrics & Success Criteria](#9-metrics--success-criteria)

---

## 1. Strategic Vision

### The Core Insight

Every research source converges on one truth: **interpretation is the product, not visualization**. Garmin Catalyst succeeded by eliminating squiggly lines. Track Titan raised $5M by translating telemetry into coaching flows. Blayze proved $8/session async coaching is accepted. The pattern is clear.

Cataclysm already has the hardest pieces: distance-domain telemetry processing, auto corner detection, per-corner KPIs, and LLM-powered coaching. The overhaul focuses on making these capabilities **revolutionary in delivery** — not just correct in analysis.

### Three Pillars

1. **Coach, Don't Report** — Every screen answers "what should I do differently?" before "what happened"
2. **Show Results** — Prove improvement over time with quantified evidence
3. **Share Everything** — Every insight becomes shareable social content

### Competitive Positioning

No product combines real-world track data + AI coaching + web-based accessibility. Every competitor is missing at least one pillar. Cataclysm fills the exact intersection of three unserved gaps.

---

## 2. Phase 1: AI Coaching Revolution

*Transform coaching from "report generation" to "intelligent driving coach."*

### 2.1 Adopt the Guidance Hypothesis

**Research basis:** Multiple motor learning papers (PMC1780106, PMC7371850) confirm that too much feedback hurts skill learning. Ross Bentley's "2 priorities per session" rule is scientifically validated.

**Current state:** `coaching.py` generates coaching for every corner. The coaching report can be overwhelming.

**Changes:**

#### A. Priority Limiter (`coaching.py`)
- Cap coaching to **3 actionable priorities per session** in the summary prompt
- Rank by estimated time gain (already computed in `gains.py`)
- The detailed corner-by-corner analysis stays available but is secondary
- Add to system prompt: "Identify the THREE corners with the largest improvement opportunity. For each, provide ONE specific actionable change."

#### B. Staged Coaching Tone (`coaching.py` + `kb_selector.py`)
Map coaching style to Fitts-Posner motor learning stages:

| Skill Level | Stage | Coaching Style | Example |
|------------|-------|---------------|---------|
| Novice | Cognitive | Directive with landmarks | "Brake at the 3-board marker for Turn 5" |
| Intermediate | Associative | Consistency + technique | "Your T5 brake point varied by 15m — aim for the 100m board every lap" |
| Advanced | Autonomous | Quantified comparison | "T5 entry speed: 62mph vs 64mph PR. Trail braking 0.3s shorter than your best lap." |

**Implementation:** Add `SKILL_TONE_PROMPTS` dict in `coaching.py` keyed by skill level. Inject into system prompt alongside KB snippets.

#### C. OIS Coaching Format
Every coaching insight follows Observation → Impact → Suggestion:

```
Observation: "You braked 12m early into Turn 5 compared to your best lap"
Impact: "This cost approximately 0.3 seconds per lap"
Suggestion: "Try braking at the 2-board marker instead of before the 3-board"
```

**Implementation:** Add OIS format instruction to `COACHING_SYSTEM_PROMPT` in `driving_physics.py`. Require the LLM to structure every recommendation in this format.

#### D. Positive Framing First
Research (Lappi 2018) and competitive analysis (Garmin Catalyst, Blayze) show leading with positives improves learning outcomes.

**Implementation:** Add to system prompt: "Lead with what the driver does well (2-3 specific strengths) before identifying improvement areas. Ratio should be approximately 60% positive / 40% improvement."

#### E. Corner Speed Sensitivity Context
Ross Bentley's simulation: 1 mph more through a corner ≈ 0.5s/lap. This makes advice concrete.

**Implementation:** Add to `DRIVING_PHYSICS_REFERENCE`: corner speed sensitivity data. When coaching mentions carrying more speed, include estimated lap time impact: "Carrying 2 more mph through Turn 5 could save approximately 0.1s at this corner alone."

### 2.2 Reflective Questions

**Research basis:** Lappi 2018 (12 deliberate practice procedures), Ziv 2023 (embodied cognition), Inner Speed Secrets (conscious vs. subconscious processing).

**Implementation:** Add to coaching prompt: "End with ONE reflective question that helps the driver develop self-awareness. Example: 'What did you feel through the steering at the apex of Turn 5?' or 'Were you aware of how much brake pressure you were using into Turn 3?'"

### 2.3 Stagnation Detection

**Research basis:** Gerrard's *Optimum Drive* (plateau-breaking), competitive analysis (no tool does this).

**Implementation:**
- In `gains.py` or new `stagnation.py`: compare last 3 sessions at the same track
- If best lap time improvement < 0.3s across 3+ sessions: trigger stagnation coaching
- Coaching prompt variant: "The driver has plateaued at [time] for [N] sessions. Their per-corner times for the last [N] sessions are: [corner-level data]. Identify corners where times have NOT improved while others have. For each stagnant corner, describe the measurable telemetry pattern (brake point, min speed, throttle application point) and how it differs from the driver's own best performance at that corner. Do NOT prescribe physical technique changes — only surface the data patterns the driver should investigate."
- **Key constraint:** The AI must never fabricate coaching interventions (e.g., "try trail braking deeper") because GPS telemetry cannot observe what the driver is physically doing. It can only compare the driver's current data against their own historical best and highlight where the numbers diverge. This aligns with data honesty guardrails 9-11.

---

## 3. Phase 2: Knowledge Base Expansion

*Expand from 20 KB snippets to 50+ with deeper physics and new coaching domains.*

### 3.1 New KB Snippet Categories

**Current state:** `kb_selector.py` has 20 snippets from *Going Faster!* only. Pattern detection is limited to 7 triggers.

**New categories to add:**

#### A. Load Transfer Quantification (from literature review §8)
```python
"LT.1": (
    "Load transfer under braking: at 1g braking in a typical 3000lb track car, "
    "approximately 625 lbs transfers to the front tires — the front carries 71% of "
    "total vehicle weight. This is why front tire grip increases dramatically under "
    "braking, enabling trail braking to tighten your line."
),
"LT.2": (
    "Load transfer in cornering: at 1g lateral, approximately 1000 lbs transfers to "
    "the outside tires — the outside tires carry 83% of total weight. The outside-front "
    "tire does most of the work. This is why smooth weight transfer matters — abrupt "
    "transitions cause momentary grip loss as tires adjust."
),
```

#### B. Brake Trace Pattern Recognition (from literature review §8)
```python
"BR.1": (
    "Optimal brake trace has 4 phases: (1) rapid initial application (0.1-0.2s), "
    "(2) peak maintenance near threshold, (3) progressive release as speed drops, "
    "(4) trail braking at 5-10% pressure into the corner. Common problems: 'staircase' "
    "pattern (fear of lockup), plateau too low (not reaching max decel), abrupt release "
    "(no trail braking, causes weight shift instability)."
),
```

#### C. Survival Reaction Detection (from Keith Code, literature review §9)
```python
"SR.1": (
    "Throttle lift mid-corner is the most dangerous survival reaction. If speed through "
    "a corner feels scary, the instinct is to lift — but this transfers weight forward, "
    "unloads the rear, and can cause snap oversteer. A small, deliberate breathe is safe; "
    "an abrupt panic lift is not. If you notice yourself lifting, the root issue is usually "
    "entering too fast. Address it at the brake point, not mid-corner."
),
"SR.2": (
    "The $10 attention budget: you have limited mental bandwidth. If $8 goes to "
    "fear and survival reactions, only $2 is available for driving technique. As "
    "corners become automatic through practice, attention frees up for refinement. "
    "Focus on mastering one corner at a time rather than trying to be fast everywhere."
),
```

#### D. Drivetrain-Specific Coaching
```python
"DT.1": (
    "FWD-specific: understeer is the natural limit behavior. Throttle mid-corner "
    "pulls the front tires toward the exit, increasing understeer. Technique: throttle "
    "application should be earlier and more progressive than RWD. Trail braking is the "
    "primary rotation tool since throttle doesn't create oversteer."
),
"DT.2": (
    "RWD-specific: oversteer is the natural limit behavior on throttle. Too much "
    "throttle too early causes the rear to step out. Technique: wait for the car to "
    "rotate, then apply throttle progressively as steering unwinds. The throttle-to- "
    "steering relationship is your primary balance control."
),
"DT.3": (
    "AWD-specific: behaves like FWD at entry (front-biased torque split) and like "
    "RWD at exit (rear receives more torque under acceleration). Technique: can be "
    "more aggressive with entry speed but must manage understeer on initial throttle. "
    "Trail braking window is shorter because AWD rotates less under braking."
),
```

#### E. Wet Weather Knowledge
```python
"WET.1": (
    "Wet line differs from dry line: avoid rubber-laid racing line (it's the most "
    "slippery surface when wet). Drive off-line on rougher pavement for more grip. "
    "Brake points move 50-100m earlier. Steering and throttle inputs must be 30-50% "
    "more gradual. All grip thresholds drop to 40-60% of dry levels."
),
```

#### F. Vision & Mental Focus
```python
"VIS.1": (
    "Look where you want to go, not where you are. Expert drivers show 2x more head "
    "rotation than novices (van Leeuwen 2017). At corner entry, eyes should already be "
    "on the apex. At the apex, eyes should be on the exit. Vision leads the car by "
    "1-2 seconds. If you're looking at the apex when you arrive there, you're late."
),
```

### 3.2 New Pattern Detection Triggers

Add to `_corner_pattern_snippets()` in `kb_selector.py`:

| Pattern | Detection Logic | Snippet |
|---------|----------------|---------|
| Survival reaction (throttle lift) | Sudden speed drop mid-corner (>3mph between apex and exit in GPS data) | SR.1 |
| Low grip utilization | Peak combined G < 0.7g across session | LT.1, LT.2 |
| Session-over-session stagnation | Best lap within 0.5s for 3+ sessions | SR.2, 8.8 |
| Short braking zone | Brake-to-apex distance < 30m | BR.1 (short corner variant) |
| High speed corners (>80mph min) | Aero effects become relevant | New aero snippet |

### 3.3 Corner Classification Enhancement

**Current:** Type I/II/III only (in `driving_physics.py`).

**Add:** Layer Driver61's 6-phase model for per-phase coaching and LowerLaptime's 7 geometric types for coaching template selection.

**Implementation:**
- Add `corner_geometry` field to `Corner` dataclass (or compute from heading change + radius)
- Classify as: esses, hairpin, chicane, double_apex, constant_radius, decreasing_radius, increasing_radius
- Select coaching template based on geometry: hairpins get "get braking done, quick direction change, aggressive throttle" (snippet 10.4). Carousels get "constant-level trail braking" (snippet 10.5).

### 3.4 Token Budget Management

**Current:** MAX_INJECTION_TOKENS = 2000 (~500 words).

**With expansion to 50+ snippets:** Increase to 3000 tokens. The model context is large enough to accommodate this. Add a priority system:
1. Top-3-gain corner snippets (highest priority)
2. Skill-level base snippets
3. Pattern-triggered snippets
4. Remaining budget for supplementary context

### 3.5 Vehicle Specs Database

**Problem:** Load transfer formulas, power-to-weight context, and drivetrain-specific coaching all need actual car specs. Currently `VehicleParams` in `equipment.py` has tire-derived grip limits but no vehicle mass, wheelbase, track width, or CG height. The KB snippets (LT.1, LT.2) hardcode "a typical 3000lb track car" — useless for a 2400lb Miata or a 4200lb M5.

**What feeds from this:**
- **Load transfer quantification** — `ΔW_lat = (W × Ay × h) / t` needs actual W, h, t
- **Braking performance context** — weight affects stopping distance, brake fade onset
- **Power-to-weight coaching** — "your car has 180hp/ton, so corner exit speed matters more than raw power"
- **Drivetrain coaching** — FWD/RWD/AWD already has KB snippets (DT.1-DT.3) but selection is manual
- **Aero relevance** — cars with splitters/wings get aero snippets; NA Miatas don't

**Architecture:**

1. **Curated vehicle database** — `cataclysm/vehicle_db.py`, following the `tire_db.py` pattern. Start with ~40-50 common HPDE cars (Miata NA/NB/NC/ND, Civic Si/Type R, BRZ/86, Corvette C5-C8, M3 E46/F80/G80, Mustang GT/S550, Cayman 987/718, GT3 991/992, S2000, 370Z, WRX STI, etc.). Each entry is a dataclass:

```python
@dataclass
class VehicleSpec:
    """Manufacturer specs for a car model."""
    make: str
    model: str
    generation: str              # "ND" for Miata, "E46" for M3, etc.
    year_range: tuple[int, int]  # (2016, 2025)
    weight_kg: float             # curb weight
    wheelbase_m: float
    track_width_front_m: float
    track_width_rear_m: float
    cg_height_m: float           # estimated — hardest to get, ~0.45-0.55m for sports cars
    weight_dist_front_pct: float # e.g., 52.0 for front-heavy
    drivetrain: str              # "RWD" | "FWD" | "AWD"
    hp: int
    torque_nm: int
    has_aero: bool               # factory splitter/wing (aftermarket = user override)
    notes: str | None = None     # "S-package adds LSD", etc.
```

2. **Data sources** — manufacturer specs cover weight, wheelbase, HP, torque, drivetrain easily. Track width is in spec sheets. CG height is the hard one — use published estimates (typically 0.45-0.55m for sports cars, 0.55-0.65m for sedans/SUVs). Weight distribution from published specs or auto-journalist measurements.

3. **User setup flow** — when creating an equipment profile, user picks their car from a searchable dropdown (make → model → generation). This populates vehicle specs as defaults. User can then override any field for modified cars:
   - Weight: "I stripped 200lbs" → override to 1100kg
   - CG height: "I lowered it 2 inches" → user can adjust
   - Aero: "I added a wing" → toggle has_aero
   - Suspension changes already covered by existing `SuspensionSpec`

4. **Integration into equipment profile** — add a `vehicle` field to `EquipmentProfile`:
```python
@dataclass
class EquipmentProfile:
    id: str
    name: str
    vehicle: VehicleSpec          # NEW — the car itself
    tires: TireSpec               # what's ON the car
    brakes: BrakeSpec | None
    suspension: SuspensionSpec | None
    vehicle_overrides: dict[str, float] = field(default_factory=dict)  # user mods
    notes: str | None = None
```

5. **Integration into coaching pipeline** — `equipment_to_vehicle_params()` gets actual weight and dimensions. Load transfer KB snippets become dynamic:
```python
# Instead of hardcoded "3000lb car":
f"Load transfer under braking at 1g: {delta_w_front:.0f} lbs transfers to the front tires — "
f"the front carries {front_pct:.0f}% of total weight. "
f"(Computed for your {vehicle.make} {vehicle.model} at {vehicle.weight_kg:.0f}kg)"
```

6. **Drivetrain auto-selection** — DT.1/DT.2/DT.3 snippets get selected automatically based on `vehicle.drivetrain` instead of requiring manual specification.

**Scope control:** Start with the curated DB + dropdown + coaching integration. Do NOT build: gear ratio tables, engine dyno curves, or suspension geometry calculators. Those are future scope if the vehicle DB proves valuable.

**Effort:** ~3 days (1 day DB + dataclass, 1 day frontend dropdown + profile integration, 1 day coaching pipeline integration + tests)

---

## 4. Phase 3: New Visualizations & Features

*Add the highest-impact visualizations identified in the killer features research.*

### 4.1 Mini-Sector Gain/Loss Map (Killer Feature #4)

**What:** Divide track into 10-20 equal-distance sectors. Color each on track map: green (faster than avg), purple (personal best), yellow/red (slower). Show gain/loss bar per sector.

**Why:** F1 broadcasts prove this is the most intuitive visualization. Answers "where am I slow?" in 2 seconds. No consumer tool does this.

**Implementation:**
- Backend: `mini_sectors.py` — divide distance domain into N equal segments, compute time per segment per lap
- Frontend: Color track map segments. Add delta bar chart below map.
- **Already exists conceptually:** Track is resampled in distance domain. D3 track map component exists. This is mainly frontend work with a thin backend computation.

**Complexity:** LOW — ~2 days backend, ~3 days frontend.

### 4.2 Time Gained per Corner — Strokes Gained (Killer Feature #2)

**What:** Golf's Strokes Gained applied to motorsport. Rank corners by "where you're leaving the most time."

**Why:** Arccos Golf (500M shot database) proves this transforms how amateurs improve. No motorsport tool implements this.

**Implementation:**
- Backend: Already computed in `gains.py` (ConsistencyGain has per-segment gains). Surface the data more prominently.
- Frontend: New "Time Gained" card at session summary level. Corner ranking by time opportunity. Simple bar chart: `gain_s` per corner, sorted descending.
- **Key UX:** "You're leaving 0.4s at Turn 5" is infinitely more actionable than a speed trace.

**Complexity:** LOW — The math already exists. This is primarily a frontend presentation change.

### 4.3 G-G Diagram with Utilization Score (Literature Review §12 Priority 3)

**What:** Scatter plot of lateral G vs. longitudinal G for each lap. Overlay the theoretical traction circle. Score = area used / area available.

**Why:** "You're using 75% of available grip through T3" is immediately actionable. Three patterns to detect: poor trail braking (gap between braking and cornering quadrants), insufficient entry speed (dots inside the circle), abrupt transitions (spikes).

**Implementation:**
- Backend: `gg_diagram.py` — compute per-sample lat_g and long_g from GPS data (already have speed + heading). Calculate utilization as area of convex hull / area of max-g circle.
- Frontend: D3 scatter plot with overlaid reference circle. Per-corner filtering. Utilization percentage as a headline number.

**Complexity:** MEDIUM — needs new backend computation + new D3 chart component.

### 4.4 Brake Fade & Tire Degradation Detection (Killer Feature #3)

**What:** Track per-corner metrics across all laps. Detect: declining peak brake G (brake fade), declining corner speed + increasing brake distance (tire degradation).

**Why:** No consumer tool does this automatically. Safety-relevant and immediately actionable.

**Implementation:**
- Backend: `degradation.py` — for each corner, compute linear regression of (lap_number → peak_brake_g) and (lap_number → min_speed). Flag if slope exceeds threshold.
- Frontend: Trend line on existing per-corner charts. Alert card: "Brake fade detected at Turn 5 starting lap 8 — peak braking dropped from 1.1g to 0.8g."

**Complexity:** MEDIUM — new backend module + UI alerts.

### 4.5 Voice-Narrated Session Summary (Killer Feature #5)

**What:** Press play and hear the AI coaching report read aloud.

**Why:** Web Speech API is free, zero cost. trophi.ai's "Mansell AI" sets user expectations. ACM study (2025) found conversational AI coaching rated more useful than dashboards.

**Implementation:**
- Frontend only: Wire existing coaching report text to `SpeechSynthesis` API (~10 lines of JS).
- Add a "Listen" button to the coaching report card.

**Complexity:** LOW — ~1 day.

### 4.6 Animated Lap Replay (Killer Feature #15)

**What:** D3.js dot tracing the racing line with synchronized speed gauge and throttle/brake bars.

**Implementation:**
- Frontend: Animate a dot along the track map path at time-proportional speed. Sync with speed/G readouts.
- Export via MediaRecorder API (canvas recording to MP4 for sharing).

**Complexity:** MEDIUM-HIGH — ~5 days.

---

## 5. Phase 4: UX Overhaul

*Restructure the experience around progressive disclosure and persona-adaptive UI.*

### 5.1 Progressive Disclosure (Exactly 2 Levels)

**Research basis:** UX research confirms 2-level progressive disclosure reduces error rates by 89% and cognitive load by 40%.

#### Level 1 — Session Summary (Default View)

When a session loads, show:

```
┌─────────────────────────────────────────────────────┐
│  SESSION SCORE: 78/100          Best: 1:45.2 (-0.8s)│
│  ─────────────────────────────────────────────────── │
│  TOP 3 PRIORITIES                                    │
│  1. Turn 5: Brake 12m earlier → save ~0.3s          │
│  2. Turn 3: Carry 2mph more through apex → save ~0.2s│
│  3. Esses: Smoother steering → save ~0.15s           │
│  ─────────────────────────────────────────────────── │
│  [Track Map - mini-sector colored]  [Lap Time Chart] │
│  ─────────────────────────────────────────────────── │
│  Consistency: 82%  |  Best Corner: T7  |  Laps: 18  │
│  ─────────────────────────────────────────────────── │
│  [↗ Share Card]  [🔗 Challenge a Friend]             │
└─────────────────────────────────────────────────────┘
```

#### Level 2 — Detailed Analysis (Drill-In)

Click any corner or "Deep Dive" to see:
- Speed trace with multi-lap overlay
- Delta-T visualization
- Corner-by-corner expandable cards (grade + KPIs)
- Full AI coaching report
- G-G diagram
- Consistency analysis
- Corner leaderboard (per-corner, multi-category)

### 5.2 Session Score (0-100)

**New metric** — a composite score that gives an instant answer to "how was my session?"

**Calculation:**
- Consistency component (40%): How close were your laps to your best? `1 - (std_dev / mean_laptime)`
- Improvement component (30%): Did you improve vs. previous session at this track?
- Technique component (30%): Aggregate of per-corner grades (brake point accuracy, trail braking, throttle commit, line accuracy)

**Implementation:** New `session_score.py` module. Displayed prominently as a large number with color (green >80, yellow 60-80, red <60). Also shown as a badge in the TopBar contextual bar (see Social P1 Task 7).

**Social integration:** Session score IS the social identity — it appears on share cards, in leaderboards, and as the hero stat in the TopBar.

### 5.3 Persona-Adaptive UI

The skill level selector should meaningfully change what the user sees:

| Element | Novice | Intermediate | Advanced |
|---------|--------|-------------|----------|
| Session summary | Score + "You improved!" | Score + top 3 corners | Score + full KPI table |
| Track map | Speed-colored | Mini-sector gain/loss | G-utilization overlay |
| Coaching format | Plain English directives | Technique + data context | Quantified targets + trends |
| Deep dive | Simplified (speed trace only) | Speed + brake + throttle | All channels + g-g diagram |
| Visible charts | 3-4 key charts | 6-8 charts | Everything |

**Implementation:** Use skill level from user settings to conditionally render components. Not hiding data — providing appropriate defaults with ability to expand.

### 5.4 "5-Minute Pit Lane Debrief" View (Killer Feature #6)

**What:** Mobile-optimized single-screen summary for between sessions at the track.

**Implementation:**
- New `/debrief` view or a "Pit Debrief" toggle on the session page
- Contains: hero card (best lap + delta), top 3 corners losing time, consistency %, ONE coaching tip for next session
- Auto-generated on CSV upload
- Optimized for phone screen (stacked cards, large text, swipeable)

**Complexity:** LOW-MEDIUM — curate existing data into a new responsive layout.

### 5.5 Insight Annotations on Charts

**Research basis:** "Never show a chart without explaining what it means" (competitive UX analysis).

**Implementation:**
- Every chart panel gets a 1-line AI-generated insight above it
- Speed trace: "Your minimum speed through T5 varied by 4mph — consistency here would save ~0.2s"
- Lap times: "Your pace dropped after lap 12 — possible tire degradation or fatigue"
- These are generated as part of the coaching pipeline, not separate API calls

---

## 6. Phase 5: Social & Viral Features

*Build the distribution mechanics that turn users into ambassadors.*

**Architecture principle:** No dedicated "Social" tab. Social features are woven into existing views as contextual actions (see design doc: `docs/plans/2026-03-02-social-features-design.md`).

**Detailed implementation plans:** This phase is broken into priority tiers with granular, file-level task specs in separate documents:
- **P0 + P1 tasks:** `docs/plans/2026-03-02-social-features-p0p1-implementation.md`
- **P2 + P3 tasks:** `docs/plans/2026-03-02-social-features-p2p3-implementation.md`

### 6.0 Fix Orphaned Social Features (P0 — Do First)

Social features already exist in the codebase but are unreachable. These P0 fixes take <1 day combined and unblock everything else.

| Task | What | Why Orphaned |
|------|------|-------------|
| **P0-1** Move share buttons to SessionReportHeader | `ShareButton` + `ShareSessionDialog` → `SessionReportHeader.tsx` | Living on unreachable `SessionDashboard` (ViewRouter routes to `SessionReport` instead) |
| **P0-2** Unhide achievements/wrapped on mobile | Remove `hidden sm:flex` from TopBar icon wrapper | CSS class hides on <640px screens |
| **P0-3** Wire CornerLeaderboard into Deep Dive | Import `CornerLeaderboard` into `CornerDetailPanel.tsx` | Component exists (104 lines + backend) but is never imported |

**Spec:** `docs/plans/2026-03-02-social-features-p0p1-implementation.md` Tasks 1-3.

### 6.1 Shareable Session Cards — Identity-Framed (P1)

**What:** Upgrade existing share card renderer with identity framing. Add hero stat ("Improved 1.3s"), consistency label, corners-mastered count. "Top 5% braking at Barber" > "Braking distance: 47m."

**Why:** Spotify Wrapped proved 500M+ shares. Every share is a free billboard. Identity framing makes cards worth sharing — data reporting does not.

**Implementation:** Enhance `ShareCardData` interface with `heroStat`, `consistencyLabel`, `cornersGraded`. Compute in `useShareCard.ts`. Update canvas renderer.

**Spec:** `docs/plans/2026-03-02-social-features-p0p1-implementation.md` Task 4.

### 6.2 "Challenge a Friend" Comparison Flow (P1)

**What:** Refine comparison dialog from technical "Share for Comparison" to viral "Challenge a Friend" flow. Add Web Share API support. Framing: "I just ran Barber — upload your session and let's see who's faster!"

**Three-layer comparison view (P2):**
1. **Tale of the Tape** — side-by-side hero stats with one-sentence AI summary
2. **Corner Scorecard** — per-corner table, tap to expand
3. **Delta Drill-Down** — speed trace overlay + AI coaching note for selected corner

**Spec:** P1 dialog refinement in `p0p1-implementation.md` Task 5. P2 three-layer view in `p2p3-implementation.md` Task 10.

### 6.3 Multi-Category Corner Leaderboards (P1)

**What:** Expand corner leaderboard from single metric (sector time) to four categories with fun titles:

| Category | Metric | Sort | Title |
|----------|--------|------|-------|
| Sector time | `sector_time_s` | ASC (lower = better) | Corner King |
| Min speed | `min_speed_mps` | DESC (higher = better) | Apex Predator |
| Brake point | `brake_point_m` | ASC (later = closer = better) | Late Braker |
| Consistency | `consistency_cv` | ASC (lower CV = better) | Smooth Operator |

**Implementation:** Add `brake_point_m` + `consistency_cv` columns to `CornerRecord` DB model. Add `category` query param to leaderboard endpoint. Add category tabs to `CornerLeaderboard.tsx`. Add leaderboard position sharing via Web Share API.

**Spec:** `docs/plans/2026-03-02-social-features-p0p1-implementation.md` Tasks 8-9.

### 6.4 New Achievement Card in Session Report (P1)

**What:** Show newly unlocked achievements inline in session report footer. "New Achievement: Consistency King" with tier icon and "View All Badges" link.

**Spec:** `docs/plans/2026-03-02-social-features-p0p1-implementation.md` Task 6.

### 6.5 Session Score in TopBar (P1)

**What:** Display session score as a colored badge next to the track name in the TopBar contextual bar. Requires session score computation (Phase 4, §5.2) to be complete first.

**Spec:** `docs/plans/2026-03-02-social-features-p0p1-implementation.md` Task 7.

### 6.6 Progress Rate Leaderboard (P2)

**What:** New endpoint computing improvement rate across sessions for a given track. For each driver: linear regression of best lap times across sessions → seconds improved per session. Show your rank and percentile: "You: #2 of 12 — Top 17%."

**Why:** Rewards improvement, not just raw speed. Encourages return visits. "I'm in the top 25% of improvers at Barber" is identity-defining.

**Implementation:** New `backend/api/routers/progress.py` endpoint + `ProgressLeaderboard.tsx` component in Progress tab.

**Spec:** `docs/plans/2026-03-02-social-features-p2p3-implementation.md` Tasks 11-12.

### 6.7 Track-Level Leaderboard Summary (P2)

**What:** Compact card in Report tab showing user's standing across all leaderboard dimensions: best lap rank, session score rank, progress rank, consistency rank. Plus which corners you hold the crown on.

**Spec:** `docs/plans/2026-03-02-social-features-p2p3-implementation.md` Task 13.

### 6.8 Tap-to-Compare in Leaderboards (P2)

**What:** Click another driver's leaderboard entry → mini comparison card showing their corner KPIs vs yours. Side-by-side with color-coded deltas.

**Spec:** `docs/plans/2026-03-02-social-features-p2p3-implementation.md` Task 14.

### 6.9 Achievements in Progress Tab + Wrapped Banner (P2)

**What:** Inline achievements section in Progress tab (latest 3-4 badges). Conditional "Season Wrapped" banner during October-December when user has 3+ sessions.

**Spec:** `docs/plans/2026-03-02-social-features-p2p3-implementation.md` Tasks 15-16.

### 6.10 Corner King Badge on Track Map (P2)

**What:** Crown icon (👑) on track map corner markers where the current user holds the leaderboard top spot. Visual reward for dominance.

**Spec:** `docs/plans/2026-03-02-social-features-p2p3-implementation.md` Task 17.

### 6.11 Season Wrapped (Killer Feature #8)

**What:** Annual recap: total laps, miles, tracks visited, best improvement, corners mastered, "driving personality." 5-6 slide storytelling flow. Shareable card. ONE TAP share.

**Implementation:** Aggregate multi-session data. Generate cards via Canvas. Build for end of track season (October-November).

**Complexity:** MEDIUM — ~3 days.

### 6.12 Future Social Infrastructure (P3 — Deferred)

These require user density to justify. Architecture notes in `p2p3-implementation.md` Tasks 18-22:

| Feature | Prerequisite | Notes |
|---------|-------------|-------|
| G-Force King leaderboard | GPS-derived lateral G (noisy, needs smoothing) | New `peak_lateral_g` column |
| Duolingo-style skill-bracketed leagues | 30+ active users per track/month | Weekly promotion/demotion |
| Track day groups | Lightweight entity: track + date + invite code | Perfect for "March 15 Barber" |
| Corner tips / GeoComments | User-submitted tips anchored to corners | Moderation needed |
| Instructor dashboard + HPDE org clubs | Instructor role, student linking, org branding | B2B distribution wedge |

---

## 7. Phase 6: Advanced Analytics

*Deeper analysis for intermediate-to-advanced drivers who want the full picture.*

### 7.1 Multi-Session Progress Dashboard Enhancement

**Current:** Progress view exists with trend charts.

**Enhancements:**
- Per-corner improvement tracking across sessions
- Milestone markers: "You broke 1:50 for the first time on Feb 15"
- Stagnation alerts: "T5 has been your #1 time loss for 3 sessions — focus here next"
- Rolling average trend lines (not just raw lap times)

### 7.2 Skill Radar Chart (Killer Feature #10)

**What:** Four dimensions tracked over time:
1. Braking (brake point accuracy + peak brake G utilization)
2. Trail Braking (brake-turn overlap quality)
3. Throttle Application (throttle commit distance + progressiveness)
4. Line Accuracy (apex hit rate + consistency)

**Implementation:** D3 radar chart. Computed from existing per-corner KPIs. Show evolution across sessions.

### 7.3 Corner Type-Specific Coaching Templates

Based on the 7-type geometric classification (LowerLaptime):

| Corner Type | Coaching Focus | Key Metric |
|------------|---------------|------------|
| Hairpin | Get braking done early, quick direction change, aggressive throttle | Throttle commit distance |
| Constant radius | Steady-state cornering, consistent speed | Min speed variance |
| Decreasing radius | Progressively tighter, patience on throttle | Late apex accuracy |
| Increasing radius | Early apex possible, progressive throttle | Exit speed |
| Esses/chicane | Minimize steering inputs, flow | Speed trace shape (U vs V) |
| Double apex | Two distinct phases, lift between | Mid-corner speed profile |

**Implementation:** Classify corners by geometry (heading change rate profile). Inject corresponding coaching template as additional context in the LLM prompt.

### 7.4 Optimal Racing Line Comparison

**Current:** `optimal_comparison.py` uses physics-based theoretical comparison.

**Enhancement:** Overlay the driver's actual GPS line on the track map alongside the theoretical optimal (outside-inside-outside). Color-code deviation. "Your line through T5 was 2m wide of the apex — tightening this could save ~0.1s."

---

## 8. Implementation Sequence

### Wave 0: Fix Orphaned Social Features (<1 day)

Quick wins — unblock social features that already exist but are inaccessible.

| # | Task | Spec | Effort |
|---|------|------|--------|
| 0.1 | Move share buttons to SessionReportHeader | P0-1 | 0.5h |
| 0.2 | Unhide achievements/wrapped on mobile | P0-2 | 0.25h |
| 0.3 | Wire CornerLeaderboard into Deep Dive corner detail | P0-3 | 0.5h |

**Spec:** `docs/plans/2026-03-02-social-features-p0p1-implementation.md` Tasks 1-3.
**Outcome:** Users can now see and use share buttons, achievements, and corner leaderboards.

### Wave 1: Coaching Intelligence (2-3 weeks)

| # | Task | Files | Effort |
|---|------|-------|--------|
| 1.1 | Add OIS format + 3-priority limit to coaching prompt | `driving_physics.py`, `coaching.py` | 1 day |
| 1.2 | Add staged coaching tone (skill-level prompts) | `coaching.py` | 1 day |
| 1.3 | Add positive framing + reflective questions to prompt | `driving_physics.py` | 0.5 day |
| 1.4 | Add corner speed sensitivity data to physics reference | `driving_physics.py` | 0.5 day |
| 1.5 | Expand KB from 20 to 40+ snippets (load transfer, brake traces, survival reactions, drivetrain, wet, vision) | `kb_selector.py` | 2 days |
| 1.6 | Add new pattern detection triggers | `kb_selector.py` | 1 day |
| 1.7 | Implement stagnation detection | New `stagnation.py` or in `gains.py` | 1 day |
| 1.8 | Corner geometry classification | `corner_analysis.py` or new module | 2 days |
| 1.9 | Vehicle specs DB (~40-50 common HPDE cars) | New `vehicle_db.py` | 1 day |
| 1.10 | Vehicle selection UI + equipment profile integration | Frontend + backend | 1 day |
| 1.11 | Dynamic load transfer + drivetrain KB snippet integration | `kb_selector.py`, `coaching.py` | 1 day |
| 1.12 | Tests for all new modules | `tests/` | 2 days |
| 1.13 | Validate coaching quality (sample prompts, check output) | Manual + validator | 1 day |

**Outcome:** Coaching goes from "generic report" to "intelligent, prioritized, skill-adapted coach."

### Wave 2: Key Visualizations (2-3 weeks)

| # | Task | Files | Effort |
|---|------|-------|--------|
| 2.1 | Mini-sector computation backend | New `mini_sectors.py` | 1 day |
| 2.2 | Mini-sector API endpoint | `backend/` | 0.5 day |
| 2.3 | Mini-sector track map visualization (frontend) | New component | 3 days |
| 2.4 | Time Gained per Corner — surface `gains.py` data prominently | Frontend refactor | 2 days |
| 2.5 | Session Score computation | New `session_score.py` | 1 day |
| 2.6 | Session Score API + frontend card | Backend + frontend | 1 day |
| 2.7 | Voice narration (Web Speech API) | Frontend only | 0.5 day |
| 2.8 | G-G diagram computation | New `gg_diagram.py` | 1 day |
| 2.9 | G-G diagram frontend | New D3 component | 2 days |
| 2.10 | Brake fade / tire degradation detection | New `degradation.py` | 1.5 days |
| 2.11 | Degradation alerts frontend | Frontend cards/alerts | 1 day |
| 2.12 | Tests | `tests/` | 2 days |

**Dependency note:** Tasks 2.5-2.6 (session score) are prerequisites for Social P1 Task 7 (score in TopBar) and share card identity framing.

**Outcome:** Visual experience goes from "telemetry charts" to "F1 broadcast-quality insight."

### Wave 3: UX Overhaul (2-3 weeks)

| # | Task | Files | Effort |
|---|------|-------|--------|
| 3.1 | Redesign session page to Level 1/Level 2 progressive disclosure | Major frontend refactor | 5 days |
| 3.2 | Session Summary hero card (score + best lap + 3 priorities) | New component | 2 days |
| 3.3 | Insight annotations on all chart panels | Coaching pipeline + frontend | 2 days |
| 3.4 | Persona-adaptive rendering (skill level controls visible complexity) | Frontend conditional logic | 2 days |
| 3.5 | Pit Lane Debrief mobile view | New responsive layout | 2 days |
| 3.6 | QA testing (desktop + mobile device emulation) | Playwright | 2 days |

**Outcome:** The app feels like it was designed by a driving instructor, not a data engineer.

### Wave 4: Social P1 Features (1-2 weeks)

| # | Task | Spec | Effort |
|---|------|------|--------|
| 4.1 | Upgrade share card to identity-framed design | P1 Task 4 | 1 day |
| 4.2 | Refine comparison dialog → "Challenge a Friend" + Web Share | P1 Task 5 | 0.5 day |
| 4.3 | New achievement card in session report footer | P1 Task 6 | 0.5 day |
| 4.4 | Session score badge in TopBar contextual bar | P1 Task 7 | 0.25 day |
| 4.5 | Expand leaderboard to multi-category (Late Braker, Smooth Operator) | P1 Task 8 | 2 days |
| 4.6 | Add leaderboard position sharing | P1 Task 9 | 0.5 day |
| 4.7 | Animated lap replay | Phase 3 §4.6 | 4 days |

**Spec:** `docs/plans/2026-03-02-social-features-p0p1-implementation.md` Tasks 4-9.
**Outcome:** Every session generates shareable, identity-framed content. Users become ambassadors.

### Wave 5: Social P2 Features (2-3 weeks)

| # | Task | Spec | Effort |
|---|------|------|--------|
| 5.1 | Three-layer comparison view (Tale of the Tape → Scorecard → Delta) | P2 Task 10 | 4 days |
| 5.2 | Progress rate leaderboard backend | P2 Task 11 | 2 days |
| 5.3 | Progress rate leaderboard frontend | P2 Task 12 | 2 days |
| 5.4 | Track-level leaderboard summary card | P2 Task 13 | 1 day |
| 5.5 | Tap-to-compare in leaderboards | P2 Task 14 | 1 day |
| 5.6 | Achievements section in Progress tab | P2 Task 15 | 0.5 day |
| 5.7 | Season Wrapped banner in Progress tab | P2 Task 16 | 0.5 day |
| 5.8 | Corner King badge on track map | P2 Task 17 | 0.5 day |

**Spec:** `docs/plans/2026-03-02-social-features-p2p3-implementation.md` Tasks 10-17.
**Outcome:** Full competitive social layer — leaderboards, comparisons, crowns, progress ranking.

### Wave 6: Advanced Analytics (Ongoing)

| # | Task | Effort |
|---|------|--------|
| 6.1 | Multi-session progress dashboard enhancement | 3 days |
| 6.2 | Skill radar chart (backend + D3 component) | 3 days |
| 6.3 | Season Wrapped full generator (5-6 slides, Canvas cards) | 3 days |
| 6.4 | Corner type-specific coaching templates | 2 days |
| 6.5 | Optimal racing line overlay on track map | 3 days |

### Wave 7: Future Social (P3 — When User Density Justifies)

| # | Task | Prerequisite |
|---|------|-------------|
| 7.1 | G-Force King leaderboard | GPS-derived lateral G smoothing |
| 7.2 | Skill-bracketed leagues (Duolingo-style) | 30+ users/track/month |
| 7.3 | Track day groups with invite codes | Basic user base |
| 7.4 | Corner tips / GeoComments | Moderation system |
| 7.5 | Instructor dashboard + HPDE org clubs | Instructor user type, org entity |

**Spec:** `docs/plans/2026-03-02-social-features-p2p3-implementation.md` Tasks 18-22.

---

## 9. Metrics & Success Criteria

### Coaching Quality

| Metric | Current | Target |
|--------|---------|--------|
| Physics accuracy (validator pass rate) | ~95% | >98% |
| Coaching specificity (OIS format adherence) | Not measured | >90% of insights |
| Priorities per session | Unlimited | Capped at 3 |
| Skill-level adaptation | Basic | Full tone + content adaptation |
| KB snippets available | 20 | 50+ |
| Pattern detection triggers | 7 | 15+ |

### User Experience

| Metric | Current | Target |
|--------|---------|--------|
| Upload-to-insight time | ~30s | <15s perceived (skeleton UI) |
| Charts with insight annotations | 0 | All main charts |
| Mobile usability | Basic responsive | Dedicated pit debrief view |
| Progressive disclosure levels | 1 (everything shown) | 2 (summary → detail) |

### Social & Engagement

| Metric | Current | Target |
|--------|---------|--------|
| Share buttons visible | No (orphaned) | Yes (Report header) |
| Leaderboard categories | 1 (sector time) | 4 (Corner King, Apex Predator, Late Braker, Smooth Operator) |
| Corner leaderboard reachable | No (dead code) | Yes (in Deep Dive corner detail) |
| Achievement visibility on mobile | Hidden | Visible |
| Sessions shared | 0 | Track after launch |
| Comparison challenges sent | 0 | Track after launch |
| Leaderboard positions shared | N/A | Track after launch |

---

## Appendix A: Research Sources Informing This Plan

| Source | Key Contribution to Plan |
|--------|------------------------|
| Literature Review (`tasks/coaching-knowledge-literature-review.md`) | 60+ sources: KB expansion content, coaching science, physics quantification |
| Killer Features (`tasks/killer-features.md`) | 15 ranked features with competitive evidence |
| Competitive UX Analysis (`tasks/competitive-ux-analysis.md`) | Persona definitions, competitor weaknesses, UX patterns, design principles |
| Social Features Research (`tasks/social-features-research.md`) | Outward-first social design, identity framing, atomic network theory |
| Social Features Design (`docs/plans/2026-03-02-social-features-design.md`) | No-new-tab architecture, contextual social actions |
| Garmin Catalyst Analysis (`tasks/garmin_catalyst_competitive_analysis.md`) | UX gold standard for HPDE, "3 priorities" validation |
| Lappi 2018 (Frontiers in Psychology) | 12 deliberate practice procedures, coaching stage mapping |
| Guidance Hypothesis (PMC1780106) | Scientific basis for limiting feedback volume |
| Fitts-Posner Motor Learning Model | Skill-level coaching tone framework |
| Ross Bentley's Speed Secrets | "2 priorities per session", corner speed sensitivity (0.5s/mph) |
| Keith Code's Survival Reactions | 7 detectable counterproductive responses |
| Driver61's 6-Phase Corner Model | Per-phase coaching template system |
| LowerLaptime's 7-Type Geometry | Corner classification for coaching template selection |

## Appendix B: Document Map

```
tasks/app-overhaul-plan.md              ← THIS FILE (master roadmap)
  ├── Phase 1-4, 6: Defined here
  └── Phase 5 (Social): References ↓

docs/plans/2026-03-02-social-features-design.md     ← Architecture & design principles
docs/plans/2026-03-02-social-features-p0p1-implementation.md  ← Tasks 1-9 (file-level specs)
docs/plans/2026-03-02-social-features-p2p3-implementation.md  ← Tasks 10-22 (file-level specs)

tasks/coaching-knowledge-literature-review.md  ← Research input (60+ sources)
tasks/killer-features.md                       ← Research input (15 features)
tasks/competitive-ux-analysis.md               ← Research input (market + UX)
tasks/social-features-research.md              ← Research input (social mechanics)
```

---

*Plan authored March 2026. Reconciled with social features P0-P3 implementation plans. Ready for implementation.*
