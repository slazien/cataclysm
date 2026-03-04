# Unified Implementation Roadmap: AI Coaching + Driving Line Analysis

**Date**: 2026-03-04
**Status**: Implementation-ready — no further research required
**Sources**: 8 deep-research documents, 200+ sources, 3 research iterations

This is an action document. Every item is implementable without additional research. Phases with no inter-phase dependencies are marked as parallelizable.

---

## Phase 0: Prompt Quick Wins

**Can be parallelized with nothing (do first — zero risk, maximum ROI)**

These changes require zero new code, no new data structures, and no schema changes. They touch only `cataclysm/coaching.py` and `cataclysm/driving_physics.py`.

### 0.1 Temperature Fix

File: `cataclysm/coaching.py` — `generate_coaching_report()`

Change the Claude API call to add `temperature=0.3`. Currently unset, which defaults to 1.0 — far too high for factual grading.

```python
response = client.messages.create(
    model=COACHING_MODEL,
    max_tokens=MAX_TOKENS,
    temperature=0.3,   # ADD THIS LINE
    system=system_prompt,
    messages=[{"role": "user", "content": user_message}],
)
```

### 0.2 XML Tag Restructuring

File: `cataclysm/coaching.py` — `_build_user_message()`

Claude was trained specifically to parse XML tags. Replace markdown headers with XML in the user message. Current structure (markdown headers interleaved with data) should become:

```
<telemetry_data>
  <session_info>...</session_info>
  <corner_analysis>...</corner_analysis>
  <lap_times>...</lap_times>
  <corner_kpis>...</corner_kpis>
  <gains>...</gains>
  <landmarks>...</landmarks>
  <equipment>...</equipment>
</telemetry_data>

<coaching_instructions>
  <skill_level>...</skill_level>
  <grading_rubric>...</grading_rubric>
  <output_format>...</output_format>
</coaching_instructions>
```

Move all telemetry data to the top, all instructions to the bottom. Anthropic's own testing shows up to 30% quality improvement with data-first ordering.

### 0.3 Prompt Instruction Changes

File: `cataclysm/driving_physics.py` — the system prompt / `_SKILL_PROMPTS` dict

Apply all of the following text changes:

**Replace "be encouraging but honest"** with:
```
Acknowledge strong corners with specific data (e.g., "Your T7 consistency was excellent — only 0.1s variance across laps"). Never use general warmth language. Praise must be data-backed.
```

**Add "because" clause requirement**:
```
Every coaching tip must include a data-backed "because" clause explaining why the change will gain time. BAD: "Brake later at T5." GOOD: "Brake at the 2-board at T5, because your current entry leaves 8m of straight-line braking unused, costing ~0.3s per lap."
```

**Add external focus requirement**:
```
Use external focus language (the environment, the car's behavior) not internal focus (your body, your inputs). BAD: "Press the brake harder." GOOD: "The car should slow more aggressively before the marker." BAD: "Turn the wheel earlier." GOOD: "Point the car toward the inside curb sooner."
```

**Add uncertainty admission**:
```
If the data is inconclusive for a corner (e.g., too few laps, high variance with no pattern), say "Data inconclusive at this corner — more laps needed" rather than forcing a diagnosis.
```

**Add autonomy-supportive framing for intermediate/advanced skill levels**:
```
For intermediate and advanced drivers, frame tips as experiments: "Try braking at the 2-board for 3 laps and compare your data" rather than commands. Giving choices improves motor learning outcomes.
```

### 0.4 Priority Corner Limit for Novices

File: `cataclysm/coaching.py` — wherever `priority_corners` count is set

Cap `priority_corners` at 2 for novice skill level. The guidance hypothesis (Wulf) shows drivers receiving feedback on 33% of items outperform those receiving 100% feedback on retention tests.

```python
MAX_PRIORITY_CORNERS = {
    "novice": 2,
    "intermediate": 3,
    "advanced": 4,
}
```

### Phase 0 Tests
- `tests/test_coaching.py`: assert temperature=0.3 in the API call kwargs
- Smoke-test prompt builds on mock session data for all 3 skill levels
- Assert `len(report["priority_corners"]) <= 2` when skill_level="novice"

---

## Phase 1: Grading and Quality Overhaul

**Can be parallelized with Phase 2 and Phase 3**

### 1.1 Evidence-Anchored Rubric

File: `cataclysm/driving_physics.py` — grading rubric section in system prompt

Replace the current vague rubric with the RULERS-style evidence-anchored version. Each criterion has measurable thresholds:

```
GRADING RUBRIC — evaluate each criterion independently (no halo effects):

BRAKING:
  A = brake point std < 3m AND peak G within 0.05G of session maximum
  B = std 3-6m AND peak G within 0.10G
  C = std 6-10m OR peak G 0.10-0.20G below max
  D = std > 10m OR peak G > 0.20G below max
  F = no consistent brake point detectable across laps
  N/A = corner has no meaningful braking zone

TRAIL BRAKING:
  A = overlap between brake release and turn-in present on 90%+ of laps
  B = present 70-90% of laps
  C = present 40-70% of laps
  D = present < 40% of laps
  F = no trail braking detected on any lap
  N/A = kinks, chicanes, or corners where trail braking is inappropriate

MINIMUM SPEED:
  A = std < 1.0 mph AND within 1 mph of physics-optimal
  B = std 1.0-2.0 mph OR within 2 mph of optimal
  C = std 2.0-3.5 mph OR 2-4 mph below optimal
  D = std > 3.5 mph OR > 4 mph below optimal
  F = > 6 mph below optimal or highly erratic

THROTTLE COMMIT:
  A = commit point std < 5m AND progressive ramp (no flat spots)
  B = std 5-8m AND mostly progressive
  C = std 8-15m OR abrupt on/off pattern on some laps
  D = std > 15m OR abrupt on/off pattern on most laps
  F = no consistent throttle commit point

Grade distribution expectation: most corners in a typical session should receive B or C. A grades should be rare (top 10-15% of corners). F grades should indicate genuine problems, not just imperfection. If your distribution is mostly A/B, recalibrate toward B/C.
```

**Add evidence-before-grading instruction**:
```
Before assigning a grade, write the evidence observation first (AutoSCORE pattern): "T5 braking: std 4.8m, peak G 0.87G (session max 0.91G). Evidence: inconsistent brake point, borderline B/C. Grade: C." This process prevents grade inflation.
```

### 1.2 Five-Step Causal Reasoning Decomposition

File: `cataclysm/driving_physics.py` — system prompt

Add the causal reasoning instruction for the `patterns` field. LLMs jump from observation to suggestion, skipping the causal mechanism. Force the chain:

```
For each coaching pattern, follow this exact 5-step chain:
1. OBSERVATION: What measurable telemetry pattern do you see? (cite numbers)
2. MECHANISM: What physics principle explains this? (reference the physics guide)
3. ROOT CAUSE: What is the driver most likely DOING to produce this? (technique diagnosis)
4. TIME IMPACT: How much time does this cost? (cite gain data in seconds)
5. FIX: What specific, actionable change would address the root cause? (include a landmark reference)

Example of the wrong approach (SYMPTOM-AS-CAUSE): "The driver brakes late at T5, causing slow exit speed."
Example of the right approach (ROOT CAUSE): "T5 exit speed is 2.3 mph below best-lap average (OBSERVATION). Late brake point means insufficient speed reduction before apex, causing early-apex to avoid running wide (MECHANISM). The driver likely lacks confidence in brake force effectiveness and compensates by turning in earlier to feel safer (ROOT CAUSE). This costs ~0.28s per lap on the back straight (TIME IMPACT). Try threshold braking (firm initial pedal application) from the 3-board, which allows a later, wider turn-in and proper apex at the 2-board (FIX)."
```

### 1.3 Golden Example A — Gold Standard Report (Intermediate @ Barber)

File: `cataclysm/driving_physics.py` — inside `<examples>` XML tags in system prompt

This is the calibration anchor. Full JSON structure showing:
- OIS format in `patterns[].tip` field (Observation-Impact-Suggestion)
- Mixed grade distribution (A at T7, B at T3, C at T5, D at T1)
- Causal patterns ("Your slow T5 exit is the root cause of your straight-line deficit, not just a corner problem")
- Landmark references ("brake at the 3-board")
- "Because" clauses ("costing ~0.3s per lap because...")
- External focus language ("the car should slow more aggressively")
- Calibrated to feel like a real intermediate session — not a perfect driver, not a disaster

Embed as:
```python
GOLDEN_EXAMPLE_A = """
<example index="1">
<!-- CORRECT: Gold-standard intermediate report at Barber Motorsports Park -->
{
  "overall_assessment": "Strong session overall. Your T3 and T7 consistency has improved markedly. T5 is your TimeKiller — the early apex there cascades across the back section. Two changes this session: T5 turn-in and T1 brake point.",
  "corner_grades": {
    "1": {"braking": "D", "trail_braking": "N/A", "min_speed": "C", "throttle": "C", "overall": "D"},
    "3": {"braking": "B", "trail_braking": "B", "min_speed": "B", "throttle": "B", "overall": "B"},
    "5": {"braking": "B", "trail_braking": "C", "min_speed": "C", "throttle": "C", "overall": "C"},
    "7": {"braking": "A", "trail_braking": "B", "min_speed": "A", "throttle": "B", "overall": "A"}
  },
  "patterns": [
    {
      "title": "T5: Early Apex Costing Exit Speed",
      "tip": "Your T5 apex is arriving at roughly 35% through the corner — the data shows min speed occurring earlier than it should. Because you're hitting the apex early, the car is pointed toward the wall on exit, forcing you to ease off rather than commit to full throttle. This costs ~0.4s on the long back straight. Try delaying your turn-in by 8-10m — use the start of the rumble strip as your new reference. The later apex (targeting 55-60% through the corner) opens the exit and lets the car accelerate as you unwind the wheel."
    }
  ],
  "priority_corners": [5, 1]
}
</example>
"""
```

### 1.4 Golden Example B — Contrastive Anti-Example

File: `cataclysm/driving_physics.py` — second `<example>` tag

Shows what NOT to do. Each bad element is annotated with `[WRONG: reason]` and `[BETTER: alternative]`:

```
<example index="2">
<!-- WRONG: Grade inflation — never give all A/B when data shows mediocre session -->
"corner_grades": {"5": {"braking": "A", ...}}  [WRONG: brake std was 9m, should be C or D]

<!-- WRONG: Internal focus -->
"tip": "Press the brake pedal harder at T5."  [WRONG: internal focus. BETTER: "The car should slow more aggressively before the 3-board."]

<!-- WRONG: Missing "because" clause -->
"tip": "Brake later at T5."  [WRONG: no data, no reason. BETTER: "Brake 6m later at T5, because your current brake point leaves 0.4s of unused deceleration on the table."]

<!-- WRONG: Symptom-as-cause -->
"tip": "T4 is slow because you're not carrying enough speed."  [WRONG: describing WHAT, not WHY. BETTER: trace back to T3 exit if linked, or diagnose the T4 entry specifically.]

<!-- WRONG: Too many priorities -->
"priority_corners": [1, 2, 3, 4, 5, 6, 7]  [WRONG: max 2-3 priorities. Focus wins.]
</example>
```

### Phase 1 Tests
- `tests/test_driving_physics.py`: assert rubric text present in system prompt output
- Mock Claude API: verify golden example present in full prompt string
- Assert causal reasoning instruction in prompt for all skill levels

---

## Phase 2: Driving Line Foundation

**Can be parallelized with Phases 1 and 3. Blocks Phase 5.**

### 2.1 New Module: `cataclysm/gps_line.py`

Create this module from scratch. It has no dependencies on other new modules.

```python
from __future__ import annotations

import numpy as np
import pymap3d
from dataclasses import dataclass
from scipy.signal import savgol_filter
from scipy.interpolate import splprep, splev
from scipy.spatial import cKDTree


@dataclass
class GPSTrace:
    """ENU-projected, smoothed GPS trace for a single lap."""
    e: np.ndarray           # East component (meters from session origin)
    n: np.ndarray           # North component (meters from session origin)
    distance_m: np.ndarray  # Distance along track (matches existing 0.7m grid)
    lap_number: int


@dataclass
class ReferenceCenterline:
    """Multi-lap median reference line for within-session comparison."""
    e: np.ndarray               # East component
    n: np.ndarray               # North component
    kdtree: cKDTree             # For O(N log N) nearest-point queries
    n_laps_used: int            # Number of laps used to build reference
    left_edge: np.ndarray       # 2nd percentile lateral offset (track boundary estimate)
    right_edge: np.ndarray      # 98th percentile lateral offset


def gps_to_enu(
    lat: np.ndarray,
    lon: np.ndarray,
    lat0: float,
    lon0: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Convert GPS lat/lon to local East-North-Up coordinates.

    Never compute geometry in lat/lon — distances are distorted.
    All laps in a session share the same origin (first point of first lap).
    """
    alt = np.zeros_like(lat)
    e, n, _ = pymap3d.geodetic2enu(lat, lon, alt, lat0, lon0, 0.0)
    return e, n


def smooth_gps_trace(
    e: np.ndarray,
    n: np.ndarray,
    spacing_m: float = 0.7,
    window_m: float = 15.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Savitzky-Golay smoothing: reduces GPS noise, preserves corner geometry.

    window_m=15 at 0.7m spacing → window=21 points, polyorder=3.
    """
    window = max(int(window_m / spacing_m) | 1, 5)  # Ensure odd, minimum 5
    e_smooth = savgol_filter(e, window, polyorder=3)
    n_smooth = savgol_filter(n, window, polyorder=3)
    return e_smooth, n_smooth


def compute_reference_centerline(
    traces: list[GPSTrace],
    smoothing_factor: float = 0.5,
) -> ReferenceCenterline:
    """Median of multiple laps → robust reference line.

    Uses median (not mean) for robustness to off-track excursions.
    Requires at least 3 laps; more laps → better reference.
    """
    ...


def compute_lateral_offsets(
    lap: GPSTrace,
    ref: ReferenceCenterline,
) -> np.ndarray:
    """Signed perpendicular distance from lap trace to reference line.

    Positive = right of reference, Negative = left of reference.
    Uses KD-tree for O(N log N) performance + cross product for sign.
    """
    ...
```

**Required new dependency**: `pymap3d>=3.0` — add to `requirements.txt` and `pyproject.toml`.

### 2.2 New Module: `cataclysm/corner_line.py`

Corner-level analysis on top of the gps_line primitives.

```python
from __future__ import annotations

from dataclasses import dataclass
import numpy as np


LINE_ERROR_THRESHOLDS = {
    "early_apex_fraction": 0.40,   # Apex in first 40% of corner = early
    "late_apex_fraction": 0.65,    # Apex after 65% of corner = late
    "offset_threshold_m": 0.8,     # Meters deviation to flag an issue
    "consistency_threshold_m": 1.0, # SD above this = inconsistent line
}


@dataclass
class CornerLineProfile:
    """Line analysis for a single corner across all laps in a session."""
    corner_number: int
    n_laps: int

    # Session-median offsets at key points (meters from reference)
    d_entry_median: float
    d_turnin_median: float
    d_apex_median: float
    d_exit_median: float

    # Apex timing
    apex_fraction_median: float      # 0.0=entry, 1.0=exit; ideal ~0.50-0.65 for Type A
    effective_radius_m: float        # Path radius at apex

    # Per-lap consistency
    d_apex_sd: float                 # Lateral SD at apex across laps
    entry_speed_cv: float            # CV of entry speed (existing metric)
    apex_speed_cv: float             # CV of apex speed

    # Derived
    line_error_type: str             # "early_apex", "wide_entry", "pinched_exit", "good_line", etc.
    severity: str                    # "minor" <0.5m, "moderate" 0.5-1.5m, "major" >1.5m
    consistency_tier: str            # "expert" <0.3m, "consistent" 0.3-0.7m, "developing" 0.7-1.5m, "novice" >1.5m
    allen_berg_type: str             # "A" (before straight), "B" (after straight), "C" (linking)


def detect_apex(
    e: np.ndarray,
    n: np.ndarray,
    corner_start_idx: int,
    corner_end_idx: int,
) -> tuple[int, float]:
    """Apex = maximum curvature: κ = |x'y'' - y'x''| / (x'^2 + y'^2)^1.5.

    Returns (apex_index_absolute, apex_fraction_0_to_1).
    """
    ...


def classify_line_error(
    apex_fraction: float,
    d_entry: float,
    d_exit: float,
    ref_apex_fraction: float,
) -> tuple[str, str]:
    """Rule-based classification: (error_type, severity)."""
    ...


def analyze_corner_lines(
    traces: list[GPSTrace],
    ref: ReferenceCenterline,
    corners: list[Corner],     # existing Corner dataclass from corners.py
    track_db_corners: list,    # corner metadata from track_db.py
) -> list[CornerLineProfile]:
    """Main entry point: analyze all corners across all laps."""
    ...
```

### 2.3 GPS Quality Gate

File: `cataclysm/corner_line.py` or `cataclysm/gps_line.py`

Line analysis requires GPS grade A or B (existing `GPSQualityReport` from `gps_quality.py`). Below that, suppress line coaching but keep speed/brake analysis.

```python
def should_enable_line_analysis(gps_quality: GPSQualityReport) -> bool:
    """Only enable for grade A or B sessions."""
    return gps_quality.grade in ("A", "B")
```

### 2.4 Integrate Line Data into Coaching Prompt

File: `cataclysm/coaching.py` — `_build_user_message()`

Add a `<line_analysis>` section to the XML-structured user message:

```python
if line_profiles and enable_line_coaching:
    sections.append("<line_analysis>")
    for profile in line_profiles:
        sections.append(f"""
  <corner number="{profile.corner_number}" type="{profile.allen_berg_type}">
    <entry_offset>{profile.d_entry_median:+.1f}m from reference</entry_offset>
    <apex_offset>{profile.d_apex_median:+.1f}m | fraction {profile.apex_fraction_median:.0%} (ideal: 50-65% for Type A)</apex_offset>
    <exit_offset>{profile.d_exit_median:+.1f}m from reference</exit_offset>
    <error_type>{profile.line_error_type} ({profile.severity})</error_type>
    <consistency>apex SD {profile.d_apex_sd:.2f}m ({profile.consistency_tier})</consistency>
  </corner>""")
    sections.append("</line_analysis>")
```

Add line analysis instructions to `driving_physics.py` system prompt:
```
When LINE ANALYSIS data is present, integrate it with speed/brake analysis. A corner with good brake data but an early apex error costs time on the exit — report these together as one issue, not two separate observations.
```

### 2.5 Unit Tests

File: `tests/test_gps_line.py` (new)

```python
def test_gps_to_enu_roundtrip():
    """Convert to ENU and back, verify sub-millimeter accuracy."""

def test_smooth_gps_trace_preserves_shape():
    """Smoothed trace should stay within 0.5m of original on slow sections."""

def test_lateral_offset_sign_convention():
    """Point known to be left of reference → negative offset."""

def test_reference_centerline_median_robustness():
    """Outlier lap (off-track excursion) should not distort reference."""

def test_apex_detection_synthetic_corner():
    """Circular arc: apex at midpoint = fraction 0.5."""
```

File: `tests/test_corner_line.py` (new)

```python
def test_classify_early_apex():
    """apex_fraction=0.3 → 'early_apex'."""

def test_gps_quality_gate():
    """Grade C session → should_enable_line_analysis() returns False."""
```

---

## Phase 3: Inter-Corner Causal Chains

**Can be parallelized with Phases 1 and 2. Blocks nothing else, but enhances Phase 6.**

### 3.1 New Module: `cataclysm/causal_chains.py`

No new dependencies — numpy + scipy only (already in project).

```python
from __future__ import annotations

from dataclasses import dataclass, field
import numpy as np
from scipy.stats import pearsonr


RECOVERY_THRESHOLDS = {
    "independent": 0.90,    # Corner pair is independent
    "weak": 0.70,           # Weak link — exit speed matters somewhat
    "moderate": 0.50,       # Moderate link — exit speed matters a lot
    "tight": 0.30,          # Tight coupling — essentially one complex
}


@dataclass
class CornerLink:
    """Relationship between two consecutive corners."""
    from_corner: int
    to_corner: int
    gap_distance_m: float
    recovery_fraction: float     # Physics-based: how much speed deficit recovers in gap
    correlation_r: float         # Pearson r: exit_speed[n] vs min_speed[n+1] across laps
    correlation_p: float         # p-value of correlation
    link_strength: str           # "independent" | "weak" | "moderate" | "tight"


@dataclass
class CascadeEffect:
    """Per-lap attribution of time loss to self vs inherited causes."""
    lap_number: int
    from_corner: int
    to_corner: int
    total_loss_s: float          # Total time loss at to_corner vs best lap
    inherited_loss_s: float      # Portion attributable to from_corner's exit speed
    self_caused_loss_s: float    # Portion caused by to_corner itself
    inheritance_fraction: float  # inherited / total; >0.6 = cascading


@dataclass
class CausalChain:
    """A connected sequence of linked corners with a shared root cause."""
    corners: list[int]           # e.g., [3, 4, 5]
    root_corner: int             # Corner where the cascade originates
    total_cascade_s: float       # Total time cost including all downstream effects
    self_time_s: float           # Root corner's own time loss
    downstream_time_s: float     # Downstream cascade from root corner
    root_cause_type: str         # "late_brake" | "early_apex" | "over_slowing" | "under_rotation"
    affected_laps_pct: float     # % of laps where cascade is detected
    coaching_summary: str        # Natural language: "T3 early apex forces T4 entry wide, costs 0.26s"


@dataclass
class SessionCausalAnalysis:
    """Session-level result: all links, chains, and the TimeKiller."""
    corner_links: list[CornerLink]
    cascade_effects: list[CascadeEffect]
    chains: list[CausalChain]
    timekiller: CausalChain | None  # Chain with highest total_cascade_s


def compute_recovery_fraction(
    exit_speed_mps: float,
    entry_speed_next_mps: float,
    gap_distance_m: float,
    max_accel_g: float = 0.5,
) -> float:
    """Physics: how much of a speed deficit recovers over a gap?

    Uses v^2 = v0^2 + 2*a*d. Returns 0.0 (tight coupling) to 1.0 (independent).
    """
    if exit_speed_mps >= entry_speed_next_mps:
        return 1.0
    accel_mps2 = max_accel_g * 9.81
    achievable_sq = exit_speed_mps**2 + 2 * accel_mps2 * gap_distance_m
    achievable = achievable_sq**0.5
    speed_deficit = entry_speed_next_mps - exit_speed_mps
    speed_recovered = min(achievable, entry_speed_next_mps) - exit_speed_mps
    return speed_recovered / speed_deficit if speed_deficit > 0 else 1.0


def detect_corner_links(
    corners: list[Corner],
    per_lap_stats: list[dict],    # existing per-lap corner stats from corner_analysis.py
) -> list[CornerLink]:
    """Hybrid detection: physics recovery fraction + Pearson correlation.

    A link is flagged when BOTH methods agree (recovery < 0.7 AND |r| > 0.6).
    """
    ...


def compute_cascade_effects(
    links: list[CornerLink],
    per_lap_stats: list[dict],
    best_lap_stats: dict,
) -> list[CascadeEffect]:
    """Per-lap attribution: inherited_loss = speed_deficit * (1 - recovery_fraction).

    Uses: T4_inherited = delta_T3_exit * (1 - recovery_fraction) / gap_time_per_mps
    """
    ...


def build_causal_chains(
    links: list[CornerLink],
    cascade_effects: list[CascadeEffect],
) -> list[CausalChain]:
    """Trace connected linked pairs into chains. Identify TimeKiller."""
    ...


def analyze_session_causal_chains(
    corners: list[Corner],
    per_lap_stats: list[dict],
    best_lap_stats: dict,
) -> SessionCausalAnalysis:
    """Main entry point. Called from corner_analysis.py after per-corner analysis."""
    links = detect_corner_links(corners, per_lap_stats)
    cascades = compute_cascade_effects(links, per_lap_stats, best_lap_stats)
    chains = build_causal_chains(links, cascades)
    timekiller = max(chains, key=lambda c: c.total_cascade_s) if chains else None
    return SessionCausalAnalysis(links, cascades, chains, timekiller)
```

### 3.2 Integration into Analysis Pipeline

File: `cataclysm/corner_analysis.py` — call `analyze_session_causal_chains()` at the end of `analyze_corners()` and attach the `SessionCausalAnalysis` to the session result.

### 3.3 Causal Chain Data in Coaching Prompt

File: `cataclysm/coaching.py` — add `<causal_chains>` section to user message:

```python
if causal_analysis and causal_analysis.chains:
    sections.append("<causal_chains>")
    if causal_analysis.timekiller:
        tk = causal_analysis.timekiller
        sections.append(f"""
  <timekiller>
    <corners>{" -> ".join(str(c) for c in tk.corners)}</corners>
    <root_corner>T{tk.root_corner} ({tk.root_cause_type})</root_corner>
    <total_impact>{tk.total_cascade_s:.2f}s ({tk.downstream_time_s:.2f}s cascade)</total_impact>
    <affected_laps>{tk.affected_laps_pct:.0%} of laps</affected_laps>
    <summary>{tk.coaching_summary}</summary>
  </timekiller>""")
    sections.append("</causal_chains>")
```

File: `cataclysm/driving_physics.py` — add TimeKiller coaching instruction:
```
When CAUSAL CHAIN data is present, the TimeKiller is the highest-priority coaching item. Frame it as: "Fix [root corner] and [downstream corners] improve automatically." Do NOT list downstream corners as separate problems — they are symptoms of the root cause.
```

### 3.4 Unit Tests

File: `tests/test_causal_chains.py` (new)

```python
def test_recovery_fraction_independent():
    """Long gap: fraction should be ~1.0."""

def test_recovery_fraction_tight_coupling():
    """Zero gap: fraction should be ~0.0."""

def test_cascade_attribution_dominated_by_upstream():
    """When inheritance > 60%, self_caused should be near zero."""

def test_timekiller_is_highest_impact_chain():
    """SessionCausalAnalysis.timekiller should have max total_cascade_s."""

def test_no_chains_when_corners_independent():
    """All recovery fractions > 0.9 → empty chains list."""
```

---

## Phase 4: Adaptive Skill Detection

**Can be parallelized with Phases 1, 2, and 3. Enhances Phase 6.**

### 4.1 New Module: `cataclysm/driver_archetypes.py`

Seven archetypes derived from telemetry. Uses only metrics already computed by `corner_analysis.py`.

```python
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Archetype(str, Enum):
    EARLY_BRAKER = "early_braker"
    LATE_BRAKER = "late_braker"
    COASTER = "coaster"
    SMOOTH_OPERATOR = "smooth_operator"
    AGGRESSIVE_ROTATOR = "aggressive_rotator"
    CONSERVATIVE_LINER = "conservative_liner"
    TRAIL_BRAZER = "trail_brazer"


ARCHETYPE_COACHING_FOCUS: dict[Archetype, str] = {
    Archetype.EARLY_BRAKER: "Confidence-building: brake deeper, use full deceleration",
    Archetype.LATE_BRAKER: "Patience: commit to corner entry position before throttle",
    Archetype.COASTER: "Corner flow: release brake progressively into turn, no coast phase",
    Archetype.SMOOTH_OPERATOR: "Pushing the limit: you have headroom, trust the data",
    Archetype.AGGRESSIVE_ROTATOR: "Smoothness: let the car rotate, reduce abrupt inputs",
    Archetype.CONSERVATIVE_LINER: "Track width: use all of the road — entry, apex, exit",
    Archetype.TRAIL_BRAZER: "Fine-tuning: refine brake release point and rotation balance",
}


@dataclass
class ArchetypeResult:
    primary: Archetype
    secondary: Archetype | None
    confidence: float              # 0.0-1.0 based on signal strength
    coaching_focus: str


def detect_archetype(corner_stats: list[dict]) -> ArchetypeResult:
    """6-dimension scoring using metrics from corner_analysis.py.

    Dimensions: brake_timing_delta, brake_force_g, coast_duration_s,
    speed_utilization_pct, input_smoothness, consistency_cv.
    Each maps to 1-2 archetypes. Highest score wins.
    """
    ...
```

### 4.2 New Module: `cataclysm/skill_detection.py`

Auto-detect skill level from telemetry — no explicit user declaration needed.

```python
from __future__ import annotations

from dataclasses import dataclass

SKILL_THRESHOLDS = {
    "lap_time_cv": {"novice": 3.0, "intermediate": 1.5},      # % CV
    "brake_sd_avg_m": {"novice": 12.0, "intermediate": 5.0},  # meters
    "min_speed_sd_avg_mph": {"novice": 4.0, "intermediate": 2.0},
    "peak_brake_g": {"novice": 0.5, "intermediate": 0.8},      # G
    "trail_braking_pct": {"novice": 20.0, "intermediate": 60.0},
    "throttle_commit_sd_m": {"novice": 15.0, "intermediate": 8.0},
}


@dataclass
class SkillAssessment:
    detected_level: str            # "novice" | "intermediate" | "advanced"
    confidence: float              # 0.0-1.0
    breakdown: dict[str, str]      # per-metric assessment
    user_declared: str | None      # override if user set it explicitly


def detect_skill_level(
    session_stats: dict,
    user_declared: str | None = None,
) -> SkillAssessment:
    """Score 6 dimensions, vote to determine level.

    User-declared level is respected if confidence > 0.6 in detected direction.
    Blended when user says "intermediate" but data shows "advanced" patterns.
    """
    ...
```

### 4.3 External Focus Translation in Prompts

File: `cataclysm/driving_physics.py` — add to `_SKILL_PROMPTS` per skill level

The translation table to bake into prompt instructions (embedded as reference for the LLM):

```
EXTERNAL FOCUS LANGUAGE (mandatory — use environment/car as reference, not body):
  AVOID: "press the brake harder" → USE: "the car should slow more aggressively before the marker"
  AVOID: "turn the wheel earlier" → USE: "point the car toward the inside curb sooner"
  AVOID: "squeeze the throttle"   → USE: "let the car accelerate as you unwind the wheel"
  AVOID: "relax your hands"       → USE: "let the car settle before committing to the apex"

For NOVICE skill level — also use analogies:
  Trail braking: "like squeezing water from a sponge — gradual release, not sudden"
  Weight transfer: "the car is a bowl of soup — keep it from spilling through the corner"
  Racing line: "like skiing — set up wide, carve through the apex, open up the exit"
  Throttle: "like accelerating in the rain — progressive, not sudden"
```

### 4.4 Archetype and Skill Data in Coaching Prompt

File: `cataclysm/coaching.py` — add to `<coaching_instructions>` XML section:

```python
sections.append(f"""
<driver_profile>
  <skill_level>{skill_assessment.detected_level} (confidence: {skill_assessment.confidence:.0%})</skill_level>
  <archetype>{archetype.primary.value}: {archetype.coaching_focus}</archetype>
  <max_priorities>{MAX_PRIORITY_CORNERS[skill_assessment.detected_level]}</max_priorities>
</driver_profile>""")
```

File: `cataclysm/driving_physics.py` — add cognitive load instruction:
```
Respect the max_priorities limit in driver_profile. Novice: 2 priorities maximum, each with a single concrete action. Intermediate: 3 priorities with some context. Advanced: up to 4 priorities with inter-corner chain analysis included.
```

### 4.5 Unit Tests

File: `tests/test_skill_detection.py` (new)

```python
def test_novice_detection_from_high_variance():
    """Brake SD > 12m, CV > 3% → detected as novice."""

def test_advanced_detection_from_low_variance():
    """Brake SD < 5m, trail braking > 60% → detected as advanced."""

def test_user_declared_respected():
    """User says intermediate, data shows intermediate → respect declaration."""

def test_archetype_coaster_detected():
    """Long coast phase, late throttle commit → COASTER archetype."""
```

---

## Phase 5: Line Visualization (Frontend)

**Blocked by Phase 2. Can be parallelized with Phases 3, 4, and 6.**

### 5.1 Speed-Colored Track Map

File: `frontend/src/components/HeroTrackMap.tsx` — extend existing component

Add a Canvas 2D rendering layer for speed-colored GPS trace. Draw each inter-sample segment as a colored line using a blue (slow) → red (fast) gradient. Use `requestAnimationFrame` for smooth rendering.

```typescript
// New function in HeroTrackMap.tsx
function drawSpeedColoredTrace(
  ctx: CanvasRenderingContext2D,
  points: Array<{x: number, y: number, speed: number}>,
  speedMin: number,
  speedMax: number,
): void {
  // Draw each segment individually with interpolated color
  // Color = lerpColor(BLUE, RED, (speed - speedMin) / (speedMax - speedMin))
}
```

### 5.2 Two-Lap GPS Overlay

File: `HeroTrackMap.tsx` — add optional `compareLap` prop

When comparison lap data is available (existing deep-dive comparison feature), render both traces on the map with different colors. Semi-transparent rendering shows overlap vs divergence. Thicker stroke = currently focused lap.

### 5.3 Lateral Offset Chart

File: New `frontend/src/components/LateralOffsetChart.tsx`

D3.js SVG chart (same pattern as existing `SpeedTrace.tsx`):
- X-axis: distance along track (shared domain with speed trace)
- Y-axis: lateral offset from reference (meters)
- Shaded band: estimated track boundaries (left_edge / right_edge from `ReferenceCenterline`)
- Vertical lines: corner entry/exit boundaries
- Zero line: reference centerline
- Two laps overlaid when comparison mode active

### 5.4 Bidirectional Hover Linking

File: `HeroTrackMap.tsx`, `LateralOffsetChart.tsx`, existing `SpeedTrace.tsx`

All charts share a distance-domain cursor via React context (existing `CrosshairContext` or equivalent). Hovering on any chart dispatches a `setDistanceCursor(d)` action. All other charts and the track map position-dot respond. Cataclysm already uses the distance domain for all data — this is an architectural fit.

### 5.5 Corner Detail Cards

File: New `frontend/src/components/CornerDetailCard.tsx`

Per-corner modal/panel showing:
- Mini track map: zoomed view of single corner, reference line (dashed) vs actual line (solid), entry/apex/exit markers
- Metrics: entry offset, apex offset, exit offset, apex fraction vs ideal
- Error type badge: "Early Apex — Moderate"
- Consistency tier badge
- Allen Berg type (A/B/C) with brief explanation

### 5.6 Backend API Endpoint

File: `backend/api/routes/` — add line analysis endpoint or extend existing session endpoint

Expose `CornerLineProfile` data from `session.line_analysis` in the API response. Add to `backend/api/schemas/session.py`:

```python
class CornerLineData(BaseModel):
    corner_number: int
    d_entry_median: float
    d_apex_median: float
    d_exit_median: float
    apex_fraction_median: float
    line_error_type: str
    severity: str
    consistency_tier: str
    allen_berg_type: str
```

### Phase 5 QA (Playwright MCP — BLOCKING before merge)
- Speed-colored track map renders on session with GPS data
- Two-lap overlay shows distinct colors, both traces visible
- Lateral offset chart renders with shaded boundaries
- Hover on speed trace → track map position dot moves to correct position
- Hover on track map → speed trace crosshair moves
- Corner detail card opens when corner is clicked
- Mobile (Pixel 7, iPhone 14): touch-hold activates crosshair, charts scale correctly, no horizontal overflow

---

## Phase 6: Longitudinal Intelligence

**Blocked by nothing, but benefits from Phase 3 (causal chains add to memory) and Phase 4 (skill level context). Can be started in parallel.**

### 6.1 Database Schema

File: `backend/models.py` — new SQLAlchemy models

```python
class CoachingMemory(Base):
    """Per-session coaching summary for longitudinal analysis."""
    __tablename__ = "coaching_memory"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    session_id: Mapped[str] = mapped_column(unique=True)
    track_name: Mapped[str] = mapped_column(index=True)
    session_date: Mapped[datetime]
    best_lap_s: Mapped[float]
    top3_avg_s: Mapped[float]
    corner_grades: Mapped[dict] = mapped_column(JSON)    # {corner_num: {criterion: grade}}
    priority_corners: Mapped[list] = mapped_column(JSON)
    key_strengths: Mapped[list] = mapped_column(JSON)    # max 3 strings
    key_weaknesses: Mapped[list] = mapped_column(JSON)   # max 3 strings
    drills_assigned: Mapped[list] = mapped_column(JSON)
    conditions: Mapped[str | None]
    equipment: Mapped[str | None]
    timekiller_corner: Mapped[int | None]                # From causal chain analysis
    detected_archetype: Mapped[str | None]


class DriverProfile(Base):
    """Longitudinal driver profile per track (aggregated from CoachingMemory)."""
    __tablename__ = "driver_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    track_name: Mapped[str]
    total_sessions: Mapped[int]
    best_ever_lap_s: Mapped[float]
    best_ever_session_id: Mapped[str]
    lap_time_progression: Mapped[list] = mapped_column(JSON)
    corner_mastery: Mapped[dict] = mapped_column(JSON)
    recurring_weaknesses: Mapped[list] = mapped_column(JSON)
    improving_areas: Mapped[list] = mapped_column(JSON)
    plateaued_areas: Mapped[list] = mapped_column(JSON)
    __table_args__ = (UniqueConstraint("user_id", "track_name"),)
```

Migration: `alembic revision --autogenerate -m "add coaching_memory and driver_profiles"`

### 6.2 New Module: `cataclysm/coaching_memory.py`

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class SessionMemoryExtract:
    """Extracted from a completed coaching report for persistence."""
    session_id: str
    track_name: str
    session_date: datetime
    best_lap_s: float
    priority_corners: list[int]
    corner_grades: dict[int, dict[str, str]]
    key_strengths: list[str]         # Extract top 3 from report patterns
    key_weaknesses: list[str]        # Extract top 3 improvement areas
    drills_assigned: list[str]       # Extract from report drills field
    conditions: str | None
    equipment: str | None


def extract_memory_from_report(
    report: CoachingReport,
    session_metadata: dict,
) -> SessionMemoryExtract:
    """Parse a completed coaching report into structured memory."""
    ...


def build_history_prompt_section(
    memories: list[CoachingMemory],
    driver_profile: DriverProfile | None,
    current_track: str,
) -> str:
    """Format history for injection into coaching prompt (~2,000 tokens budget).

    Uses hierarchical summarization: recent session verbatim, older sessions compressed.
    """
    ...
```

### 6.3 New Module: `cataclysm/corners_gained.py`

Adapted from Arccos Golf "Strokes Gained" — decomposes the gap to target lap time by corner.

```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CornersGainedBreakdown:
    """How much time each corner/phase contributes to the gap from target."""
    target_lap_s: float
    current_best_s: float
    total_gap_s: float

    # Per-corner attribution
    braking_gains: dict[int, float]    # {corner: seconds_available}
    min_speed_gains: dict[int, float]
    throttle_gains: dict[int, float]
    line_gains: dict[int, float]       # When line analysis available
    consistency_gains: dict[int, float]

    # Top opportunities
    top_3_opportunities: list[tuple[int, str, float]]  # (corner, description, seconds)
    coaching_summary: str  # "To break 1:40: T5 braking (0.3s), T1 entry (0.2s), T8 consistency (0.15s)"


def compute_corners_gained(
    session_stats: dict,
    target_lap_s: float,
    track_db_corners: list,
) -> CornersGainedBreakdown:
    """Decompose gap to target into per-corner, per-phase opportunities.

    Uses sensitivity analysis: vary each component independently,
    sum contributions across all laps to estimate total gain.
    """
    ...
```

### 6.4 New Module: `cataclysm/flow_lap.py`

```python
from __future__ import annotations

from dataclasses import dataclass


FLOW_LAP_WEIGHTS = {
    "proximity_to_pb": 0.45,   # All corners within X% of personal best
    "balance": 0.25,           # No single corner dominates the deficit
    "smoothness": 0.20,        # Low variance in driving inputs
    "timing": 0.10,            # Mid-session placement (more likely to be flow)
}


@dataclass
class FlowLapResult:
    flow_laps: list[int]       # Lap numbers identified as flow laps
    scores: dict[int, float]   # Per-lap composite score (0.0-1.0)
    threshold: float           # Score >= this is "flow" (default 0.75)


def detect_flow_laps(
    per_lap_stats: list[dict],
    best_lap_stats: dict,
    session_laps: int,
) -> FlowLapResult:
    """Identify peak performance laps using 4-criteria composite score."""
    ...
```

### 6.5 New Module: `cataclysm/milestones.py`

```python
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class MilestoneType(str, Enum):
    PERSONAL_BEST = "personal_best"
    CORNER_PB = "corner_pb"
    CONSISTENCY_UNLOCK = "consistency_unlock"
    BRAKE_POINT_IMPROVEMENT = "brake_point_improvement"
    SUB_LAP_TIME = "sub_lap_time"
    TECHNIQUE_UNLOCK = "technique_unlock"   # e.g., trail braking first appears
    FLOW_STATE = "flow_state"


@dataclass
class Milestone:
    type: MilestoneType
    description: str            # "New personal best: 1:42.3 (-0.8s)"
    magnitude: float            # Size of improvement
    corner: int | None          # None for session-wide milestones


def detect_milestones(
    current_session: CoachingMemory,
    history: list[CoachingMemory],
    flow_result: FlowLapResult | None,
) -> list[Milestone]:
    """Compare current session to history to detect milestone events."""
    ...
```

### 6.6 Pre-Session Briefing Endpoint

File: `backend/api/routes/` — new endpoint `GET /sessions/briefing?track={name}`

Returns a briefing for a driver returning to a track. Uses `DriverProfile` and most recent `CoachingMemory` for the track. Returns JSON with:
- `focus_areas`: list of 1-3 priority items from last session
- `progress_summary`: "Your T5 brake point moved 15m later over 4 sessions"
- `drill_reminder`: drills assigned last session
- `lap_target`: suggested stretch goal based on progression trend

File: New `cataclysm/briefing.py` — `generate_briefing()` function.

### Phase 6 Tests
- `tests/test_coaching_memory.py`: assert memory extraction from mock report
- `tests/test_corners_gained.py`: assert top_3_opportunities sums <= total_gap_s
- `tests/test_flow_lap.py`: mock session where laps 8 and 12 are near PB → detected as flow laps
- `tests/test_milestones.py`: assert new PB triggers PERSONAL_BEST milestone

---

## Phase 7: GPS+IMU Fusion (Future Enhancement)

**Blocked by Phase 2 (needs gps_line.py). Not parallelizable with Phase 2 — enhances it after.**

This phase improves line accuracy from ~0.5m to ~0.2-0.3m. It is NOT a prerequisite for Phase 2. Phase 2 is already viable at 0.5m CEP.

### 7.1 Savitzky-Golay First (Simple, High Value)

File: `cataclysm/gps_line.py` — `smooth_gps_trace()` is already designed for this

The SG filter at `window_m=15` reduces GPS noise from ~0.5m to ~0.2-0.3m RMS without any IMU data. This should be validated on real sessions before pursuing EKF. **If SG smoothing is sufficient for line analysis quality, skip the EKF entirely.**

### 7.2 CTRV-EKF + RTS Smoother (Complex, Modest Improvement)

Required new dependency: `filterpy>=1.4` — add to `requirements.txt` only when this phase starts.

File: `cataclysm/gps_line.py` — add `fuse_gps_imu()` function

State vector: `[x_east, y_north, psi, v, psi_dot]` (5 states)

```python
def fuse_gps_imu(
    lat: np.ndarray,
    lon: np.ndarray,
    speed_mps: np.ndarray,
    yaw_rate_dps: np.ndarray,
    heading_deg: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """CTRV-EKF forward pass + RTS backward smoother.

    Forward pass: predict from CTRV model, update with GPS + yaw_rate.
    Backward pass: RTS smoother uses all future GPS to refine past estimates.
    Returns smoothed (e, n) in local ENU coordinates.

    Implementation notes:
    - Uses filterpy.kalman.ExtendedKalmanFilter + rts_smoother()
    - Process noise Q: tuned empirically (yaw_rate noise ~2 dps, speed ~0.1 m/s)
    - Measurement noise R: GPS position ~0.5m, speed 0.05 m/s, yaw_rate 2 dps
    - Handle psi_dot ≈ 0 (straight line) separately in CTRV model to avoid division by zero
    """
    ...
```

Realistic accuracy improvement over SG-only: 0.1-0.3m additional reduction. This narrows detection threshold for 0.3-0.5m lateral offset differences — useful for advanced driver line comparison.

---

## Dependencies and Parallelization

```
Phase 0 (Prompt Quick Wins)     — No dependencies. Start immediately.
Phase 1 (Grading Overhaul)      — No dependencies. Parallel with 0.
Phase 2 (Driving Line Foundation) — No dependencies. Parallel with 0, 1.
Phase 3 (Causal Chains)         — No dependencies. Parallel with 0, 1, 2.
Phase 4 (Adaptive Skill)        — No dependencies. Parallel with 0, 1, 2, 3.
Phase 5 (Line Visualization)    — BLOCKED BY Phase 2.
Phase 6 (Longitudinal)          — No hard blockers. Parallel with 2, 3, 4.
Phase 7 (GPS+IMU Fusion)        — BLOCKED BY Phase 2 (needs gps_line.py).
```

**Recommended execution order:**
- Sprint 1: Phases 0 + 1 in parallel (pure prompt work, fast iteration)
- Sprint 2: Phases 2 + 3 + 4 in parallel (new Python modules, independent)
- Sprint 3: Phases 5 + 6 in parallel (frontend unblocked after Phase 2)
- Sprint 4: Phase 7 only if Phase 2 line analysis shows quality needs improvement

---

## Testing Strategy Per Phase

| Phase | New Test Files | Key Coverage |
|-------|---------------|--------------|
| 0 | `tests/test_coaching.py` (extend) | temperature=0.3 in API call; novice priority cap |
| 1 | `tests/test_driving_physics.py` (extend) | rubric text present; golden examples in prompt |
| 2 | `tests/test_gps_line.py` (new), `tests/test_corner_line.py` (new) | ENU roundtrip; lateral offset sign; GPS quality gate |
| 3 | `tests/test_causal_chains.py` (new) | recovery_fraction physics; cascade attribution; TimeKiller selection |
| 4 | `tests/test_skill_detection.py` (new), `tests/test_driver_archetypes.py` (new) | thresholds; voting; archetype signatures |
| 5 | Playwright MCP QA (blocking before merge) | All visual components; mobile; hover sync |
| 6 | `tests/test_coaching_memory.py`, `tests/test_corners_gained.py`, `tests/test_flow_lap.py`, `tests/test_milestones.py` (all new) | Memory extraction; gap decomposition; flow scoring; milestone detection |
| 7 | `tests/test_gps_line.py` (extend) | EKF convergence; RTS smoother improves over raw GPS |

**Coverage rule**: Every new module gets a `tests/test_<module>.py`. Use synthetic data fixtures — never real session files. Mock the Claude API in all coaching tests.

**Quality gates before any merge**:
1. `ruff check cataclysm/ tests/ backend/` — zero errors
2. `ruff format cataclysm/ tests/ backend/`
3. `dmypy run -- cataclysm/ backend/` — zero type errors
4. `pytest tests/ backend/tests/ -v` — all pass
5. Dispatch `superpowers:code-reviewer` agent
6. If any frontend files changed: Playwright MCP QA on desktop + Pixel 7 + iPhone 14
