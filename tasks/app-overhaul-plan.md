# Cataclysm App Overhaul Plan

*Comprehensive plan synthesizing the literature review (60+ sources), killer features research, competitive UX analysis, and current architecture into actionable implementation phases.*

*March 2026*

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
- Coaching prompt variant: "The driver has plateaued at [time] for [N] sessions. Identify the specific corners where their technique has become habitual rather than optimal. Suggest ONE new approach to break through."

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

**Complexity:** MEDIUM-HIGH — ~5 days. Defer to Phase 5 with sharing features.

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

### 5.2 Session Score (0-100)

**New metric** — a composite score that gives an instant answer to "how was my session?"

**Calculation:**
- Consistency component (40%): How close were your laps to your best? `1 - (std_dev / mean_laptime)`
- Improvement component (30%): Did you improve vs. previous session at this track?
- Technique component (30%): Aggregate of per-corner grades (brake point accuracy, trail braking, throttle commit, line accuracy)

**Implementation:** New `session_score.py` module. Displayed prominently as a large number with color (green >80, yellow 60-80, red <60).

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

### 6.1 Shareable Session Cards (Killer Feature #1)

**What:** Auto-generated social media cards (9:16 for stories, 1:1 for posts) with track map, racing line, best lap, improvement delta, AI coaching headline. "Analyzed by Cataclysm" branding. ONE TAP to share.

**Why:** Spotify Wrapped proved 500M+ shares. Every share is a free billboard.

**Implementation:**
- Frontend: Canvas/SVG rendering of a card template using existing D3 charts
- Share via Web Share API (native share sheet on mobile)
- Branding: "Analyzed by Cataclysm" + app URL at bottom

**Complexity:** MEDIUM — ~3-4 days.

### 6.2 Driver-to-Driver Comparison (Killer Feature #9)

**What:** Upload session → get shareable link → friend uploads → both see overlay with AI comparing their styles.

**Why:** Every comparison request is an install request. The viral loop is built-in.

**Implementation:**
- Backend: Generate shareable session links. Cross-user delta analysis (extend existing delta comparison).
- Frontend: Split-screen comparison view with AI coaching insights.
- The coaching prompt includes: "Compare Driver A and Driver B's approaches. Where is each faster? What technique differences explain the gaps?"

**Complexity:** HIGH — needs user identity + cross-session matching + new comparison view. Defer to later in this phase.

### 6.3 Season Wrapped (Killer Feature #8)

**What:** Annual recap: total laps, miles, tracks, best improvement, corners mastered, "driving personality." Shareable card.

**Implementation:** Aggregate multi-session data into a storytelling flow (5-6 slides). Generate cards. ONE TAP share.

**Complexity:** MEDIUM — build for end of track season (October-November).

### 6.4 Achievement/Badge System (Killer Feature #14)

**What:** Gamification badges triggered by real accomplishments:
- "Consistency King" — 10 laps within 0.5s
- "Brake Master" — high trail braking utilization
- "Track Rat" — 50+ laps at one track
- "Glass Ceiling" — broke a plateau
- "Sub-[X]" — hit a lap time milestone

**Implementation:** Badge logic on existing metrics. New `achievements.py` backend module. Badge display in sidebar/profile.

**Complexity:** LOW-MEDIUM — ~3 days.

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
| 1.9 | Tests for all new modules | `tests/` | 2 days |
| 1.10 | Validate coaching quality (sample prompts, check output) | Manual + validator | 1 day |

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

### Wave 4: Social & Viral (2-3 weeks)

| # | Task | Files | Effort |
|---|------|-------|--------|
| 4.1 | Shareable session card generator (Canvas/SVG) | New frontend module | 3 days |
| 4.2 | Web Share API integration | Frontend | 1 day |
| 4.3 | Achievement/badge system backend | New `achievements.py` | 2 days |
| 4.4 | Achievement display frontend | New components | 2 days |
| 4.5 | Skill radar chart backend computation | New module | 1 day |
| 4.6 | Skill radar chart D3 component | New D3 chart | 2 days |
| 4.7 | Animated lap replay | D3 animation + sync | 4 days |

**Outcome:** Every session generates shareable content. Users become ambassadors.

### Wave 5: Advanced (Ongoing)

| # | Task | Effort |
|---|------|--------|
| 5.1 | Multi-session progress dashboard enhancement | 3 days |
| 5.2 | Driver-to-driver comparison with shared links | 5 days |
| 5.3 | Season Wrapped generator | 3 days |
| 5.4 | Corner type-specific coaching templates | 2 days |
| 5.5 | Optimal racing line overlay on track map | 3 days |

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

### Engagement

| Metric | Current | Target |
|--------|---------|--------|
| Sessions shared | 0 | Track after launch |
| Return visits per user | Not tracked | Track after launch |
| Feature: Voice narration usage | N/A | Track after launch |
| Feature: Achievement unlocks | N/A | Track after launch |

---

## Appendix: Research Sources Informing This Plan

| Source | Key Contribution to Plan |
|--------|------------------------|
| Literature Review (`coaching-knowledge-literature-review.md`) | 60+ sources: KB expansion content, coaching science, physics quantification |
| Killer Features (`killer-features.md`) | 15 ranked features with competitive evidence |
| Competitive UX Analysis (`competitive-ux-analysis.md`) | Persona definitions, competitor weaknesses, UX patterns, design principles |
| Garmin Catalyst Analysis (`garmin_catalyst_competitive_analysis.md`) | UX gold standard for HPDE, "3 priorities" validation |
| UX Research Report (`ux-research-report.md`) | OIS format, progressive disclosure, F/Z scan patterns |
| Lappi 2018 (Frontiers in Psychology) | 12 deliberate practice procedures, coaching stage mapping |
| Guidance Hypothesis (PMC1780106) | Scientific basis for limiting feedback volume |
| Fitts-Posner Motor Learning Model | Skill-level coaching tone framework |
| Ross Bentley's Speed Secrets | "2 priorities per session", corner speed sensitivity (0.5s/mph) |
| Keith Code's Survival Reactions | 7 detectable counterproductive responses |
| Driver61's 6-Phase Corner Model | Per-phase coaching template system |
| LowerLaptime's 7-Type Geometry | Corner classification for coaching template selection |

---

*Plan authored March 2026. Ready for implementation.*
