# AI Coaching Improvements — Comprehensive Research Synthesis

**Date**: 2026-03-04
**Source**: Three Ralph Loop iterations, 200+ unique sources, 100+ web searches
**Status**: Research complete. Implementation is the priority.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Current System Assessment](#2-current-system-assessment)
3. [Prompt Architecture Overhaul](#3-prompt-architecture-overhaul)
4. [Causal Chain Detection](#4-causal-chain-detection)
5. [Adaptive Skill-Level Coaching](#5-adaptive-skill-level-coaching)
6. [Motor Learning Science](#6-motor-learning-science)
7. [Longitudinal Intelligence](#7-longitudinal-intelligence)
8. [Grading and Quality](#8-grading-and-quality)
9. [Competitive Analysis](#9-competitive-analysis)
10. [Implementation Roadmap](#10-implementation-roadmap)
11. [Ready-to-Implement Prompt Changes](#11-ready-to-implement-prompt-changes)
12. [Sources](#12-sources)

---

## 1. Executive Summary

Three iterations of deep research converge on **five capability gaps** that, when closed, transform Cataclysm from "good automated analysis" into "better than AiM Solo plus a dedicated coach."

**Gap 1: Prompt architecture** — Temperature defaults to 1.0 (should be 0.3). No XML tags, no golden examples, no causal reasoning instruction. Hours of work, massive quality uplift.

**Gap 2: Independent corner grading** — We grade corners in isolation. Track Titan's TimeKiller traces cascading errors across corners. A driver whose T4 problem is entirely caused by T3 gets told to fix T4. This is the single biggest coaching quality gap.

**Gap 3: One-size coaching** — Three tiers (novice/intermediate/advanced) exist but archetype detection does not. A "Coaster" and an "Early Braker" are both novices but need fundamentally different advice.

**Gap 4: No session memory** — Every session starts cold. No awareness of "last session you worked on T5 braking and moved 8m later." No Corners Gained decomposition toward a target lap time.

**Gap 5: Grade inflation** — Current rubric lacks behavioral anchors. LLM agreeableness bias produces mostly B/B+ reports. No distribution guidance forces bell curves.

**The core architecture insight**: Our problem domain has known physics (v² = v₀² + 2ad), known temporal ordering (T3 always before T4), and small data sizes (8–20 laps per session). We do NOT need heavyweight ML/causal inference libraries. Simple statistics plus physics equations outperform learned models at our data scale.

---

## 2. Current System Assessment

### Architecture Overview

| Component | File | Purpose |
|-----------|------|---------|
| Core coaching logic | `cataclysm/coaching.py` | Prompt building, API calls, report generation |
| Corner analysis | `cataclysm/corner_analysis.py` | Pre-computed corner statistics |
| Physics reference | `cataclysm/driving_physics.py` | System prompt, physics guardrails |
| KB injection | `cataclysm/kb_selector.py` | Skill-level knowledge base snippets |
| Validation | `cataclysm/coaching_validator.py` | Adaptive sampling guardrails |
| API endpoints | `backend/api/routers/coaching.py` | HTTP/WS endpoints, background tasks |

### What Works Well

- Pre-computation is correct: all numerical analysis (corner KPIs, gains, optimal comparison) is computed before the LLM call. The LLM generates narrative, not arithmetic.
- OIS feedback structure (Observation → Impact → Suggestion) maps to motor learning principles.
- Skill-level-specific system prompts already exist (`_SKILL_PROMPTS` dict).
- 3-priority-corner limit is scientifically validated (guidance hypothesis).
- Model choice (Haiku 4.5) is correct — 90–95% of Sonnet quality at 1/3 cost (~$0.04/report).

### Critical Gaps

| Gap | Root Cause | Fix |
|-----|-----------|-----|
| Temperature = 1.0 (default) | Never explicitly set | Set to 0.3 in `coaching.py` |
| Markdown headers in prompts | Legacy structure | Convert to XML tags |
| Data and instructions interleaved | No clear separation | Data first, instructions last |
| No golden examples | Never built | Create 2 examples, embed in system prompt |
| Independent corner grading | No inter-corner analysis | Build `causal_chains.py` |
| No archetype detection | Feature gap | Build `driver_archetypes.py` |
| Grade inflation | Vague rubric | Evidence-anchored rubric with thresholds |
| No session memory | DB tables don't exist | `coaching_memory` + `driver_profiles` tables |
| No "because" clauses | Prompt gap | Add explicit requirement |
| Internal focus language | Prompt gap | External focus requirement + translation table |

---

## 3. Prompt Architecture Overhaul

### 3.1 Temperature — The Single Highest-Impact Change

**Current state**: Temperature is unset, defaulting to 1.0. This is far too high for factual coaching.

**Research finding**: Temperature 0.3 with top_p implicitly set is the optimal balance:
- Enough determinism for consistent grading (A–F scale won't fluctuate wildly session to session)
- Enough variance for coaching prose to feel natural and personalized
- Research: "Structured tasks require 0.0–0.2 for consistency; coaching prose needs 0.5–0.7 for naturalness" — the 0.3 sweet spot bridges both

**Critical nuance**: Temperature controls prediction confidence, not factual accuracy. Accuracy comes from prompt quality and grounding in pre-computed data. Temperature is a consistency lever.

**With structured outputs** (available on Haiku 4.5), JSON validity is guaranteed independent of temperature. Once structured outputs are enabled, relax temperature to 0.4–0.5 for better prose naturalness.

**Do NOT set both temperature and top_p** — these interact non-obviously. Use temperature alone.

```python
# In coaching.py, generate_coaching_report()
msg = client.messages.create(
    model="claude-haiku-4-5-20251001",
    max_tokens=16384,
    temperature=0.3,  # replaces default of 1.0
    system=system,
    messages=[{"role": "user", "content": prompt}],
)
```

### 3.2 XML Tag Structure

Claude was trained to recognize XML tags as a prompt-organizing mechanism. Anthropic testing shows **30% quality improvement** with data-first, instructions-last ordering.

**Optimal nesting depth**: 2 levels. 3+ levels has diminishing returns and risks confusing smaller models.

**Do NOT mix markdown headers inside XML tags** — choose one structural system per section.

**Proposed user message structure**:

```xml
<telemetry_data>
  <session_info>Track, best lap, total laps, corner count, conditions</session_info>
  <corner_analysis>Pre-computed analysis block</corner_analysis>
  <lap_times>Table of all laps</lap_times>
  <corner_kpis note="best lap marked with *">All-laps KPI table</corner_kpis>
  <gains>Gain estimation vs session best</gains>
  <optimal>Physics-optimal analysis</optimal>
  <landmarks>Visual landmarks for this track</landmarks>
  <equipment>Vehicle + tire + conditions</equipment>
  <causal_chains>Inter-corner cascade analysis (Phase 2)</causal_chains>
  <session_history>Driver history at this track (Phase 4)</session_history>
</telemetry_data>

<coaching_instructions>
  <skill_level>Novice/Intermediate/Advanced context</skill_level>
  <analysis_focus>What to analyze across all laps</analysis_focus>
  <grading_rubric>A-F definitions with behavioral anchors</grading_rubric>
</coaching_instructions>

<examples>
  <example index="1">Gold standard report (Example A)</example>
  <example index="2">Contrastive anti-example (Example B)</example>
</examples>

<output_format>
  JSON schema + constraints (num corners, speed markers, etc.)
</output_format>
```

**Critical ordering rule**: Longform telemetry data at top. Output format specification at the very end, closest to where generation begins. This is Anthropic's strongest documented recommendation.

### 3.3 Golden Examples

**Research finding**: 2–3 examples is the sweet spot for Haiku 4.5. Beyond 3, the "few-shot dilemma" — incorporating excessive examples paradoxically degrades performance. Quality trumps quantity. Put the best example first.

**Design strategy**: One "gold standard" example showing all desired qualities + one contrastive "anti-example" with `[WRONG]` and `[BETTER]` annotations. This contrastive approach is particularly powerful for preventing grade inflation and improving causal reasoning.

**Use semi-realistic synthetic examples** — based on plausible data from real tracks (e.g., Barber Motorsports Park), but designed to illustrate specific patterns. Fully real examples contain confounding factors; purely synthetic examples teach unrealistic patterns.

See Section 11 for the complete golden example text ready to paste into `driving_physics.py`.

### 3.4 Data Ordering Within Prompt

Per the 2025 "Order Effect" research, LLMs are highly sensitive to ordering. Optimal ordering:

1. Role/system context (system prompt)
2. Physics reference + guardrails (system prompt)
3. Knowledge base snippets (system prompt)
4. Long-form telemetry data (TOP of user message)
5. Coaching instructions + grading rubric
6. Golden examples
7. Output format specification (VERY END, closest to generation start)

### 3.5 Structured Outputs Migration

Haiku 4.5 supports structured outputs (constrained decoding) as of 2025. This guarantees JSON validity independent of temperature. Migration path:

1. Define a Pydantic schema matching the existing `CoachingReport` dataclass
2. Pass the schema to the API `response_format` parameter
3. Remove any `{` prefill if used — deprecated pattern, structured outputs replace it
4. Once confirmed working, relax temperature to 0.4–0.5 for better prose

---

## 4. Causal Chain Detection

### 4.1 The Problem

We grade corners independently. If a driver blows T3 and ruins T4 as a result, we report two separate problems when the real fix is just T3. Track Titan's "TimeKiller" traces root causes through multiple corners — this is our #1 competitive gap.

**Known physics simplifies this enormously**: We do not need DoWhy, Bayesian networks, or Granger causality. The causal graph is known (track layout defines it), physical mechanisms are understood (v² = v₀² + 2ad), and temporal ordering is fixed (T3 always before T4). Simple statistics + physics outperform learned models at 8–20 laps per session.

### 4.2 Corner Link Detection — Two Methods

**Method 1: Physics-Based (Static, Per-Track)**

```python
def compute_recovery_fraction(
    exit_speed_mps: float,
    natural_approach_speed_mps: float,
    gap_distance_m: float,
    max_accel_g: float = 0.5,  # typical street car full throttle
) -> float:
    """Fraction of speed deficit recoverable in the available gap.

    Returns 0.0–1.0:
      1.0 = full recovery (corners are independent)
      < 0.7 = corners are linked
      < 0.3 = tightly coupled
    """
    if exit_speed_mps >= natural_approach_speed_mps:
        return 1.0

    accel_mps2 = max_accel_g * 9.81
    achievable_speed_sq = exit_speed_mps**2 + 2 * accel_mps2 * gap_distance_m
    achievable_speed = achievable_speed_sq**0.5

    deficit = natural_approach_speed_mps - exit_speed_mps
    recovered = min(achievable_speed, natural_approach_speed_mps) - exit_speed_mps

    return min(1.0, recovered / deficit) if deficit > 0 else 1.0
```

**Classification thresholds**:
- `recovery_fraction >= 0.9`: Independent corners
- `0.5 <= recovery_fraction < 0.9`: Partially linked
- `recovery_fraction < 0.5`: Strongly linked
- `recovery_fraction < 0.2`: Tightly coupled (essentially one complex)

**Method 2: Data-Driven (Dynamic, Per-Session)**

Pearson correlation between T[n] exit speed and T[n+1] min speed across all laps:

```python
def compute_exit_entry_correlation(
    all_lap_corners: dict[int, list[Corner]],
    cn_a: int,
    cn_b: int,
) -> tuple[float, float]:
    """Pearson r between corner A exit speed and corner B min speed across laps."""
    exit_speeds: list[float] = []
    min_speeds: list[float] = []

    for lap_corners in all_lap_corners.values():
        corner_map = {c.number: c for c in lap_corners}
        if cn_a in corner_map and cn_b in corner_map:
            exit_speeds.append(corner_map[cn_a].min_speed_mps)
            min_speeds.append(corner_map[cn_b].min_speed_mps)

    if len(exit_speeds) < 4:
        return 0.0, 1.0

    if np.std(exit_speeds) < 1e-6 or np.std(min_speeds) < 1e-6:
        return 0.0, 1.0

    r, p = pearsonr(exit_speeds, min_speeds)
    return float(r), float(p)
```

**Use hybrid approach**: Physics for initial classification (which pairs COULD be linked), correlation to confirm (which pairs ARE linked for this driver/car). Only flag cascades when both methods agree.

### 4.3 Data Structures

New module: `cataclysm/causal_chains.py`

```python
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class CornerLink:
    """Physical coupling between two adjacent corners."""
    corner_a: int
    corner_b: int
    gap_distance_m: float
    recovery_fraction: float  # 0.0 = tightly coupled, 1.0 = independent
    correlation_r: float
    correlation_p: float
    link_strength: str  # "tight" | "moderate" | "weak" | "independent"


@dataclass
class CascadeEffect:
    """Per-lap quantification of how one corner's error affects the next."""
    lap: int
    source_corner: int
    affected_corner: int
    source_speed_delta_mps: float
    inherited_speed_delta_mps: float
    inherited_time_cost_s: float
    self_caused_time_cost_s: float
    inheritance_fraction: float  # 1.0 = 100% inherited from upstream


@dataclass
class CausalChain:
    """A detected chain of cascading errors across multiple corners."""
    root_cause_corner: int
    affected_corners: list[int]
    root_cause_type: str  # "late_brake" | "early_apex" | "slow_exit"
    total_cascade_time_s: float
    root_cause_time_s: float
    downstream_time_s: float
    laps_affected: list[int]
    frequency: float  # fraction of laps where this chain appeared
    coaching_summary: str  # natural language for the LLM


@dataclass
class SessionCausalAnalysis:
    """Complete causal chain analysis for a session."""
    links: list[CornerLink]
    chains: list[CausalChain]  # sorted by total_cascade_time_s descending
    total_cascade_time_s: float
    cascade_fraction: float  # what fraction of total time loss is cascading
    top_time_killer: CausalChain | None
```

### 4.4 Cascade Quantification

**The key decomposition**: `T4_total_loss = T4_self_caused + T4_inherited_from_T3`

```python
def compute_lap_cascades(
    lap_corners: list[Corner],
    best_corners: list[Corner],
    links: list[CornerLink],
) -> list[CascadeEffect]:
    """For a single lap, quantify how upstream errors propagate downstream."""
    effects = []
    best_map = {c.number: c for c in best_corners}
    lap_map = {c.number: c for c in lap_corners}

    for link in links:
        if link.link_strength == "independent":
            continue

        cn_a, cn_b = link.corner_a, link.corner_b
        if not all(k in lap_map for k in [cn_a, cn_b]) or cn_a not in best_map:
            continue

        source_delta = best_map[cn_a].min_speed_mps - lap_map[cn_a].min_speed_mps
        if source_delta <= 0:
            continue  # No upstream error to cascade

        propagation_factor = 1.0 - link.recovery_fraction
        inherited_delta = source_delta * propagation_factor
        total_delta_b = best_map[cn_b].min_speed_mps - lap_map[cn_b].min_speed_mps

        if total_delta_b <= 0:
            continue

        inherited_delta = min(inherited_delta, total_delta_b)
        self_delta = total_delta_b - inherited_delta

        avg_speed = (best_map[cn_b].min_speed_mps + lap_map[cn_b].min_speed_mps) / 2
        corner_length = best_map[cn_b].exit_distance_m - best_map[cn_b].entry_distance_m

        if avg_speed > 0.1:
            inherited_time = corner_length * inherited_delta / (avg_speed**2)
            self_time = corner_length * self_delta / (avg_speed**2)
        else:
            inherited_time = self_time = 0.0

        effects.append(CascadeEffect(
            lap=0,  # set by caller
            source_corner=cn_a,
            affected_corner=cn_b,
            source_speed_delta_mps=round(source_delta, 3),
            inherited_speed_delta_mps=round(inherited_delta, 3),
            inherited_time_cost_s=round(inherited_time, 4),
            self_caused_time_cost_s=round(self_time, 4),
            inheritance_fraction=round(inherited_delta / total_delta_b, 3),
        ))

    return effects
```

### 4.5 TimeKiller Prompt Integration

Add this pre-computed block to the coaching prompt:

```
<causal_chains>
## Causal Chain Analysis (TimeKiller Detection)

### Chain 1 (TimeKiller): T3 -> T4 -> T5
- Root cause: T3 (braking too late — entry speed too high → early apex)
- Total cascade: 0.26s (0.15s at T3 + 0.08s at T4 + 0.03s at T5) across 75% of laps
- Fix: Brake 8m earlier at T3 → T4 and T5 improve automatically
- T4 inheritance fraction: 0.72 (72% of T4's time loss is from T3)

### Chain 2: T7 -> T8
- Root cause: T7 (slow exit speed — coasting through turn)
- Total cascade: 0.11s across 60% of laps
</causal_chains>
```

**Coaching principle**: Coach the ROOT (brake point at T3), not the SYMPTOM (exit speed at T5). If inheritance_fraction > 0.6, label the downstream corner as "(cascading from TX)" and focus the tip on the root.

---

## 5. Adaptive Skill-Level Coaching

### 5.1 Driver Archetype Detection

Seven archetypes detectable from telemetry we already compute:

| Archetype | Telemetry Signature | Coaching Focus |
|-----------|-------------------|----------------|
| **Early Braker** | Brake point 15–30m before optimal, low peak brake G, long coast before turn-in | Confidence building, later braking, reference points |
| **Late Braker / Hero** | Late brake, inconsistent (high std), sometimes locks up, early apex | Patience, trail braking, anchoring to a fixed reference |
| **Coaster** | Gap between brake release and throttle, low min speed, late throttle commit | Eliminate dead zone, trail braking concept, commit to gas |
| **Smooth Operator** | Low variance across laps, moderate G-forces, clean traces | Pushing limits, finding where more speed lives |
| **Aggressive Rotator** | High lateral G, abrupt steering inputs, tight apex | Smoothness, car control, weight transfer timing |
| **Conservative Liner** | Consistent but early apex or wide entry, high repeat accuracy | Track width usage, late apex geometry, re-examine line |
| **Trail Brazer** | Strong trail braking, good overlap, but brake past apex too often | Release point refinement, let rotation come from initial phase |

**Detection pseudocode** (per-corner, using metrics already computed):

```python
def detect_corner_archetype(corner_data: list[Corner]) -> str:
    avg_brake_to_apex = mean(c.apex_distance_m - c.brake_point_m for c in corner_data)
    avg_peak_g = mean(c.peak_brake_g for c in corner_data)
    throttle_gap = mean(c.throttle_commit_m - c.apex_distance_m for c in corner_data)
    brake_std = stdev(c.brake_point_m for c in corner_data)
    has_trail_braking = fraction(c for c in corner_data if c.trail_brake_present)

    if avg_brake_to_apex > 1.5 * expected_brake_zone and avg_peak_g < 0.5:
        return "early_braker"
    elif brake_std > 12 and avg_peak_g > 0.8:
        return "late_braker_hero"
    elif throttle_gap > 30 and not has_trail_braking:
        return "coaster"
    elif brake_std < 5 and throttle_std < 8:
        return "smooth_operator"
    elif has_trail_braking > 0.6 and brake_past_apex:
        return "trail_brazer"
    elif apex_consistency < 0.1 and early_apex_fraction > 0.5:
        return "conservative_liner"
    return "balanced"
```

### 5.2 Telemetry-Based Skill Level Detection

Auto-detect skill level from telemetry (no explicit driver declaration needed):

| Metric | Novice | Intermediate | Advanced |
|--------|--------|-------------|----------|
| Lap time CV (coefficient of variation) | > 3% | 1.5–3% | < 1.5% |
| Brake point std dev (avg across corners) | > 12m | 5–12m | < 5m |
| Min speed std dev (avg across corners) | > 4 mph | 2–4 mph | < 2 mph |
| Peak brake G (session max) | < 0.5G | 0.5–0.8G | > 0.8G |
| Trail braking present (% of corners) | < 20% | 20–60% | > 60% |
| Throttle commit consistency (std dev) | > 15m | 8–15m | < 8m |

**Progression detection** (when to advance coaching tier):

| Transition | Telemetry Indicators |
|-----------|---------------------|
| Novice → Intermediate | Brake std < 10m, min speed CV < 8%, 5+ track sessions at this track |
| Intermediate → Advanced | Brake std < 5m, min speed CV < 5%, within 5% of track record, 15+ sessions |

### 5.3 Scaffolding and ZPD (Vygotsky Applied)

Vygotsky's Zone of Proximal Development: teach at the edge of current capability. Early coaching constrains the problem space ("just hit the same brake marker every lap"), then progressively expands it.

**Cognitive load limits per level**:
- Novice: 1–2 instructions per corner maximum
- Intermediate: 2–3 instructions per corner
- Advanced: 3–4 instructions per corner plus inter-corner chain analysis

**Priority corners per level** (guidance hypothesis alignment, Bentley's 2-directive rule):
- Novice (HPDE 1–2): 1–2 priority corners only
- Intermediate (HPDE 3): 2–3 priority corners
- Advanced (HPDE 4+): 3–4 priority corners with full causal chain analysis

### 5.4 Implicit Learning Analogy Library (Novices)

Novices benefit from analogies that bypass explicit technique description, reducing cognitive load:

| Technique | Analogy | Basis |
|-----------|---------|-------|
| Trail braking | "Like squeezing water from a sponge — gradual release, not sudden" | Liao & Masters 2001 |
| Weight transfer | "Imagine the car is a bowl of soup — keep it from spilling" | Embodied cognition |
| Racing line | "Like skiing — set up wide, carve through the apex" | Skill transfer |
| Throttle application | "Like accelerating in the rain — progressive, not sudden" | Risk calibration |
| Brake pressure | "The car can stop much shorter — feel the seatbelt pull you forward harder" | External focus |

---

## 6. Motor Learning Science

### 6.1 External Focus of Attention — Most Important Language Rule

The motor learning literature is unambiguous across hundreds of studies (Wulf meta-analysis, Chua et al. 2021 meta-analysis): **external focus consistently outperforms internal focus at every skill level**.

- External focus: attention directed to effects in the environment ("the car should slow more aggressively")
- Internal focus: attention directed to body movements ("press the brake pedal harder")

**The distance effect**: More distal external cues produce better outcomes than proximal ones. Novices need proximal external cues (brake board); experts benefit from distal ones (exit point, 2 seconds ahead).

**External focus translation table** (required for all coaching output):

| Internal Focus (PROHIBITED) | External Focus (REQUIRED) | Skill Level |
|---|---|---|
| "Press the brake pedal harder" | "The car should slow more aggressively before the marker" | All |
| "Turn the steering wheel earlier" | "Point the car toward the inside curb sooner" | All |
| "Turn the wheel more gradually" | "The car should track a wider arc through the corner" | All |
| "Squeeze the throttle" | "Let the car accelerate as you unwind the wheel" | Int/Adv |
| "Relax your hands" | "Let the car talk to you through the wheel" | Advanced |
| "Apply 0.9G of brake force" | "Feel the nose dive under braking — that's the weight loading the front tires" | All |
| "Your min speed was 3 mph low" | "Carry enough speed that you barely need to add power through the apex" | All |

**Include kinesthetic sensations** for each tip:
- Weight transfer: "Feel the nose dive under braking, then lighten as you trail off"
- Rotation: "Feel the car rotate around the apex — don't fight it with steering"
- Throttle: "Feel the rear squat as you unwind the wheel and squeeze throttle"
- Speed: "You'll feel like you're braking too early at first — trust the data"

### 6.2 OPTIMAL Theory of Motor Learning (Wulf & Lewthwaite 2016)

Three factors work additively to enhance motor learning:

1. **Enhanced Expectancies** — belief that improvement is possible (growth mindset framing)
2. **Autonomy Support** — giving the learner choices, not prescriptive commands
3. **External Focus** — referencing environment, not body movements

We partially address #1 and #3. We miss #2 entirely.

**Autonomy-supportive framing for intermediate+ drivers**: Frame tips as experiments, not commands:
- "Try anchoring to the 3-board for 3 laps, then compare your data"
- "Experiment with trailing the brakes 5m deeper into T5"
- "Test whether holding flat through the kink changes your exit speed"

**For novices**, prescriptive commands are appropriate (novices lack the background knowledge to make informed choices):
- "Brake at the 3-board marker every lap for the next 3 laps"
- "Do not lift mid-corner — keep the steering smooth and consistent"

### 6.3 The Guidance Hypothesis — Less Feedback is Better

Counter-intuitive but well-established (Winstein & Schmidt 1990, confirmed 2020 meta-analysis): drivers receiving feedback on 33% of items outperform those receiving 100% feedback on retention tests. More feedback creates dependency; less forces self-monitoring and deeper learning.

**Implementation**: This scientifically validates our existing 3-priority-corner approach. For novices, reduce to 1–2 priorities and explicitly say: "Don't try to fix everything. Focus only on Turn 5 for your next 3 sessions."

### 6.4 Warmth Instructions Degrade Accuracy — Critical Warning

Oxford Internet Institute study (July 2025, arXiv:2507.21919): optimizing LLMs for warmth degrades factual reliability by +10–30 percentage points. Warm models validate incorrect beliefs 40% more often when users express frustration.

**Do NOT add** "be warm and friendly" or "be empathetic" to the system prompt. Our current instruction "be encouraging but honest" is borderline safe but should be replaced with:

> "Begin with 2–3 specific data-backed strengths (e.g., 'Your T7 consistency was excellent — only 0.1s variance across 12 laps'). Let positive tone come from the OIS structure, not from general warmth language."

The OIS format is the best defense against the warmth/accuracy tradeoff because every observation must cite specific numbers.

### 6.5 "Because" Clauses — 41% Increase in Acceptance

Bank of America AI coaching research: explaining WHY a recommendation is made increases user acceptance by 41%.

Every coaching tip must include a data-backed "because" clause:
- BAD: "Try braking later at T5"
- GOOD: "Try braking at the 2-board at T5, because your current brake point (3-board) leaves 8m of unused straight-line braking, costing ~0.3s per lap"

---

## 7. Longitudinal Intelligence

### 7.1 Session Memory Architecture

**Design choice**: Hybrid structured + summarized memory. No vector DB needed initially.
- **Structured data**: PostgreSQL tables for per-session metrics (grades, speeds, priorities, milestones)
- **Narrative context**: Summarized to ~2,000 tokens for prompt injection

**Token budget allocation** for coaching prompt with history:

| Section | Token Budget | Content |
|---|---|---|
| System prompt | ~1,500 | Coaching persona, format instructions |
| Session history injection | ~2,000 | Structured summary |
| KB snippets | ~500 | Driving technique knowledge |
| Current session data | ~5,000 | Lap times, corner KPIs, gains, analysis |
| Output buffer | ~3,000 | Reserve for response |
| **Total** | **~12,000** | Well within Haiku's 200k context |

**Database tables**:

```sql
CREATE TABLE coaching_memory (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    track_name TEXT NOT NULL,
    session_date TIMESTAMPTZ NOT NULL,
    best_lap_time_s FLOAT NOT NULL,
    top3_avg_time_s FLOAT,
    corner_grades JSONB,        -- {1: {braking: "B", trail: "C", ...}, ...}
    priority_corners JSONB,     -- [5, 3, 1]
    corner_speeds JSONB,        -- {1: 45.2, 2: 67.8, ...}
    key_strengths JSONB,        -- ["consistent braking", ...]
    key_weaknesses JSONB,       -- ["late throttle T5", ...]
    drills_assigned JSONB,      -- ["brake marker drill T5", ...]
    conditions_summary TEXT,
    equipment_summary TEXT,
    coaching_summary TEXT,      -- 2-3 sentence AI-generated summary
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(user_id, session_id)
);

CREATE TABLE driver_profiles (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    track_name TEXT NOT NULL,
    total_sessions INT DEFAULT 0,
    first_session_date TIMESTAMPTZ,
    latest_session_date TIMESTAMPTZ,
    best_ever_lap_s FLOAT,
    best_ever_session_id TEXT,
    corner_mastery JSONB,       -- {1: {best_speed: 45.2, trend: "improving", ...}}
    recurring_weaknesses JSONB,
    improving_areas JSONB,
    plateaued_areas JSONB,
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(user_id, track_name)
);
```

**Dataclasses**:

```python
@dataclass
class CoachingMemoryEntry:
    session_id: str
    session_date: datetime
    track_name: str
    best_lap_time_s: float
    corner_grades: dict[int, dict[str, str]]
    priority_corners: list[int]
    corner_best_speeds_mph: dict[int, float]
    key_strengths: list[str]
    key_weaknesses: list[str]
    drills_assigned: list[str]
    conditions: str | None
    equipment: str | None


@dataclass
class CornerMastery:
    corner_number: int
    sessions_seen: int
    best_min_speed_mph: float
    latest_min_speed_mph: float
    speed_trend: str  # "improving" | "plateaued" | "regressing"
    best_grade: str
    latest_grade: str
    grade_history: list[tuple[datetime, str]]
```

### 7.2 Corners Gained (Adapted from Arccos Golf "Strokes Gained")

Arccos doesn't just show "you're bad at approach shots." It shows: "To go from 12 handicap to 8, gain 2.3 strokes per round on approach." Our equivalent:

> "To reach 1:40 from your current 1:42, focus on T5 braking (0.8s), T1 entry (0.4s), and consistency (0.6s)."

We already compute the numbers — we just don't frame them as a path to a target.

**Formula**:

```
Corners Gained (T_n) = Expected_Time(T_n, baseline) - Actual_Time(T_n)
Positive = faster than expected | Negative = slower
```

**Baseline strategy**: Start with personal best (always available). Add population percentiles when enough users exist per track.

**Facet decomposition** (same as Arccos's five facets):

```python
@dataclass
class CornerGain:
    corner_number: int
    gained_s: float
    expected_time_s: float
    actual_time_s: float
    gained_braking_s: float    # from brake point delta
    gained_min_speed_s: float  # from speed delta
    gained_throttle_s: float   # from throttle timing delta
    gained_line_s: float       # residual (line/positioning)


@dataclass
class CornersGainedResult:
    lap_number: int
    total_gained_s: float
    corner_gains: list[CornerGain]
    gained_braking_s: float    # session-level facet totals
    gained_min_speed_s: float
    gained_throttle_s: float
    gained_line_s: float
```

**Cross-session visualization** (the most powerful application):

```
Session 1 (March 1):  Total CG = -2.4s  T1: -0.3s  T3: -0.8s  T5: -1.2s
Session 2 (March 15): Total CG = -1.1s  T1: -0.1s  T3: -0.3s  T5: -0.8s
Improvement: +1.3s gained | Biggest gain: T3 (+0.5s)
```

### 7.3 Flow Lap Detection

Flow state from Csikszentmihalyi: challenge-skill balance, complete immersion, intrinsic motivation. Coaching should NOT disrupt flow with over-prescription.

**Flow lap = all corners within a tight band of personal best, simultaneously.** Not just one great corner — all of them.

```python
@dataclass
class FlowLapResult:
    flow_laps: list[int]
    flow_score_per_lap: dict[int, float]  # 0.0–1.0
    session_flow_window: tuple[int, int] | None
    flow_quality: str  # "deep_flow" | "light_flow" | "no_flow"


def detect_flow_laps(
    all_lap_corners: dict[int, list[Corner]],
    lap_summaries: list[LapSummary],
    personal_bests: dict[int, float],
) -> FlowLapResult:
    """4-component composite flow score per lap."""
    PROXIMITY_THRESHOLD = 0.05  # within 5% of personal best sector time
    BALANCE_MAX_CV = 0.08       # max coefficient of variation across corners
    SMOOTHNESS_THRESHOLD = 0.15  # max technique variance
    FLOW_SCORE_THRESHOLD = 0.7

    # For each lap, compute weighted composite:
    # flow_score = 0.45 * proximity + 0.25 * balance + 0.20 * smoothness + 0.10 * timing_bonus
    # proximity: min (not avg) corner proximity — ALL corners must be near PB
    # balance: low CV across corner proximity scores — no "hero corners"
    # smoothness: low speed CV within the lap
    # timing_bonus: mid-session laps get 0.1 boost (first 2 / last 2 laps excluded)
```

**Coaching use of flow laps**:
- "Laps 8, 12, and 14 were your flow laps — all corners within 95% of personal best. What were you thinking/feeling during those laps?"
- "The driver's performance during the flow window represents their TRUE current ability level. Grade based on this window, not warmup/cooldown laps."
- Flow quality "deep_flow" (3+ consecutive flow laps) signals the driver has internalized the track and is ready for the next challenge level.

### 7.4 Pre-Session Briefing Generation

When a driver returns to a track, generate a focus briefing from session history:

- **Novices**: Learning goals (process-focused) — "Today at Barber: focus on hitting the same brake point every lap at T5. Consistency before speed."
- **Advanced**: Performance goals (outcome-focused) — "Your T5 brake point moved 15m later over 4 sessions. This session, test whether you can reach the 1-board consistently."

**Briefing structure** (adapted from F1 race engineer debrief protocol):
1. Recap of last session's priority corners and whether drills were attempted (inferred from data)
2. One primary focus goal for today
3. One stretch goal if conditions allow
4. Equipment/conditions context (different tires = adjust braking expectations)

### 7.5 Milestone Detection

Progress Principle (Amabile & Kramer): 28% of minor progress events had major emotional impact on motivation. Small wins matter enormously. Celebrate them.

**15+ milestone types to detect**:
- First-ever personal best lap time
- Corner-specific personal best (fastest ever through T5)
- Consistency milestone (brake point std drops below threshold for the first time)
- Brake point improvement (moved X meters later vs. historical average)
- Sub-X lap time achievement (first time under 1:45, 1:40, etc.)
- Technique unlock (trail braking detected for first time)
- Flow state achievement (first deep_flow session)
- Cross-session streak (3+ consecutive sessions improving at same corner)

---

## 8. Grading and Quality

### 8.1 The Grade Inflation Problem

Research on LLM-as-judge grading reveals systematic biases that directly apply to our system:
- **Agreeableness bias**: LLM judges have true positive rates > 96% but true negative rates < 25% — they almost never give bad scores
- **Verbosity bias**: ~15% grade inflation from associating longer descriptions with higher quality
- Without explicit distribution guidance, models default to "everyone gets B+"

**Mitigation**: Evidence-anchored behavioral rubrics + explicit grade distribution expectations.

### 8.2 Evidence-Anchored Rubric (RULERS Framework)

Replace the current vague rubric with measurable behavioral thresholds. Require evidence extraction BEFORE grading (RULERS framework: "reliable LLM judging requires executable rubrics, verifiable evidence, and calibrated scales").

```
BRAKING:
  A: Brake point std < 3m AND peak G within 0.05G of best across 90%+ of laps
  B: Brake point std < 5m AND peak G within 0.10G of best across 75%+ of laps
  C: Brake point std 5–8m OR peak G spread > 0.15G OR inconsistent on 3+ laps
  D: Brake point std > 8m OR frequently missing braking zone
  F: No consistent brake point established OR dangerous braking patterns

TRAIL BRAKING:
  A: Trail brake present on 90%+ of laps with consistent timing
  B: Trail braking present on 70%+ of laps with minor timing variance
  C: Trail braking inconsistent or absent on 40%+ of laps
  D: No trail braking detected; abrupt brake release at turn-in on most laps
  N/A: Flat-out kinks, lifts, or novice drivers where trail braking is inappropriate

MIN SPEED:
  A: Min speed std < 1.0 mph AND within 1 mph of target on 90%+ of laps
  B: Min speed std 1.0–2.0 mph AND within 2 mph of target on 75%+ of laps
  C: Min speed std 2.0–3.0 mph OR consistently 3+ mph below target
  D: Min speed std > 3.0 mph OR erratic speed patterns suggesting fear/uncertainty
  F: Min speed consistently 5+ mph below target suggesting fundamental line issues

THROTTLE:
  A: Throttle commit std < 5m AND progressive application on 90%+ of laps
  B: Throttle commit std 5–10m AND mostly progressive
  C: Throttle commit std 10–15m OR hesitant/partial throttle on 3+ laps
  D: Throttle commit std > 15m OR abrupt on/off throttle patterns
  F: No consistent throttle point OR mid-corner lifts suggesting fear
```

### 8.3 Grade Distribution Expectations

Add to system prompt:

```
Grade distribution guidance:
- A typical intermediate driver should have mostly B/C grades with 1-2 As and possibly 1-2 Ds
- An all-A report is almost never correct — it means you are not differentiating performance
- An all-D/F report is also suspect — even struggling drivers have relative strengths
- The BEST corner for the session might get 1-2 As; the WORST might get 1-2 Ds
- Grade each criterion independently: great braking can coexist with poor throttle at the same corner
- After grading, ask yourself: "Is this distribution a normal bell curve around B/C?"
```

### 8.4 Evidence-Before-Grading Protocol

Add to system prompt:

```
For each corner grade, you MUST:
1. First cite the specific statistics from the pre-computed analysis (std, mean, best values)
2. Map those statistics to the rubric criteria above
3. THEN assign the grade
Do NOT assign grades intuitively — follow the rubric thresholds.

If data is inconclusive for a corner (e.g., fewer than 4 clean laps), say:
"Insufficient data to grade — only 3 clean laps available at T7"
Never hallucinate a cause you cannot support with telemetry data.
```

### 8.5 Anti-Patterns to Avoid

| Anti-Pattern | Research Source | Risk |
|---|---|---|
| Add generic warmth ("be warm and friendly") | Oxford 2025 (arXiv:2507.21919) | +10–30% error rate increase |
| Add verbose chain-of-thought for Haiku | Wharton 2024 | Faulty reasoning in smaller models |
| Add > 3 few-shot examples | PromptHub meta-analysis | Few-shot dilemma, degraded performance |
| Use internal-focus language | Wulf meta-analysis (hundreds of studies) | Disrupts motor learning at all skill levels |
| Show all corners to novices | Guidance hypothesis + Bentley | Information overload, dependency |
| Use gamification badges for motivated users | Self-determination theory | Extrinsic rewards HARM intrinsic motivation |
| Sacrifice accuracy for encouragement | Sycophancy research (Anthropic) | Destroys trust when discovered |
| Set both temperature AND top_p | Multiple sources | Non-obvious interactions, unpredictable behavior |
| Grade intuitively then find evidence | RULERS framework | Retroactive justification is unreliable |
| Vague rubric without thresholds | RULERS/AutoRubric | Grade inflation, halo effects |

---

## 9. Competitive Analysis

### vs. Track Titan ($5M funded, sim-only)

| Capability | Track Titan | Cataclysm Current | Cataclysm Post-Research |
|-----------|------------|-------------------|------------------------|
| Inter-corner causation | TimeKiller (physics sim) | None | Causal chains (Phase 2) |
| Root cause coaching | Coaching Flows | Independent corners | 5-step causal decomposition |
| Skill adaptation | Basic novice/pro | 3 tiers | 7 archetypes + auto-detect |
| Session memory | Limited | None | Full longitudinal intelligence |
| Real-world telemetry | No (sim only) | Yes | Yes |
| Hardware required | PC + sim rig | Phone + RaceChrono ($30) | Phone + RaceChrono ($30) |
| Coaching methodology | Physics simulation | LLM + pre-computed | LLM + physics + motor learning science |

**Track Titan threat timeline**: Real-world launch estimated late 2026 – early 2027. Our head start: 6–12 months.

### vs. Garmin Catalyst 2 ($1,199)

| Capability | Catalyst 2 | Cataclysm Post-Research |
|-----------|-----------|------------------------|
| Coaching depth | "Brake earlier" rule-based | Root cause chains, evidence-anchored |
| Personalization | Minimal | Archetype + skill-adaptive |
| Price | $1,199 + subscription | Free / low-cost (hardware: $30) |
| Session memory | Basic trend lines | Full longitudinal intelligence |
| AI coaching | Rule-based | LLM + physics guardrails |

### vs. Griiip (hardware-dependent, B2B)

| Capability | Griiip | Cataclysm |
|-----------|-------|----------|
| Deployment model | OEM hardware (Skip Barber, NJMP) | Software-only, any iOS/Android |
| Market | Racing schools, professional series | HPDE track day drivers |
| Coaching | Real-time in-car display | Post-session deep analysis |
| Overlap | Minimal — different segment | White space |

### Market Position

**Market size**: $579.5M → $1,489.5M by 2035 (9.9% CAGR, racing telemetry market).

**Unique position**: Nobody is doing zero-hardware-barrier, LLM-powered deep coaching for real-world track day drivers with physics-grounded causal analysis, skill-level-adapted coaching, cross-session progress tracking, and interactive follow-up chat.

### "Holy Shit" Feature Stack

**For Novices (HPDE 1–2)**:
1. Plain English coaching with analogies ("like squeezing water from a sponge")
2. 1–2 priorities only — celebrate what they're doing right
3. Visual landmarks ("brake at the 3-board") not meter distances
4. Growth trajectory ("You improved 0.8s. At this rate, break 1:45 in 2 more sessions")
5. External focus only — "the car should…" never "you should press…"
6. Pre-session briefing ("Today: focus only on T5 braking consistency")
7. Milestone celebrations (first PB, consistency achievement)
8. Flow lap identification ("Laps 8 and 12 were your best — what did that feel like?")

**For Advanced (HPDE 4+, racers)**:
1. Root cause chains ("Your T4 problem starts at T3. Fix the brake point and T4 improves automatically.")
2. TimeKiller detection ("Your biggest cascade: T3→T4→T5, costing 0.26s total")
3. Archetype insights ("Your data shows a 'Coaster' pattern. Here's how to convert coast to commitment.")
4. Corners Gained decomposition ("To break 1:38: T5 braking 0.3s, T1 entry 0.2s, consistency 0.15s")
5. Session memory ("Your T5 brake point moved 15m later over 4 sessions. Consistency improved 0.8s.")
6. Evidence-anchored grades ("T5 Braking: B (std 4.2m, peak G within 0.08G)")
7. Setup hints from telemetry ("T2 and T6 both show understeer signatures — consider adding front grip")
8. Experiment-framed tips ("Try braking 5m deeper at T5 for 3 laps and compare your data")

**For Everyone**:
1. < 30-second analysis — upload CSV → full coaching report instantly
2. Follow-up chat — "Why should I brake later?" → physics-backed explanation
3. Shareable session cards
4. No hardware required ($30 RaceChrono vs $1,199 Garmin)
5. "Because" clauses on every tip — trust through data transparency

---

## 10. Implementation Roadmap

### Phase 0 — Prompt Quick Wins (parallelizable)
*Highest ROI, zero architecture changes. Do this first.*

| # | Change | File | Impact |
|---|--------|------|--------|
| 1 | Set `temperature=0.3` | `coaching.py` | Consistency + accuracy (1 line) |
| 2 | Add uncertainty admission instruction | `driving_physics.py` | Reduces hallucinated causation |
| 3 | Replace markdown headers with XML tags | `coaching.py` | ~30% parsing improvement |
| 4 | Move data to top, instructions to bottom | `coaching.py` | ~30% quality improvement |
| 5 | Replace "be encouraging" with "cite data-backed strengths" | `driving_physics.py` | Prevents warmth/accuracy tradeoff |
| 6 | Add "because" clause requirement | `driving_physics.py` | +41% recommendation acceptance |
| 7 | Add external focus language requirement + translation table | `driving_physics.py` | Motor learning improvement |
| 8 | Add kinesthetic sensation vocabulary | `driving_physics.py` | Bridges data → execution |
| 9 | Add autonomy-supportive framing for intermediate+ | `driving_physics.py` | OPTIMAL Theory compliance |
| 10 | Reduce priority_corners to 2 for novice | `coaching.py` | Guidance hypothesis alignment |

### Phase 1 — Grading and Causal Reasoning (parallelizable with Phase 0)
*Quality of analysis leap.*

| # | Change | File | Impact |
|---|--------|------|--------|
| 11 | Evidence-anchored rubric (per-criterion thresholds) | `driving_physics.py` | Prevents grade inflation |
| 12 | Grade distribution expectations | `driving_physics.py` | Bell curve around B/C |
| 13 | Evidence-before-grading instruction | `driving_physics.py` | RULERS framework compliance |
| 14 | 5-step causal reasoning decomposition | `driving_physics.py` | Root cause > symptom coaching |
| 15 | Create Golden Example A (intermediate @ Barber) | `driving_physics.py` | Calibrates all output qualities |
| 16 | Create Golden Example B (contrastive anti-example) | `driving_physics.py` | Shows what NOT to do |

### Phase 2 — Inter-Corner Causal Chains
*Our #1 competitive gap. Matches Track Titan.*

| # | Change | File | Impact |
|---|--------|------|--------|
| 17 | `CornerLink` + `compute_recovery_fraction()` + correlation | New: `causal_chains.py` | Detect linked corners |
| 18 | `CascadeEffect` + per-lap propagation | `causal_chains.py` | Quantify cascading errors |
| 19 | `CausalChain` + session aggregation + TimeKiller | `causal_chains.py` | Root cause identification |
| 20 | Integrate into pipeline: add to coaching prompt | `corner_analysis.py`, `coaching.py` | LLM receives chain data |
| 21 | Add causal chain instruction to system prompt | `driving_physics.py` | LLM interprets chain data correctly |
| 22 | Frontend: cascade badges + inheritance bars on corner cards | Frontend components | Visual cascade display |

### Phase 3 — Adaptive Skill Detection (parallelizable with Phase 2)
*Personalization without explicit setup.*

| # | Change | File | Impact |
|---|--------|------|--------|
| 23 | 7-archetype detection from telemetry | New: `driver_archetypes.py` | Auto-classify driving style |
| 24 | Archetype-specific coaching language injected into prompt | `coaching.py`, `driving_physics.py` | Tailored tips per archetype |
| 25 | Auto skill level detection (6-dimension scoring) | New: `skill_detection.py` | No explicit skill declaration needed |
| 26 | External focus translation table in system prompt (skill-level-aware) | `driving_physics.py` | Proximal → distal by skill |
| 27 | Implicit learning analogies library for novices | `driving_physics.py` | Reduce cognitive load |
| 28 | Cognitive load limits per skill level enforced in prompt | `coaching.py` | Right amount of detail per driver |

### Phase 4 — Longitudinal Intelligence
*Session-over-session intelligence.*

| # | Change | File | Impact |
|---|--------|------|--------|
| 29 | `coaching_memory` + `driver_profiles` DB tables + migrations | `models.py`, `alembic/` | Structured memory storage |
| 30 | Memory extraction service after report generation | New: `coaching_memory.py` | Auto-persist session insights |
| 31 | Hierarchical summarization for prompt injection | `coaching_memory.py` | ~2,000 token history context |
| 32 | Corners Gained algorithm | New: `corners_gained.py` | Target-based improvement path |
| 33 | Flow lap detection | `corner_analysis.py` or new `flow_detection.py` | Identify peak performance laps |
| 34 | Pre-session briefing generation | New: `briefing.py` + API endpoint | Focus guidance before driving |
| 35 | Milestone detection + celebration | New: `milestones.py` + frontend | Progress Principle engagement |
| 36 | Session comparison with condition normalization | New: `session_comparison.py` | Fair cross-session comparison |

### Phase 5 — Structured Outputs Migration (parallelizable)
*Technical debt reduction.*

| # | Change | File | Impact |
|---|--------|------|--------|
| 37 | Define Pydantic schema for coaching report JSON | `coaching.py` | Type-safe output definition |
| 38 | Migrate to structured outputs API parameter | `coaching.py` | 100% JSON conformance |
| 39 | Relax temperature to 0.4–0.5 | `coaching.py` | Better prose with guaranteed JSON |

### Phase 6 — Validation and Tuning (ongoing)

| # | Change | Impact |
|---|--------|--------|
| 40 | A/B test old vs. new prompt on 20 sessions | Measure quality delta |
| 41 | Validate grade distribution (should be bell curve B/C) | Catch inflation regression |
| 42 | Review causal reasoning quality in outputs | Verify WHY not WHAT |
| 43 | Tune archetype detection thresholds on real data | Accuracy validation |
| 44 | Calibrate flow detection threshold (0.7) on real sessions | User feedback loop |
| 45 | Iterate golden examples based on output quality | Continuous improvement |

---

## 11. Ready-to-Implement Prompt Changes

All text below can be pasted directly into `driving_physics.py` (system prompt) or `coaching.py` (user prompt builder).

### 11.1 Temperature Setting (coaching.py)

```python
msg = client.messages.create(
    model="claude-haiku-4-5-20251001",
    max_tokens=16384,
    temperature=0.3,  # LOW for factual accuracy; high enough for natural prose
    system=system,
    messages=[{"role": "user", "content": prompt}],
)
```

### 11.2 XML Tag Restructure (coaching.py — user prompt builder)

Replace:
```python
f"## Lap Times\n{lap_text}\n\n## Corner KPIs — All Laps\n{corner_text}"
```

With:
```python
f"""<telemetry_data>
<lap_times>
{lap_text}
</lap_times>

<corner_kpis note="best lap marked with *">
{corner_text}
</corner_kpis>
</telemetry_data>"""
```

### 11.3 Causal Reasoning Requirement (driving_physics.py — system prompt addition)

```
## Causal Reasoning Requirement

For each priority corner, trace the root cause chain:
1. OBSERVATION: What measurable telemetry pattern do you see? (cite numbers)
2. MECHANISM: What physics principle explains this? (reference the physics guide)
3. ROOT CAUSE: What is the driver likely DOING to produce this? (technique diagnosis)
4. TIME IMPACT: How much time does this cost? (cite gain data)
5. FIX: What specific change would address the ROOT CAUSE?

Example chain:
  Symptom: Low exit speed at T5
  ← Caused by: Delayed throttle (waiting for car to settle)
  ← Caused by: Early apex (car pointed at outside wall)
  ← ROOT CAUSE: Brake point 12m early → too much entry speed → early turn-in → early apex
  → FIX: Anchor braking to the 3-board (fixes entry → fixes apex → fixes exit)

Coach the ROOT (brake point), not the SYMPTOM (exit speed). If a corner's grades
show D in throttle but the real problem is entry, say so explicitly.

If you see <causal_chains> data in the prompt showing that a corner's problem is
inherited from an upstream corner (inheritance_fraction > 0.6), focus the coaching
on the root cause corner, not the affected one.
```

### 11.4 External Focus + Kinesthetic Language (driving_physics.py — system prompt addition)

```
## Coaching Voice — External Focus Required

Frame ALL tips in terms of what the CAR does or what the driver FEELS, not what
the body does.

PROHIBITED (internal focus):
  "Press the brake pedal harder"
  "Turn the steering wheel more gradually"
  "Relax your hands on the wheel"

REQUIRED (external focus):
  "The car should slow more aggressively before the marker"
  "The car should track a wider arc through the corner"
  "Let the car talk to you through the wheel"

For each priority corner tip, include ONE kinesthetic sensation the driver will
feel when executing correctly:
  - Weight transfer: "Feel the nose dive under braking, then lighten as you trail off"
  - Rotation: "Feel the car rotate around the apex — don't fight it with steering"
  - Throttle: "Feel the rear squat as you unwind the wheel and squeeze throttle"
  - Speed: "You'll feel like you're braking too early at first — trust the data"

DISTANCE EFFECT (apply by skill level):
  - Novice: proximal external cues ("focus on the brake board", "look at the apex cone")
  - Intermediate: mid-range ("watch the exit curbing", "let the car track to the apex")
  - Advanced: distal ("focus on the exit point, 2 seconds ahead")
```

### 11.5 Autonomy-Supportive Language (driving_physics.py — system prompt addition)

```
## Autonomy Support (Intermediate and Advanced Only)

For intermediate and advanced drivers, frame tips as EXPERIMENTS, not commands:
  "Try anchoring to the 3-board for 3 laps, then compare your data"
  "Experiment with trailing the brakes 5m deeper into T5"
  "Test whether holding flat through the kink changes your exit speed"

For novices, prescriptive commands are appropriate (they lack the experience to
make informed choices):
  "Brake at the 3-board marker every lap for the next 3 laps"
  "Do not lift mid-corner — keep the steering smooth and consistent"
```

### 11.6 "Because" Clause Requirement (driving_physics.py — system prompt addition)

```
## Evidence-Backed Recommendations

Every coaching recommendation MUST include a data-backed "because" clause:

BAD: "Try braking later at T5"
GOOD: "Try braking at the 2-board at T5, because your current brake point (3-board)
      leaves 8m of unused straight-line braking, costing ~0.3s per lap"

The "because" gives the driver confidence that advice is grounded in THEIR data,
not generic guidance. Cite specific numbers from the pre-computed analysis.
```

### 11.7 Grade Distribution and Evidence-Anchored Rubric (driving_physics.py — replace existing rubric)

```
## Grading Rubric — Evidence-Anchored Behavioral Thresholds

Grade each criterion INDEPENDENTLY. Do not grade the corner holistically.

BRAKING:
  A: Brake point std < 3m AND peak G within 0.05G of best across 90%+ of laps
  B: Brake point std < 5m AND peak G within 0.10G of best across 75%+ of laps
  C: Brake point std 5-8m OR peak G spread > 0.15G OR inconsistent on 3+ laps
  D: Brake point std > 8m OR frequently missing braking zone
  F: No consistent brake point OR dangerous braking patterns

TRAIL BRAKING:
  A: Present on 90%+ of laps with consistent timing
  B: Present on 70%+ of laps with minor timing variance
  C: Inconsistent or absent on 40%+ of laps
  D: No trail braking; abrupt brake release at turn-in on most laps
  N/A: Novice driver, flat kink, or lift corner where trail braking is inappropriate

MIN SPEED:
  A: Std < 1.0 mph AND within 1 mph of target on 90%+ of laps
  B: Std 1.0-2.0 mph AND within 2 mph of target on 75%+ of laps
  C: Std 2.0-3.0 mph OR consistently 3+ mph below target
  D: Std > 3.0 mph OR erratic patterns suggesting fear/uncertainty
  F: Consistently 5+ mph below target suggesting fundamental line issues

THROTTLE:
  A: Commit std < 5m AND progressive application on 90%+ of laps
  B: Commit std 5-10m AND mostly progressive
  C: Commit std 10-15m OR hesitant/partial throttle on 3+ laps
  D: Commit std > 15m OR abrupt on/off throttle patterns
  F: No consistent throttle point OR mid-corner lifts

## Grade Distribution Guidance

A typical intermediate driver's session should show:
  - Mostly B/C grades across criteria
  - 1-2 A grades maximum (reserved for genuinely outstanding consistency)
  - 1-2 D grades for clear technique gaps
  - No all-A report (means you are not differentiating — almost never accurate)
  - No all-D/F report (even struggling drivers have relative strengths)

## Evidence-Before-Grading Protocol

For each corner grade, you MUST:
1. Cite the specific statistics (std, mean, best values from the pre-computed data)
2. Map those statistics to the rubric criteria above
3. THEN assign the grade

If data is inconclusive (fewer than 4 clean laps at this corner), write:
"Insufficient data to grade — only N clean laps available"
Never guess a cause you cannot support with the telemetry data provided.
```

### 11.8 Golden Example (driving_physics.py — system prompt addition, in <examples> tags)

```xml
<examples>
<example index="1">
<context>
Track: Barber Motorsports Park, 12 laps, intermediate driver, dry conditions,
street tires (RE-71RS). Best lap: 1:42.3. Session best corner splits vs. optimal
shown in corner_kpis section.
</context>
<ideal_output>
{
  "summary": "Strong session with clear progression — your T7 consistency was
   elite (0.5 mph std across 12 laps). You found 1.2 mph of corner speed at T5
   through the session, and your brake points at T1 tightened from ±12m to ±4m
   by the final third. Primary opportunity is T3 where your entry speed variance
   (4.2 mph std) suggests the brake point isn't anchored to a fixed reference.
   What visual marker are you using for your T3 brake point?",

  "priority_corners": [
    {
      "corner": 3,
      "time_cost_s": 0.42,
      "issue": "Brake point shifts 15m between best and worst laps, causing 4.2
               mph entry speed variance. This forces mid-corner corrections that
               delay throttle application by 0.3s on average.",
      "tip": "Anchor braking to the 2-board shadow for 3 laps — the car should
              slow aggressively before the board passes your A-pillar. You'll
              feel the nose dive earlier, giving you confidence to trail brake
              deeper. Try this approach and compare your entry speed data."
    }
  ],

  "corner_grades": {
    "1": {"braking": "B", "trail_braking": "C", "min_speed": "B", "throttle": "B"},
    "3": {"braking": "D", "trail_braking": "N/A", "min_speed": "C", "throttle": "C"},
    "7": {"braking": "A", "trail_braking": "B", "min_speed": "A", "throttle": "B"}
  },

  "patterns": [
    "T3 brake variance (±8m) is the ROOT CAUSE of T3-T4 time loss: inconsistent
     entry speed forces mid-corner adjustment, which delays throttle and costs
     0.42s average. Fix the brake point, not the throttle.",
    "T7 elite consistency (0.5 mph std) shows you CAN be repeatable — apply this
     same anchoring discipline to T3."
  ]
}
</ideal_output>
</example>

<example index="2" type="anti-example">
<context>Same session as above.</context>
<bad_output>
{
  "summary": "Great session! You showed really good pace and your consistency
   was impressive overall.",
  [WRONG: Generic warmth with no data. What was consistent? By how much?]

  "priority_corners": [
    {
      "corner": 3,
      "tip": "Try braking later and pressing the pedal harder into the corner."
      [WRONG: Internal focus ("pressing"), no causal chain, no "because" clause,
       no data citation, no kinesthetic cue]
    }
  ],

  "corner_grades": {
    "1": {"braking": "A", "trail_braking": "A", "min_speed": "A", "throttle": "A"},
    "3": {"braking": "A", "trail_braking": "B", "min_speed": "A", "throttle": "A"}
    [WRONG: All-A report. Brake std at T3 was 8m (= D by rubric). This is grade
     inflation from agreeableness bias. Evidence: brake_std_m=8.2 in corner_kpis]
  },

  "patterns": [
    "Your brake pressure of 85 PSI suggests you're under-braking."
    [WRONG: Fabricated data — brake PSI is not in our telemetry. Never cite data
     not present in the pre-computed analysis. This is hallucination.]
  ]
}
</bad_output>
<lessons>
- Every claim must cite numbers from the pre-computed analysis
- Grade distribution must follow rubric thresholds, not intuition
- Tips must use external focus language with kinesthetic cues
- "Because" clauses are required on every recommendation
- Never fabricate telemetry metrics not present in the data
</lessons>
</example>
</examples>
```

### 11.9 Session History Injection (coaching.py — add when Phase 4 is built)

```
<session_history>
## Driver History at {track_name}

Sessions: {total_sessions} | First visit: {first_date} | Latest: {latest_date}
Best-ever lap: {best_ever_lap_s:.2f}s (session {best_ever_session_id})
Progression: {formatted_progression}

### Previous Session ({prev_date})
Best lap: {prev_best:.2f}s | Priority corners: T{p1}, T{p2}
Drills assigned: {drills_list}
Key takeaway: {prev_summary}

### Corner Mastery Profile
{for each corner}
T{n}: Grade {latest_grade} (trend: {trend}) | Best speed: {best_mph:.1f} mph
{end for}

### Recurring Coaching Themes
- Strengths (consistent 3+ sessions): {strengths}
- Persistent weaknesses (3+ sessions): {weaknesses}
- Improving areas: {improving}
- Plateaued areas (no change 3+ sessions): {plateaued}

### Coaching Instructions for This Session
- Reference the driver's history when relevant
  (e.g., "last session you were braking 10m too early at T5 — check if that improved")
- Acknowledge improvement where it occurred
  (e.g., "Your T3 min speed improved from 42 mph to 45 mph — great progress")
- If a weakness persists from last session, escalate coaching intensity
- If drills were assigned, infer whether the data shows they were attempted
</session_history>
```

---

## 12. Sources

### LLM Prompt Engineering
- [Anthropic: Prompting Best Practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)
- [Anthropic: Use XML Tags](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/use-xml-tags)
- [Anthropic: Long Context Tips](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/long-context-tips)
- [Anthropic: Structured Outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)
- [Anthropic: Avoiding Hallucinations (Course)](https://github.com/anthropics/courses/blob/master/prompt_engineering_interactive_tutorial/Anthropic%201P/08_Avoiding_Hallucinations.ipynb)
- [PromptHub: Few-Shot Prompting Guide](https://www.prompthub.us/blog/the-few-shot-prompting-guide)
- [The Few-Shot Dilemma (2025)](https://arxiv.org/html/2509.13196v1)
- [Finding Golden Examples (Towards Data Science)](https://towardsdatascience.com/finding-golden-examples-a-smarter-approach-to-in-context-learning/)
- [LLMs are Contrastive Reasoners (2024)](https://arxiv.org/html/2403.08211v2)
- [The Order Effect in LLMs (2025)](https://arxiv.org/html/2502.04134v2)
- [LLM Temperature Guide (Tetrate)](https://tetrate.io/learn/ai/llm-temperature-guide)
- [Wharton: Decreasing Value of Chain of Thought (2025)](https://gail.wharton.upenn.edu/research-and-insights/tech-report-chain-of-thought/)
- [Too Nice to Be True: Warmth Degrades Reliability (Oxford 2025)](https://arxiv.org/abs/2507.21919)
- [Mind Your Tone: Prompt Politeness (2025)](https://arxiv.org/abs/2510.04950)
- [Causal Reasoning Addresses LLM Limitations (InfoQ)](https://www.infoq.com/articles/causal-reasoning-observability/)

### Grading and Quality
- [RULERS: Locked Rubrics (2026)](https://arxiv.org/abs/2601.08654)
- [AutoRubric (2026)](https://arxiv.org/html/2603.00077)
- [Rubric Is All You Need (2025)](https://arxiv.org/html/2503.23989v1)
- [Evaluating Scoring Bias in LLM-as-Judge (2025)](https://arxiv.org/html/2506.22316v1)
- [LLM-as-a-Judge: A Practical Guide (Towards Data Science)](https://towardsdatascience.com/llm-as-a-judge-a-practical-guide/)
- [AutoSCORE: Evidence-Before-Grading (2025)](https://arxiv.org/html/2509.21910v1)

### Motor Learning Science
- [OPTIMAL Theory of Motor Learning — Wulf & Lewthwaite 2016](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5056258/)
- [External Focus Meta-Analysis — Chua et al. 2021 (PubMed)](https://pubmed.ncbi.nlm.nih.gov/34843301/)
- [External Focus Meta-Analysis — Nature Scientific Reports 2025](https://www.nature.com/articles/s41598-025-19862-2)
- [Guidance Hypothesis — Winstein & Schmidt 1990](https://journals.sagepub.com/doi/10.1177/00315125900240010)
- [Self-Controlled Practice (Frontiers)](https://www.frontiersin.org/articles/10.3389/fpsyg.2020.00849/full)
- [Implicit vs Explicit Learning — Liao & Masters 2001](https://pubmed.ncbi.nlm.nih.gov/11411779/)
- [Vygotsky ZPD Applied to Motor Learning](https://www.simplypsychology.org/zone-of-proximal-development.html)
- [Dreyfus Model of Skill Acquisition](https://en.wikipedia.org/wiki/Dreyfus_model_of_skill_acquisition)

### Professional Coaching Methods
- [Ross Bentley: Coaching With Data (Speed Secrets)](https://rossbentley.substack.com/p/speed-secrets-coaching-with-data)
- [Driver 61: Corner Phases](https://driver61.com/uni/corner-phases/)
- [Driver 61: Prioritising Corners](https://driver61.com/uni/prioritising-corners/)
- [YourDataDriven: Race Engineer Debriefs](https://www.yourdatadriven.com/levelling-up-your-racing-driver-feedback/)
- [Blayze: Complex Corners](https://blayze.io/blog/car-racing/complex-corners)
- [Allen Berg: Three Corner Types](https://www.allenbergracingschools.com/expert-advice/race-tracks-three-corners-types/)
- [HP Academy: Going Faster with Data Analysis](https://www.hpacademy.com/technical-articles/going-faster-with-data-analysis/)
- [Skip Barber Racing School](https://www.skipbarber.com/courses/3-day-racing-school/)
- [BMW Performance Driving School](https://bmwperformancecenter.com/driverschool/)
- [Porsche Track Experience](https://experience.porsche.com/en/track/track-experience/about-track-experience)

### Causal Chain Detection
- [Track Titan: Coaching Flows (Nov 2025)](https://www.tracktitan.io/post/november-2025-update-coaching-flows)
- [Track Titan AI Deep Dive (Skywork)](https://skywork.ai/skypage/en/Track-Titan-An-AI-Powered-Deep-Dive-for-Sim-Racers-and-Tech-Enthusiasts/1976160936392716288)
- [Full Grip Motorsport: Telemetry Analysis](https://www.fullgripmotorsport.com/telemetry)
- [DoWhy: Root Cause Analysis (AWS Blog)](https://aws.amazon.com/blogs/opensource/root-cause-analysis-with-dowhy-an-open-source-python-library-for-causal-machine-learning/)
- [Visual Analytics for Causal Analysis (arXiv)](https://arxiv.org/pdf/2009.02458)

### Adaptive Skill and Archetypes
- [AI Approach for Analyzing Driving Behaviour (Springer 2023)](https://link.springer.com/chapter/10.1007/978-3-031-49065-1_19)
- [AI-Enabled Prediction of Sim Racing Performance (ScienceDirect 2024)](https://www.sciencedirect.com/science/article/pii/S2451958824000472)
- [Scaffolding Theory for Motor Skill Acquisition (Frontiers 2025)](https://www.frontiersin.org/journals/human-neuroscience/articles/10.3389/fnhum.2025.1631958/full)
- [NASA HPDE Official](https://drivenasa.com/hpde/)
- [The Racer's Mind — Lappi 2018](https://pmc.ncbi.nlm.nih.gov/articles/PMC6099114/)

### Longitudinal Intelligence
- [Arccos Golf: Strokes Gained Analytics](https://www.arccosgolf.com/pages/strokes-gained-analytics)
- [Flow State Meta-Analysis (Tandfonline)](https://www.tandfonline.com/doi/full/10.1080/1750984X.2021.1929402)
- [Progress Principle — Amabile & Kramer (HBR)](https://hbr.org/2011/05/the-power-of-small-wins)
- [WHOOP AI Guidance](https://www.whoop.com/us/en/thelocker/new-ai-guidance-from-whoop/)
- [Memory Mechanisms in LLM Agents (Emergent Mind)](https://www.emergentmind.com/topics/memory-mechanisms-in-llm-based-agents)
- [Context Engineering — LangChain](https://blog.langchain.com/context-engineering-for-agents/)

### Performance Psychology
- [AI Coaching Effectiveness — Systematic Review 2025](https://pmc.ncbi.nlm.nih.gov/articles/PMC11614623/)
- [Explainability Increases Acceptance by 41% — Bank of America](https://coachello.ai/blog/how-ai-coaching-create-personalized-development/)
- [Self-Determination Theory in Sport (Frontiers)](https://www.frontiersin.org/articles/10.3389/fpsyg.2020.00849/full)
- [SBI Feedback Model (CCL)](https://www.ccl.org/articles/leading-effectively-articles/closing-the-gap-between-intent-vs-impact-sbii/)

### Competitive Intelligence
- [Griiip x Skip Barber](https://www.skipbarber.com/2025/07/14/drive-to-thrive-skip-barber-racing-school-and-griiip-launch-game-changing-tech-partnership-to-accelerate-the-future-of-motorsport-training/)
- [Racing Telemetry Market — $1.49B by 2035](https://market.us/report/racing-telemetry-market/)
- [Humanizing AI Is a Trap (NNG)](https://www.nngroup.com/articles/humanizing-ai/)
