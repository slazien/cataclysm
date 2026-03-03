# Cataclysm App Overhaul Plan

*Unified plan synthesizing the literature review (60+ sources), killer features research, competitive UX analysis, social features design, and current architecture into a single actionable roadmap.*

*March 2026 — Reconciled with social features P0-P3 implementation plans. Audited against codebase — completed features marked ✅, partial ⚠️, remaining ❌.*

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

**Current state:** `coaching.py` generates coaching for every corner. The prompt includes "Focus on the 2-3 biggest improvements" as a soft guideline, but there's no hard cap.

**Changes:**

#### A. Priority Limiter (`coaching.py`) — ⚠️ PARTIAL (soft guideline exists, needs hard enforcement)
- Enforce a hard cap of **3 actionable priorities per session** in the summary prompt
- Rank by estimated time gain (already computed in `gains.py`)
- The detailed corner-by-corner analysis stays available but is secondary
- Strengthen prompt: "Identify the THREE corners with the largest improvement opportunity. For each, provide ONE specific actionable change."

#### B. Staged Coaching Tone (`coaching.py` + `kb_selector.py`) — ✅ DONE
Already implemented as `_SKILL_PROMPTS` dict with three branches:
- **Novice** (HPDE Group 1-2): 1-2 priorities, no trail braking, encouraging language
- **Intermediate** (HPDE Group 3): Trail braking, brake optimization, consistency focus
- **Advanced** (HPDE Group 4+): Micro-optimization, composite/theoretical analysis

No further work needed.

#### C. OIS Coaching Format — ❌ TODO
Every coaching insight should follow Observation → Impact → Suggestion:

```
Observation: "You braked 12m early into Turn 5 compared to your best lap"
Impact: "This cost approximately 0.3 seconds per lap"
Suggestion: "Experiment with braking closer to the 2-board marker"
```

**Implementation:** Add OIS format instruction to `COACHING_SYSTEM_PROMPT` in `driving_physics.py`. Require the LLM to structure every recommendation in this format. Note: Suggestions must stay grounded in telemetry data — "experiment with X" rather than prescribing physical technique.

#### D. Positive Framing First — ⚠️ PARTIAL (soft instruction exists, needs structuring)
Current prompt says "Be encouraging but honest" and "celebrate what they're doing well" but doesn't enforce leading with positives.

**Implementation:** Strengthen to: "Begin the report with 2-3 specific data-backed strengths (e.g., 'Your T7 consistency was excellent — only 0.1s variance'). Then transition to improvement areas. Ratio: ~60% positive / 40% improvement."

#### E. Corner Speed Sensitivity Context — ❌ TODO
Ross Bentley's generic "1 mph more ≈ 0.5s/lap" varies by track and corner.

**Implementation:** Compute corner-specific speed sensitivity from the driver's own telemetry: simulate "what if min speed was 1mph higher?" by adjusting speed profile and recomputing segment time via the velocity profile solver. This replaces the generic Bentley approximation with a data-grounded, car+track-specific number. Add the computed value to the coaching prompt context per corner.

### 2.2 Reflective Questions — ❌ TODO

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

*Expand from 18 KB snippets to 50+ with deeper physics and new coaching domains.*

### 3.1 New KB Snippet Categories — ❌ TODO

**Current state:** `kb_selector.py` has **18 snippets** from *Going Faster!* only (9 base snippets by skill level + 9 pattern-triggered snippets). Pattern detection has **9 triggers** (not 7 as originally estimated).

**New categories to add:**

#### A. Load Transfer Quantification (from literature review §8)
**Note:** These snippets become **dynamic** once the Vehicle Specs DB (§3.5) is implemented — hardcoded "3000lb car" is replaced with the driver's actual car specs.
```python
# Static fallback (used until vehicle DB is integrated):
"LT.1": (
    "Load transfer under braking: at 1g braking in a typical 3000lb track car, "
    "approximately 625 lbs transfers to the front tires — the front carries 71% of "
    "total vehicle weight. This is why front tire grip increases dramatically under "
    "braking, enabling trail braking to tighten your line."
),
# Dynamic version (with vehicle DB):
# f"Load transfer under braking at 1g: {delta_w_front:.0f} lbs transfers to the front — "
# f"the front carries {front_pct:.0f}% of total weight."
# f"(Computed for your {vehicle.make} {vehicle.model} at {vehicle.weight_kg:.0f}kg)"
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

### 4.1 Mini-Sector Gain/Loss Map (Killer Feature #4) — ✅ DONE

**Fully implemented:**
- Backend: `cataclysm/mini_sectors.py` with `MiniSector` and `MiniSectorLapData` dataclasses, `compute_mini_sectors()` function
- API: `GET /{session_id}/mini-sectors` with configurable `n_sectors` (3-100, default 20)
- Frontend: `MiniSectorMap.tsx` — GPS-projected polylines, color-coded by classification (pb/faster/slower/neutral)
- Hook: `useMiniSectors()` in `useAnalysis.ts`

### 4.2 Time Gained per Corner — Strokes Gained (Killer Feature #2) — ✅ DONE

**Fully implemented:**
- Backend: `cataclysm/gains.py` — three-tier system (ConsistencyGain, CompositeGain, TheoreticalGain) with per-corner time gains
- API: `GET /{session_id}/gains`
- Frontend: `TimeGainedChart.tsx` — bar chart showing top time-gaining corners, sorted by gain descending
- Hook: `useGains()` in `useAnalysis.ts`

### 4.3 G-G Diagram with Utilization Score (Literature Review §12 Priority 3) — ❌ TODO

**What:** Scatter plot of lateral G vs. longitudinal G for each lap. Overlay the reference traction circle. Score = area used / area available.

**Why:** "You're using 75% of available grip through T3" is immediately actionable. Three patterns to detect: poor trail braking (gap between braking and cornering quadrants), insufficient entry speed (dots inside the circle), abrupt transitions (spikes).

**Note:** Lateral and longitudinal G traces already exist in `LinkedChartResponse` (`lateral_g_traces`, `longitudinal_g_traces`), so the raw data is available. What's missing is the G-G scatter visualization and utilization computation.

**Caveat:** GPS-derived G is noisy at 25Hz. Smoothing clips peaks, so utilization scores will read systematically lower than with accelerometer data. Solution: normalize against observed max G (not theoretical traction circle) — measures "how close to YOUR observed limit" rather than a theoretical max. This also avoids needing the tire mu.

**Implementation:**
- Backend: `gg_diagram.py` — compute utilization as convex hull area / observed-max-g circle area. Per-corner filtering.
- Frontend: D3 scatter plot with overlaid reference circle. Per-corner tab. Utilization % as headline number.

**Complexity:** MEDIUM — ~3 days (backend module exists in raw data, needs aggregation + new D3 component).

### 4.4 Brake Fade & Tire Degradation Detection (Killer Feature #3) — ✅ DONE

**Fully implemented:**
- Backend: `cataclysm/degradation.py` — `DegradationEvent` and `DegradationAnalysis` dataclasses, linear regression with R²≥0.5 threshold, severity classification (mild/moderate/severe)
- API: `GET /{session_id}/degradation`
- Frontend: `DegradationAlerts.tsx` — alerts for brake fade and tire degradation
- Hook: `useDegradation()` in `useAnalysis.ts`

### 4.5 Voice-Narrated Session Summary (Killer Feature #5) — ✅ DONE

**Fully implemented:**
- Frontend: `useSpeechSynthesis.ts` — Web Speech API integration with speak/pause/stop controls
- Used in: `ReportSummary.tsx` — narrates coaching report text aloud
- Rate, pitch, volume configurable

### 4.6 Animated Lap Replay (Killer Feature #15) — ✅ DONE

**Fully implemented:**
- Frontend: `LapReplay.tsx` — animates car position along track with synchronized speed gauge and G-force trail
- Sub-components: `ReplayControls.tsx` (play/pause/speed), `ReplayTrackMap.tsx` (GPS viz), `GForceDisplay.tsx`
- Hook: `useReplay()` — manages playback state, current index, timestamp sync
- Available as a Deep Dive sub-tab (gated to intermediate+ skill level)

**Remaining:** MediaRecorder API export for sharing (canvas recording to MP4) — not yet implemented.

---

## 5. Phase 4: UX Overhaul

*Restructure the experience around progressive disclosure and persona-adaptive UI.*

### 5.1 Progressive Disclosure — ✅ DONE (tab-based, 4 views)

**Current implementation:** The app uses a tab-based progressive disclosure model with four views:
1. **Report** — AI coaching summary hero, priority corners, corner grades, patterns/drills
2. **Deep Dive** — Speed, Corner, Sectors (intermediate+), Replay (intermediate+) sub-tabs
3. **Progress** — Trend analysis across sessions
4. **Debrief** — Mobile-optimized pit lane summary

This differs from a strict 2-level expand/collapse pattern but achieves the same goal — summary first (Report tab), detail on demand (Deep Dive tab). The dashboard (`SessionDashboard`) already has a hero metrics row (session score, best lap, top 3 avg, session avg) + grid layout (priorities, track map, time gained, skill radar, lap times).

**Remaining opportunity:** The Report → Deep Dive transition could be made more seamless (e.g., clicking a corner in the Report could auto-navigate to Deep Dive with that corner selected).

### 5.2 Session Score (0-100) — ✅ DONE

**Fully implemented:**
- Frontend: `SessionScore.tsx` — circular progress ring with animated counter (800ms ease-out)
- Calculation (in `SessionDashboard.tsx`):
  - Consistency (40%): lap-to-lap performance variance
  - Pace (30%): best lap vs ideal lap time
  - Corner Grades (30%): average grade across all corners
- Color coding: green ≥80, amber 60-80, red <60
- Subtitle: "Strong session" / "Room to improve" / "Focus on fundamentals"
- Displayed as hero metric in dashboard

**Note:** The plan's original "Technique component" mentioned "line accuracy" — the current implementation uses corner grades (A/B/C/D/F) instead, which is better grounded since it's based on telemetry-observable metrics (brake point, min speed, throttle commit) rather than GPS lateral position.

### 5.3 Persona-Adaptive UI — ✅ DONE (comprehensive)

**Fully implemented** via `useSkillLevel.ts` with 13 feature toggles:

| Feature | Novice | Intermediate | Advanced |
|---------|--------|-------------|----------|
| Sectors Tab | No | Yes | Yes |
| Custom Tab | No | No | Yes |
| Replay Tab | No | Yes | Yes |
| Heatmap | No | Yes | Yes |
| Boxplot | No | Yes | Yes |
| Absolute Distances | No | Yes | Yes |
| Relative Distances | Yes | Yes | No |
| Grade Explanations | Yes | No | No |
| Guided Prompts | Yes | Yes | No |
| Raw Data Table | No | No | Yes |
| Keyboard Overlay | No | No | Yes |
| Delta Breakdown | No | Yes | Yes |
| G-Force Analysis | No | No | Yes |

Persisted in Zustand store via persist middleware. Default: Intermediate.

### 5.4 "5-Minute Pit Lane Debrief" View (Killer Feature #6) — ✅ DONE

**Fully implemented:**
- `PitLaneDebrief.tsx` with hero card (pit board style), time-loss corners analysis, quick tips, consistency metrics
- Sub-components: `DebriefHeroCard.tsx`, `TimeLossCorners.tsx`, `QuickTip.tsx`
- Available as a tab in both desktop TopBar and mobile bottom nav
- Mobile-optimized layout

### 5.5 Insight Annotations on Charts — ⚠️ PARTIAL

**Current state:** `TopPriorities.tsx` shows AI coaching insights prominently on the dashboard. Some charts have annotation infrastructure but it's sparse and feature-flagged. Corner grade explanations exist (gated to novice skill level).

**Remaining:**
- Expand to all major charts (speed trace, lap times, heatmap)
- Annotations should be precomputed in the coaching pipeline and delivered via API, not generated client-side
- Time impact estimates (e.g., "consistency here would save ~0.2s") must be computed from telemetry, not AI-guessed

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

### 7.2 Skill Radar Chart (Killer Feature #10) — ✅ DONE

**Fully implemented:**
- Frontend: `SkillRadar.tsx` — D3 radar plot with 4-5 skill dimensions (braking, trail braking, entry/min speed, throttle/exit)
- Computation: `skillDimensions.ts` — `computeSkillDimensions()` converts corner grades to 0-100 scores per axis
- Color: Indigo (#6366f1), shows average score across all axes
- Displayed on `SessionDashboard` in the grid layout

**Remaining:** Show evolution across sessions (session-over-session overlay of radar shapes).

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

### 7.4 Optimal Racing Line Comparison — ⚠️ BACKEND DONE, FRONTEND MINIMAL

**Current:** `optimal_comparison.py` fully implements physics-based optimal comparison:
- `CornerOpportunity` dataclass (actual/optimal min speed, speed gap, brake points, time cost)
- `OptimalComparisonResult` with per-corner gaps and total delta
- API: `GET /{session_id}/optimal-profile` (equipment-aware, uses tire grip params)
- Frontend: Used indirectly for "Ideal Lap Time" metric card and session score computation

**Remaining enhancement:** Dedicated visualization showing the per-corner speed gap as a bar chart or overlay. Note: GPS lateral position claims ("2m wide of apex") exceed consumer GPS precision (3-5m). Use relative comparison (best lap vs other laps) or gate on GPS quality instead.

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

### Wave 1: Coaching Intelligence

*Skill-level prompts already implemented. Focus on remaining coaching gaps.*

| # | Task | Files |
|---|------|-------|
| ~~1.1~~ | ~~Staged coaching tone~~ | ✅ DONE (`_SKILL_PROMPTS` in `coaching.py`) |
| 1.2 | Add OIS format + harden 3-priority cap | `driving_physics.py`, `coaching.py` |
| 1.3 | Strengthen positive framing + add reflective questions | `driving_physics.py` |
| 1.4 | Compute corner speed sensitivity from telemetry | `velocity_profile.py`, `coaching.py` |
| 1.5 | Expand KB from 18 to 40+ snippets (load transfer, brake traces, survival reactions, drivetrain, wet, vision) | `kb_selector.py` |
| 1.6 | Add new pattern triggers (survival reaction, low grip, stagnation, short brake, aero) | `kb_selector.py` |
| 1.7 | Implement stagnation detection | New `stagnation.py` or in `gains.py` |
| 1.8 | Corner geometry auto-classification | `corner_analysis.py` or new module |
| 1.9 | Vehicle specs DB (~40-50 common HPDE cars) | New `vehicle_db.py` |
| 1.10 | Vehicle selection UI + equipment profile integration | Frontend + backend |
| 1.11 | Dynamic load transfer + drivetrain KB snippet integration | `kb_selector.py`, `coaching.py` |
| 1.12 | Tests for all new modules | `tests/` |
| 1.13 | Validate coaching quality (sample prompts, check output) | Manual + validator |

**Parallelizable:** 1.2-1.3 (prompt changes), 1.5-1.6 (KB work), 1.9-1.11 (vehicle DB) are independent streams — run with parallel agents.

**Outcome:** Coaching gains OIS structure, data-grounded sensitivity numbers, 2x more KB depth, and vehicle-specific physics context.

### Wave 2: Remaining Visualizations & Annotations

*Most visualizations already done. Only G-G diagram and chart annotations remain.*

| # | Task | Files |
|---|------|-------|
| ~~2.x~~ | ~~Mini-sector, Time Gained, Session Score, Voice, Degradation~~ | ✅ ALL DONE |
| 2.1 | G-G diagram computation (normalize to observed max G) | New `gg_diagram.py` |
| 2.2 | G-G diagram frontend (D3 scatter + per-corner filter) | New component |
| 2.3 | Expand chart insight annotations to all major charts | Coaching pipeline + frontend |
| 2.4 | Tests | `tests/` |

**Parallelizable:** 2.1-2.2 (G-G) and 2.3 (annotations) are independent.

**Outcome:** G-G diagram fills the last major visualization gap. Chart annotations add narrative context everywhere.

### Wave 3: UX Polish & Social P0

*Core UX already done. Focus on polish, orphan fixes, and remaining gaps.*

| # | Task | Files |
|---|------|-------|
| ~~3.x~~ | ~~Progressive disclosure, hero card, persona-adaptive, debrief~~ | ✅ ALL DONE |
| 3.1 | Report→Deep Dive seamless corner click navigation | Frontend routing |
| 3.2 | Replay export via MediaRecorder (canvas → MP4 for sharing) | Frontend |
| 3.3 | Optimal comparison per-corner visualization (backend data exists) | Frontend component |
| 3.4 | Skill radar session-over-session overlay | Frontend component |
| 3.5 | P0: Move share buttons to SessionReportHeader | P0-1 |
| 3.6 | P0: Unhide achievements/wrapped on mobile | P0-2 |
| 3.7 | P0: Wire CornerLeaderboard into Deep Dive corner detail | P0-3 |
| 3.8 | QA testing (desktop + mobile device emulation) | Playwright |

**Parallelizable:** 3.1-3.4 are independent frontend tasks. P0 fixes (3.5-3.7) are trivial and can be done in one pass.

**Outcome:** Polish remaining gaps, unlock orphaned social features, ship P0 fixes.

### Wave 4: Social P1 Features

| # | Task | Spec |
|---|------|------|
| 4.1 | Upgrade share card to identity-framed design | P1 Task 4 |
| 4.2 | Refine comparison dialog → "Challenge a Friend" + Web Share | P1 Task 5 |
| 4.3 | New achievement card in session report footer | P1 Task 6 |
| 4.4 | Session score badge in TopBar contextual bar | P1 Task 7 |
| 4.5 | Expand leaderboard to multi-category (Late Braker, Smooth Operator) | P1 Task 8 |
| 4.6 | Add leaderboard position sharing | P1 Task 9 |
| ~~4.7~~ | ~~Animated lap replay~~ | ✅ DONE (`LapReplay.tsx`) |

**Spec:** `docs/plans/2026-03-02-social-features-p0p1-implementation.md` Tasks 4-9.
**Outcome:** Every session generates shareable, identity-framed content. Users become ambassadors.

### Wave 5: Social P2 Features

| # | Task | Spec |
|---|------|------|
| 5.1 | Three-layer comparison view (Tale of the Tape → Scorecard → Delta) | P2 Task 10 |
| 5.2 | Progress rate leaderboard backend | P2 Task 11 |
| 5.3 | Progress rate leaderboard frontend | P2 Task 12 |
| 5.4 | Track-level leaderboard summary card | P2 Task 13 |
| 5.5 | Tap-to-compare in leaderboards | P2 Task 14 |
| 5.6 | Achievements section in Progress tab | P2 Task 15 |
| 5.7 | Season Wrapped banner in Progress tab | P2 Task 16 |
| 5.8 | Corner King badge on track map | P2 Task 17 |

**Spec:** `docs/plans/2026-03-02-social-features-p2p3-implementation.md` Tasks 10-17.
**Outcome:** Full competitive social layer — leaderboards, comparisons, crowns, progress ranking.

### Wave 6: Advanced Analytics

| # | Task | Files |
|---|------|-------|
| 6.1 | Multi-session progress dashboard enhancement (per-corner trends, milestones, rolling averages) | Frontend + backend |
| ~~6.2~~ | ~~Skill radar chart~~ | ✅ DONE (`SkillRadar.tsx` + `skillDimensions.ts`) |
| ~~6.3~~ | ~~Season Wrapped generator~~ | ✅ DONE (`SeasonWrapped.tsx`, 4 slides + personalities) |
| 6.2 | Skill radar session-over-session evolution overlay | Frontend component |
| 6.3 | Corner type-specific coaching templates (hairpin, chicane, esses, etc.) | `kb_selector.py` |
| 6.4 | Optimal comparison per-corner speed gap visualization | Frontend component |

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
| Priorities per session | Soft "2-3" guideline | Hard cap at 3 |
| Skill-level adaptation | ✅ Full (novice/intermediate/advanced) | Done |
| KB snippets available | 18 | 50+ |
| Pattern detection triggers | 9 | 15+ |
| Vehicle-specific coaching | None | Car-specific load transfer, drivetrain, power-to-weight |

### User Experience

| Metric | Current | Target |
|--------|---------|--------|
| Upload-to-insight time | ~30s | <15s perceived (skeleton UI) |
| Charts with insight annotations | Sparse (TopPriorities only) | All main charts |
| Mobile usability | ✅ Responsive + pit debrief | Done |
| Progressive disclosure levels | ✅ 4 views (Report/DeepDive/Progress/Debrief) | Done |
| Persona-adaptive rendering | ✅ 13 feature toggles | Done |
| Session Score | ✅ Implemented (3-component, 0-100) | Done |

### Social & Engagement

| Metric | Current | Target |
|--------|---------|--------|
| Share buttons visible | ✅ Yes (SessionDashboard) | Move to Report header too |
| Share card data | Canvas card exists, improvement delta TODO | Identity-framed with hero stat |
| Leaderboard categories | 1 (sector time) | 4 (Corner King, Apex Predator, Late Braker, Smooth Operator) |
| Corner leaderboard reachable | ❌ Orphaned (component exists, not wired) | Yes (in Deep Dive corner detail) |
| Achievements system | ✅ Implemented (8 types, tiers, backend) | Visible on mobile + in Report |
| Season Wrapped | ✅ Implemented (4 slides, personalities) | Share card export |
| Achievement visibility on mobile | Hidden (`hidden sm:flex`) | Visible |
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
