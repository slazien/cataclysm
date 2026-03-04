# Inter-Corner Causal Chain Detection & Root Cause Analysis

**Date**: 2026-03-04
**Iteration**: 3 of 3 (Ralph Loop)
**Focus**: Inter-Corner Dependencies, Causal Chain Detection, Root Cause Analysis Algorithms

---

## Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Topic 1: Inter-Corner Dependencies in Motorsport](#2-topic-1-inter-corner-dependencies-in-motorsport)
3. [Topic 2: Root Cause Analysis Algorithms](#3-topic-2-root-cause-analysis-algorithms)
4. [Topic 3: Corner Combination Detection](#4-topic-3-corner-combination-detection)
5. [Topic 4: Exit-Entry Speed Correlation](#5-topic-4-exit-entry-speed-correlation)
6. [Topic 5: Implementation Patterns](#6-topic-5-implementation-patterns)
7. [Proposed Algorithm Design](#7-proposed-algorithm-design)
8. [Coaching Report Integration](#8-coaching-report-integration)
9. [Implementation Roadmap](#9-implementation-roadmap)

---

## 1. Executive Summary

Our biggest competitive gap versus Track Titan is the inability to detect how mistakes cascade across corners. Currently, Cataclysm grades each corner independently -- if a driver blows T3 and that ruins T4, we report them as two separate problems when the real fix is just T3.

Track Titan's "TimeKiller" feature addresses exactly this: it traces root causes through multiple corners, identifying that "the root cause started two corners before when the driver didn't straighten up the car correctly for braking, which then made the driver run wide into subsequent corners and delayed throttle application" ([Track Titan Nov 2025 Update](https://www.tracktitan.io/post/november-2025-update-coaching-flows)).

This document synthesizes research across racing engineering, causal inference, and algorithm design to propose a practical implementation for Cataclysm. The key insight: we do not need heavy-weight causal ML libraries. The physics of corner-to-corner speed propagation is well-understood and deterministic enough to implement with straightforward kinematics + correlation analysis on the data we already have.

---

## 2. Topic 1: Inter-Corner Dependencies in Motorsport

### 2.1 How Racing Engineers Identify Corner-to-Corner Dependencies

Professional race engineers use a systematic approach to identify inter-corner dependencies:

**Corner Priority Hierarchy** ([Driver61 - Prioritising Corners](https://driver61.com/uni/prioritising-corners/)):
1. Corners before long straights (highest priority -- exit speed multiplied over distance)
2. Next fastest corners before straights
3. Corners after straights (entry speed matters less)
4. Corners leading into other corners (lowest individual priority, but highest cascade risk)

The critical insight: "the faster a car is travelling, the more difficult it is to accelerate, and so any loss of speed at entry is harder to make up again." A 5 mph deficit exiting a fast corner produces greater time loss than the same deficit from a slow corner due to higher aerodynamic drag and taller gear ratios.

**Connected Corner Decision Framework** ([Blayze - Complex Corners](https://blayze.io/blog/car-racing/complex-corners)):
Professional coaches use a "work backwards" approach:
1. Identify the priority exit (usually the last corner before a straight)
2. Ask: "Which part of this corner allows me to be faster for a longer period?"
3. Test whether sacrificing the preceding corner measurably helps the priority corner
4. At COTA T6-T9, testing showed sacrificing T7 exit speed provided NO advantage in T8 (the corners were too different), but setting up correctly for T7 entry via T6 sacrifice WAS significantly faster

This means not all adjacent corners are actually coupled -- physical testing or data analysis is needed to determine real dependencies.

### 2.2 The "Connected Corners" Concept

Corners are "connected" when:
1. The straight between them is too short for the car to reach a natural terminal speed
2. Exit speed from corner N directly constrains entry speed at corner N+1
3. The racing line through corner N physically positions the car for (or against) the optimal entry to corner N+1

**Types of corner connections** ([Allen Berg Racing Schools](https://www.allenbergracingschools.com/expert-advice/race-tracks-three-corners-types/)):
- **Chicanes**: Two opposite-direction corners with zero straight between them. Maximum coupling.
- **Esses**: Same-direction undulations where rhythm matters more than individual speed. ([Blayze VIR Esses](https://blayze.io/blog/car-racing/uphill-esses-and-oak-tree-at-vir))
- **Corner Complexes**: 2-4 corners with short straights where exit of each feeds the next.
- **Isolated Corners**: Separated by straights long enough for full speed recovery. No cascading.

### 2.3 How Competitors Detect Inter-Corner Effects

**Track Titan's TimeKiller** ([Track Titan](https://www.tracktitan.io/)):
- Uses a "proprietary simulation engine" that runs thousands of scenarios
- Determines how much each mistake costs "down to the thousandth of a second"
- Key capability: traces root cause through multiple corners -- identifies that a mistake 2 corners back caused current corner's problem
- Their "Coaching Flows" provide root cause analysis "within seconds" by finding "the biggest root cause of time-loss" rather than listing mistakes corner by corner
- Reduced simulation time from 9 seconds to under 4 seconds (Dec 2025 optimization)

**Full Grip Motorsport** ([Full Grip Telemetry](https://www.fullgripmotorsport.com/telemetry)):
- Analyzes "corner linking" as an explicit metric alongside entry/apex/exit speed
- Uses 19 specialized detectors examining braking, throttle, steering, racing line
- Identifies over 100 types of improvement opportunities
- Provides "corner-by-corner optimization with auto-detected corner definitions"
- Evaluates "track width usage, apex positioning, entry/exit optimization"

**Key Competitive Gap**: Both Track Titan and Full Grip explicitly analyze corner-to-corner relationships. Cataclysm currently treats each corner as independent. This is the single most impactful feature gap to close.

### 2.4 Professional Race Engineering Methods

**MoTec/Professional Approach** ([MoTec Telemetry Guide](https://trinacriasimracing.wordpress.com/beginners-guide-to-telemetry-analysis-motec/)):
- Engineers use "Delta - Section [s]" channels showing time gained/lost as a function of distance
- Compare laps on a distance scale to see braking point, entry, apex, exit markers overlaid
- Key insight: looking at where the delta TIME changes, not just where speed differs
- A speed difference at corner exit produces an expanding time delta through the following straight
- The delta STOPS expanding when speeds converge (at the next brake point or speed-limited section)

**HP Academy Method** ([HP Academy](https://www.hpacademy.com/technical-articles/going-faster-with-data-analysis/)):
- Use Excel micro-sector analysis: divide track into small distance segments
- Compare chronometric (time) performance in each micro-sector vs reference lap
- Identifies not just WHERE time is lost, but how losses in one sector propagate to the next

---

## 3. Topic 2: Root Cause Analysis Algorithms

### 3.1 Causal Inference for Time-Series Data

**Granger Causality** ([Wikipedia](https://en.wikipedia.org/wiki/Granger_causality), [PMC Review](https://pmc.ncbi.nlm.nih.gov/articles/PMC10571505/)):
- Core idea: Variable X "Granger-causes" Y if past values of X improve predictions of Y beyond what past values of Y alone provide
- Originally developed for economics (1969), now widely used in neuroscience and time-series analysis
- **Applicability to our problem**: Limited for direct corner-to-corner analysis because:
  - We have structured sequential data (corner N always precedes corner N+1), not general time series
  - The causal direction is known a priori (exit speed of T3 -> entry speed of T4, never the reverse)
  - We have small sample sizes per session (8-20 laps) -- Granger tests need substantial data
- **Better fit**: Cross-correlation analysis at specific lags, which we can compute with `statsmodels.tsa.stattools.ccf` ([Statsmodels CCF](https://www.statsmodels.org/dev/generated/statsmodels.tsa.stattools.ccf.html))

**Cross-Correlation Analysis** ([GeeksforGeeks](https://www.geeksforgeeks.org/machine-learning/cross-correlation-analysis-in-python/), [DataInsightOnline](https://www.datainsightonline.com/post/cross-correlation-with-two-time-series-in-python)):
- Measures similarity between two series at different time lags
- For our case: correlate T3_exit_speed with T4_min_speed across laps at lag=0
- If r > 0.7 across 8+ laps, T3 exit strongly predicts T4 performance
- Can be computed per corner pair using `scipy.signal.correlate` or `numpy.corrcoef`

### 3.2 Bayesian Networks for Fault Diagnosis

**Manufacturing RCA Parallel** ([IEEE Xplore](https://ieeexplore.ieee.org/document/4415291/), [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0890695504001609)):
- Manufacturing uses Bayesian belief networks to trace quality defects through sequential machining operations
- Directly parallel to our problem: sequential corners are sequential machining stations
- "Data from multiple sensors on sequential machining operations are combined through a causal belief network framework to provide a probabilistic diagnosis of the root cause"
- Key advantage: provides probabilistic confidence levels, not just binary "yes/no"

**Ensemble Bayesian Networks** ([ScienceDirect](https://www.sciencedirect.com/science/article/pii/S0278612524001213)):
- Modern approach: ensemble of Bayesian Networks for more robust diagnosis
- "Human-interpretable probabilistic reasoning method for root cause analysis"
- Learns structure from historical data -- applicable to our multi-session corner data

**Applicability Assessment**: Bayesian networks are theoretically ideal but over-engineered for our current needs. We have:
- Known causal structure (the track layout defines the DAG)
- Simple linear relationships (exit speed -> straight speed -> entry speed)
- Small sample sizes (8-20 laps per session)

A simpler correlation + physics model will outperform a learned Bayesian network at our data scale.

### 3.3 Fault Tree Analysis Applied to Driving

**FTA Concepts** ([Wikipedia](https://en.wikipedia.org/wiki/Fault_tree_analysis)):
- Top-down approach: start with the undesired event (time loss at corner N), work backwards through possible causes
- Uses Boolean logic gates (AND/OR) to combine causes
- Applied to driving, a "slow exit at T4" fault tree:
  ```
  Slow T4 Exit (TOP EVENT)
  ├── OR: T4-specific mistakes
  │   ├── Late brake point at T4
  │   ├── Early apex at T4
  │   └── Late throttle commitment at T4
  └── OR: Cascading from T3
      ├── AND: Poor T3 exit + short straight
      │   ├── Slow T3 exit speed
      │   └── Insufficient recovery distance
      └── AND: Wrong positioning from T3
          ├── Wide T3 exit line
          └── Forces compromised T4 entry
  ```

**Fishbone / Ishikawa Diagrams** ([Wikipedia](https://en.wikipedia.org/wiki/Ishikawa_diagram)):
- Categorize causes into groups (Braking, Steering, Throttle, Line Choice, Setup, Track Conditions)
- Useful for visualization and coaching communication
- Mazda famously used Ishikawa diagrams in MX-5 development

**Best Fit for Cataclysm**: The fault tree structure maps directly onto our data model. We can build a simplified fault tree algorithmically:
1. Detect time loss at a corner (vs best lap or session median)
2. Check if the loss correlates with the preceding corner's exit metrics
3. If yes, trace further back through the chain until we find the root cause

### 3.4 Distinguishing Correlation from Causation in Telemetry

This is simpler in our domain than in general data science because:
1. **Temporal ordering is fixed**: T3 always happens before T4 on every lap
2. **Physics constrains the mechanism**: exit speed at T3 determines available speed at T4 entry through well-understood kinematics (v^2 = v0^2 + 2ad)
3. **We can test counterfactuals**: "If exit speed at T3 had been X mph higher, what would entry speed at T4 have been?" using kinematic equations
4. **Confounders are limited**: tire degradation, fuel load, and weather affect all corners similarly within a session

The main confounder is **driver confidence**: a bad T3 may cause mental hesitation at T4 beyond what physics dictates. This is undetectable from telemetry alone but can be noted in coaching output.

---

## 4. Topic 3: Corner Combination Detection

### 4.1 Automatic Detection of Corner Complexes

**Current Cataclysm State**: We already have `parent_complex` in the `Corner` dataclass and `_assign_complex_ids()` in `segmentation.py`. This groups consecutive corners with the same direction. But this misses:
- Chicanes (opposite-direction connected corners)
- Complexes where a short transition separates corners of different directions
- The key question: is the inter-corner gap short enough that speed cannot fully recover?

**Proposed Algorithm -- Recovery Distance Analysis**:

The fundamental question: "Can the car reach terminal velocity (or the natural approach speed for the next corner) in the gap between corners?"

```python
def compute_recovery_fraction(
    exit_speed_mps: float,
    entry_speed_next_mps: float,
    gap_distance_m: float,
    max_accel_g: float = 0.5,  # typical street car full throttle
) -> float:
    """How much of the available speed gap can be recovered in the available distance?

    Returns a fraction 0.0-1.0 where:
    - 1.0 = car can fully reach the natural approach speed (corners are independent)
    - < 0.7 = corners are linked (exit speed of prev constrains entry of next)
    - < 0.3 = corners are tightly coupled (virtually zero recovery)
    """
    if exit_speed_mps >= entry_speed_next_mps:
        return 1.0  # Already at or above needed speed

    # v^2 = v0^2 + 2*a*d
    accel_mps2 = max_accel_g * 9.81
    achievable_speed_sq = exit_speed_mps**2 + 2 * accel_mps2 * gap_distance_m
    achievable_speed = achievable_speed_sq ** 0.5

    speed_deficit = entry_speed_next_mps - exit_speed_mps
    speed_recovered = min(achievable_speed, entry_speed_next_mps) - exit_speed_mps

    if speed_deficit <= 0:
        return 1.0
    return speed_recovered / speed_deficit
```

**Classification thresholds** (proposed):
- `recovery_fraction >= 0.9`: Independent corners (full recovery possible)
- `0.5 <= recovery_fraction < 0.9`: Partially linked (exit speed matters somewhat)
- `recovery_fraction < 0.5`: Strongly linked (exit speed directly constrains entry)
- `recovery_fraction < 0.2`: Tightly coupled (essentially one complex)

### 4.2 How to Determine Which Corners Form Complexes

**Method 1: Geometry-Based (Static, Per-Track)**
- Compute gap distance between each consecutive corner pair: `gap_m = corner[n+1].entry_distance_m - corner[n].exit_distance_m`
- Using best-lap exit/entry speeds, compute recovery fraction
- Corners with recovery_fraction < 0.7 are "linked"
- This can be pre-computed per track and stored in `track_db.py`

**Method 2: Data-Driven (Dynamic, Per-Session)**
- Compute Pearson correlation between T[n] exit speed and T[n+1] min speed across all laps
- If |r| > 0.6 with p < 0.05, the corners are empirically linked
- This adapts to the actual car/driver combination (a faster car may decouple corners that are linked for a slower car)
- Can be computed in `corner_analysis.py` alongside existing `_compute_correlations()`

**Method 3: Hybrid (Recommended)**
- Use geometry for initial classification (which pairs COULD be linked)
- Confirm with per-session correlation (which pairs ARE linked for this driver/car)
- Only flag cascading effects when both methods agree

### 4.3 Track Titan's TimeKiller Analysis

From the [Track Titan deep dive](https://skywork.ai/skypage/en/Track-Titan-An-AI-Powered-Deep-Dive-for-Sim-Racers-and-Tech-Enthusiasts/1976160936392716288):

Track Titan's approach:
1. **Simulation-based**: They run a physics simulation of what WOULD have happened if a specific mistake hadn't occurred
2. **Propagation model**: They trace how fixing one corner's mistake would change subsequent corners
3. **Attribution**: Time savings are attributed to the ROOT CAUSE corner, not to every affected corner
4. **Prioritization**: The "TimeKiller" is the single corner/phase that, if fixed, yields the most total time savings including downstream effects

**Key difference from simple corner grading**: A corner might show 0.2s of time loss on its own, but if it causes 0.4s of downstream cascading loss, the TimeKiller analysis shows it as 0.6s total impact.

### 4.4 Quantifying Inter-Corner Time Loss Attribution

The central question: "How much of T4's time loss was caused by T3 vs T4 itself?"

**Proposed Decomposition Method**:

```
T4_total_time_loss = T4_self_caused_loss + T4_inherited_loss

Where:
  T4_inherited_loss = f(T3_exit_speed_delta, gap_distance, recovery_fraction)
  T4_self_caused_loss = T4_total_time_loss - T4_inherited_loss
```

Specifically:
1. Compute T3's exit speed deviation from best-lap: `delta_v3_exit = v3_exit_best - v3_exit_actual`
2. Propagate through the gap: `delta_v4_entry = delta_v3_exit * (1 - recovery_fraction)`
3. Estimate inherited time cost: `inherited_time_s = delta_v4_entry * gap_time_per_mps`
4. T4's own contribution: `self_time_s = T4_total_loss - inherited_time_s`

If `self_time_s` is near zero, T4's problem is entirely inherited from T3. If `self_time_s` is dominant, T4 has its own independent issue.

---

## 5. Topic 4: Exit-Entry Speed Correlation

### 5.1 Mathematical Model: Exit Speed Propagation

The physics of speed carry between corners is governed by kinematics with aerodynamic drag:

**Simplified model (constant acceleration, no drag)**:
```
v_entry_next^2 = v_exit_prev^2 + 2 * a * d_gap
```
Where:
- `v_exit_prev`: Exit speed from previous corner (m/s)
- `v_entry_next`: Achievable entry speed at next corner (m/s)
- `a`: Average acceleration on the connecting straight (m/s^2)
- `d_gap`: Distance between corner exit and next corner entry (m)

**With drag (more realistic for high-speed cars)**:
```
m * dv/dt = F_engine - 0.5 * rho * Cd * A * v^2
```
This requires numerical integration, but for track-day cars at moderate speeds (50-130 mph), the simplified model is within 5% accuracy over typical inter-corner gaps (50-300m).

**Time impact of exit speed delta** ([Driver61](https://driver61.com/uni/corner-exit/)):

The time to traverse a gap of distance `d` starting at speed `v0` with constant acceleration `a`:
```
t = (-v0 + sqrt(v0^2 + 2*a*d)) / a
```

For a 1 mph (0.447 m/s) exit speed advantage over a 200m straight with 0.5g acceleration:
- At 60 mph exit: saves ~0.015 seconds
- At 100 mph exit: saves ~0.009 seconds
- At 40 mph exit: saves ~0.022 seconds

This confirms the racing engineering principle: exit speed gains are worth more from slower corners.

### 5.2 Separating Legitimate Speed Differences from Cascading Errors

A critical subtlety: different corners have different natural speeds. T3 might be a 45 mph corner and T4 a 90 mph corner. A driver going 43 mph through T3 and 87 mph through T4 has TWO separate issues -- the T4 issue is not necessarily caused by T3.

**How to distinguish**:

1. **Compute deviation from session best** (not absolute speeds):
   - T3 deviation: 43 - 45 = -2 mph (2 mph slow)
   - T4 deviation: 87 - 90 = -3 mph (3 mph slow)

2. **Compute what T3's deviation would propagate to T4**:
   - If recovery fraction is 0.3, T3's -2 mph becomes -2 * 0.3 = -0.6 mph inherited at T4 entry
   - T4's total deviation is -3 mph, so T4's self-caused loss is -3 - (-0.6) = -2.4 mph

3. **Attribution**:
   - T4 inherited loss: 0.6 mph (20% from T3)
   - T4 self-caused loss: 2.4 mph (80% from T4 itself)
   - Coaching should focus on T4 as a separate issue

4. **Contrast with a cascading case**:
   - T3: -4 mph slow, T4: -3 mph slow
   - With recovery fraction 0.3: inherited = 4 * 0.3 = 1.2 mph
   - But wait -- if inherited > total deviation, cap at total: T4 self-caused = max(0, 3 - 1.2) = 1.8 mph
   - But with recovery fraction 0.8: inherited = 4 * 0.8 = 3.2 mph -> capped at 3.0 mph
   - T4 self-caused = 0 mph. T4's entire problem is inherited from T3.

### 5.3 Sequential Decision-Making Perspective

Research on [sequential decision-making in motorsport](https://www.researchgate.net/publication/290180544_Real-time_decision_making_in_motorsports_analytics_for_improving_professional_car_race_strategy) shows that:

- Driver momentum has a 70% correlation with end-of-race positioning
- Consistent upward or downward movements suggest predictable performance trends
- In our context: a driver who makes a mistake at T3 often makes worse subsequent mistakes (confidence cascade)

This suggests we should also check for **systematic degradation patterns**: if T3, T4, AND T5 are all progressively worse, this is likely a confidence cascade, not independent errors. The coaching response should address the root cause (T3) and explicitly note that T4-T5 will improve automatically.

---

## 6. Topic 5: Implementation Patterns

### 6.1 Python Libraries for Causal Analysis

**Heavy-weight options (evaluated, NOT recommended for our use case)**:

| Library | Purpose | Why Not For Us |
|---------|---------|----------------|
| [DoWhy](https://github.com/py-why/dowhy) | General causal inference | Over-engineered; our DAG is known (track layout), not learned |
| [DoWhy-GCM](https://www.pywhy.org/dowhy/v0.11.1/example_notebooks/gcm_online_shop.html) | Root cause attribution in graphical causal models | Elegant API but heavy dependency; designed for larger datasets |
| [causal-learn](https://github.com/py-why/causal-learn) | Causal discovery from data | We don't need to DISCOVER the causal graph -- the track defines it |
| [CausalInference](https://pypi.org/project/dowhy/) | Treatment effect estimation | Wrong paradigm (A/B testing, not sequential analysis) |

**Lightweight options (recommended)**:

| Library | Purpose | How We Use It |
|---------|---------|---------------|
| `numpy.corrcoef` | Pearson correlation | Cross-corner KPI correlation per session |
| `scipy.stats.pearsonr` | Correlation with p-values | Statistical significance of corner coupling |
| `scipy.stats.spearmanr` | Rank correlation | More robust to outliers in small samples |
| `statsmodels.tsa.stattools.ccf` | Cross-correlation function | Lag analysis if we extend to time-series |
| `numpy` kinematics | Speed propagation physics | Exit-to-entry speed model |

**Rationale**: We have a domain where the causal structure is known (corner sequence), the physical mechanism is understood (kinematics), and sample sizes are small (8-20 laps). Simple statistical methods with physics-informed models will outperform complex causal ML.

### 6.2 Correlation Matrices for Multi-Corner Analysis

A session-level correlation matrix can reveal unexpected dependencies:

```python
import numpy as np
from scipy.stats import pearsonr

def build_inter_corner_correlation_matrix(
    all_lap_corners: dict[int, list[Corner]],
    n_corners: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Build correlation matrix: exit_speed[i] vs min_speed[i+1] across laps.

    Returns (correlation_matrix, p_value_matrix) of shape (n_corners-1,).
    """
    correlations = np.zeros(n_corners - 1)
    p_values = np.ones(n_corners - 1)

    lap_numbers = sorted(all_lap_corners.keys())

    for i in range(n_corners - 1):
        corner_a_num = i + 1
        corner_b_num = i + 2

        exit_speeds = []
        entry_speeds = []

        for lap in lap_numbers:
            corners = {c.number: c for c in all_lap_corners[lap]}
            if corner_a_num in corners and corner_b_num in corners:
                # Use exit speed proxy: speed at exit_distance_m
                # (or we can compute it from the raw data)
                a = corners[corner_a_num]
                b = corners[corner_b_num]
                exit_speeds.append(a.min_speed_mps)  # proxy
                entry_speeds.append(b.min_speed_mps)

        if len(exit_speeds) >= 4:
            r, p = pearsonr(exit_speeds, entry_speeds)
            correlations[i] = r
            p_values[i] = p

    return correlations, p_values
```

### 6.3 Presenting Causal Chains to Non-Technical Users

Research on causal visualization for non-technical audiences ([Visual Analytics for Causal Analysis](https://arxiv.org/pdf/2009.02458), [RootCause.ai](https://docs.rootcause.ai/user-guide/digital-twin/causal-graph)):

**Best practices**:
1. **Linear chain, not graph**: Drivers think sequentially -- show T3 -> T4 -> T5, not a DAG
2. **Color coding**: Green (no issue), Yellow (some inherited loss), Red (root cause)
3. **Natural language first**: "Your T5 was slow because of T3" before any numbers
4. **One actionable item**: Focus on the root cause corner only -- "Fix T3 and T4-T5 will improve automatically"
5. **Quantify the cascade**: "Fixing T3 would save 0.15s at T3 + 0.08s at T4 + 0.03s at T5 = 0.26s total"

**Sankey/flow diagrams** are effective for showing causal influence flowing through a system ([RootCause.ai](https://docs.rootcause.ai/user-guide/digital-twin/causal-graph)), with flow width showing contribution magnitude. But for a coaching report text, a simple chain notation works better:

```
Root Cause Chain: T3 (late brake) -> T4 (slow entry, -3 mph) -> T5 (compromised line)
Total cascade impact: 0.26s
Fix T3 brake point and T4-T5 improve automatically.
```

**PyRCA** ([Salesforce PyRCA](https://www.salesforce.com/blog/pyrca/)): Salesforce's AIOps root cause analysis library provides interactive dashboards for RCA. While not directly applicable, the visualization patterns (directed flow, contribution bars) are worth studying for our frontend.

---

## 7. Proposed Algorithm Design

### 7.1 Architecture Overview

New module: `cataclysm/causal_chains.py`

The algorithm has three stages:
1. **Detect Linked Corner Pairs** (static + dynamic)
2. **Compute Cascading Effects Per Lap** (physics-based propagation)
3. **Aggregate Into Causal Chains** (session-level root cause identification)

### 7.2 Data Structures

```python
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CornerLink:
    """Describes the physical coupling between two adjacent corners."""

    corner_a: int           # Upstream corner number
    corner_b: int           # Downstream corner number
    gap_distance_m: float   # Distance between exit of A and entry of B
    recovery_fraction: float  # 0.0 = tightly coupled, 1.0 = independent
    correlation_r: float    # Pearson r between A exit speed and B min speed
    correlation_p: float    # p-value for the correlation
    link_strength: str      # "tight", "moderate", "weak", "independent"


@dataclass
class CascadeEffect:
    """Per-lap quantification of how one corner's error affects the next."""

    lap: int
    source_corner: int       # Where the error originated
    affected_corner: int     # Where the effect is felt
    source_speed_delta_mps: float   # How slow the source corner was vs best
    inherited_speed_delta_mps: float  # How much of that propagated
    inherited_time_cost_s: float     # Time cost of the inherited deficit
    self_caused_time_cost_s: float   # Time cost of the corner's own errors
    inheritance_fraction: float      # What fraction of total loss is inherited


@dataclass
class CausalChain:
    """A detected chain of cascading errors across multiple corners."""

    root_cause_corner: int    # The corner where the chain starts
    affected_corners: list[int]  # Downstream corners affected
    root_cause_type: str      # "late_brake", "early_apex", "slow_exit", etc.
    total_cascade_time_s: float  # Total time cost across the entire chain
    root_cause_time_s: float    # Time cost at the root cause corner itself
    downstream_time_s: float    # Additional time cost in downstream corners
    laps_affected: list[int]    # Which laps showed this pattern
    frequency: float            # Fraction of laps where this chain appeared
    coaching_summary: str       # Natural language description for the LLM


@dataclass
class SessionCausalAnalysis:
    """Complete causal chain analysis for a session."""

    links: list[CornerLink]          # All corner pair linkages
    chains: list[CausalChain]        # Detected causal chains, sorted by impact
    total_cascade_time_s: float      # Sum of all cascading time losses
    cascade_fraction: float          # What fraction of total time loss is cascading
    top_time_killer: CausalChain | None  # The single biggest cascade
```

### 7.3 Core Algorithm

```python
import numpy as np
from scipy.stats import pearsonr

# ── Stage 1: Detect Corner Links ──────────────────────────────────

def detect_corner_links(
    all_lap_corners: dict[int, list[Corner]],
    best_lap_corners: list[Corner],
    max_accel_g: float = 0.5,
) -> list[CornerLink]:
    """Detect which adjacent corner pairs are physically linked."""

    links: list[CornerLink] = []
    corner_numbers = sorted({c.number for cs in all_lap_corners.values() for c in cs})

    for i in range(len(corner_numbers) - 1):
        cn_a = corner_numbers[i]
        cn_b = corner_numbers[i + 1]

        # Get best-lap corners for gap computation
        best_a = next((c for c in best_lap_corners if c.number == cn_a), None)
        best_b = next((c for c in best_lap_corners if c.number == cn_b), None)
        if best_a is None or best_b is None:
            continue

        # Gap distance
        gap_m = best_b.entry_distance_m - best_a.exit_distance_m
        if gap_m <= 0:
            gap_m = 1.0  # Overlapping corners = tightly coupled

        # Recovery fraction (physics-based)
        exit_speed = best_a.min_speed_mps  # Proxy: apex speed ~ exit speed
        entry_speed = best_b.min_speed_mps  # Proxy for approach speed
        recovery = compute_recovery_fraction(
            exit_speed, entry_speed, gap_m, max_accel_g
        )

        # Correlation (data-driven)
        r, p = compute_exit_entry_correlation(
            all_lap_corners, cn_a, cn_b
        )

        # Classify link strength
        if recovery < 0.3 or (abs(r) > 0.7 and p < 0.05):
            strength = "tight"
        elif recovery < 0.7 or (abs(r) > 0.5 and p < 0.1):
            strength = "moderate"
        elif recovery < 0.9:
            strength = "weak"
        else:
            strength = "independent"

        links.append(CornerLink(
            corner_a=cn_a,
            corner_b=cn_b,
            gap_distance_m=round(gap_m, 1),
            recovery_fraction=round(recovery, 3),
            correlation_r=round(r, 3),
            correlation_p=round(p, 4),
            link_strength=strength,
        ))

    return links


def compute_recovery_fraction(
    exit_speed_mps: float,
    natural_approach_speed_mps: float,
    gap_distance_m: float,
    max_accel_g: float,
) -> float:
    """Fraction of speed deficit recoverable in the available gap distance."""
    if exit_speed_mps >= natural_approach_speed_mps:
        return 1.0

    accel_mps2 = max_accel_g * 9.81
    achievable_speed_sq = exit_speed_mps**2 + 2 * accel_mps2 * gap_distance_m
    achievable_speed = achievable_speed_sq ** 0.5

    deficit = natural_approach_speed_mps - exit_speed_mps
    recovered = min(achievable_speed, natural_approach_speed_mps) - exit_speed_mps

    return min(1.0, recovered / deficit) if deficit > 0 else 1.0


def compute_exit_entry_correlation(
    all_lap_corners: dict[int, list[Corner]],
    cn_a: int,
    cn_b: int,
) -> tuple[float, float]:
    """Pearson correlation between corner A exit speed and corner B min speed."""
    exit_speeds: list[float] = []
    min_speeds: list[float] = []

    for lap_corners in all_lap_corners.values():
        corner_map = {c.number: c for c in lap_corners}
        if cn_a in corner_map and cn_b in corner_map:
            exit_speeds.append(corner_map[cn_a].min_speed_mps)
            min_speeds.append(corner_map[cn_b].min_speed_mps)

    if len(exit_speeds) < 4:
        return 0.0, 1.0  # Insufficient data

    # Check for zero variance
    if np.std(exit_speeds) < 1e-6 or np.std(min_speeds) < 1e-6:
        return 0.0, 1.0

    r, p = pearsonr(exit_speeds, min_speeds)
    return float(r), float(p)


# ── Stage 2: Compute Per-Lap Cascading Effects ───────────────────

def compute_lap_cascades(
    lap_corners: list[Corner],
    best_corners: list[Corner],
    links: list[CornerLink],
) -> list[CascadeEffect]:
    """For a single lap, compute how each corner's errors cascade downstream."""

    effects: list[CascadeEffect] = []
    link_map = {(l.corner_a, l.corner_b): l for l in links}
    best_map = {c.number: c for c in best_corners}
    lap_map = {c.number: c for c in lap_corners}

    for link in links:
        if link.link_strength == "independent":
            continue

        cn_a, cn_b = link.corner_a, link.corner_b
        if cn_a not in lap_map or cn_b not in best_map or cn_b not in lap_map:
            continue
        if cn_a not in best_map:
            continue

        # Speed deviation at source corner
        source_delta = best_map[cn_a].min_speed_mps - lap_map[cn_a].min_speed_mps

        if source_delta <= 0:
            continue  # Source corner was at or above best -- no cascade

        # Propagate through the link
        propagation_factor = 1.0 - link.recovery_fraction
        inherited_delta = source_delta * propagation_factor

        # Total deviation at affected corner
        total_delta_b = best_map[cn_b].min_speed_mps - lap_map[cn_b].min_speed_mps

        if total_delta_b <= 0:
            continue  # Affected corner was fine despite upstream issue

        # Attribute: how much of B's loss is from A vs B's own error
        inherited_delta = min(inherited_delta, total_delta_b)
        self_delta = total_delta_b - inherited_delta

        # Convert speed deltas to time costs
        # t = d / v; dt = d * (1/v_slow - 1/v_fast)
        avg_speed = (best_map[cn_b].min_speed_mps + lap_map[cn_b].min_speed_mps) / 2
        corner_length = best_map[cn_b].exit_distance_m - best_map[cn_b].entry_distance_m

        if avg_speed > 0.1:
            inherited_time = corner_length * inherited_delta / (avg_speed ** 2)
            self_time = corner_length * self_delta / (avg_speed ** 2)
        else:
            inherited_time = 0.0
            self_time = 0.0

        inheritance_frac = inherited_delta / total_delta_b if total_delta_b > 0 else 0.0

        effects.append(CascadeEffect(
            lap=0,  # Set by caller
            source_corner=cn_a,
            affected_corner=cn_b,
            source_speed_delta_mps=round(source_delta, 3),
            inherited_speed_delta_mps=round(inherited_delta, 3),
            inherited_time_cost_s=round(inherited_time, 4),
            self_caused_time_cost_s=round(self_time, 4),
            inheritance_fraction=round(inheritance_frac, 3),
        ))

    return effects


# ── Stage 3: Aggregate Into Causal Chains ─────────────────────────

def detect_causal_chains(
    all_lap_corners: dict[int, list[Corner]],
    best_lap_corners: list[Corner],
    links: list[CornerLink],
    min_cascade_time_s: float = 0.01,
    min_frequency: float = 0.3,
) -> list[CausalChain]:
    """Detect recurring causal chains across all laps in a session."""

    best_map = {c.number: c for c in best_lap_corners}
    lap_numbers = sorted(all_lap_corners.keys())

    # Collect all cascade effects across laps
    all_effects: dict[int, list[CascadeEffect]] = {}
    for lap_num in lap_numbers:
        effects = compute_lap_cascades(
            all_lap_corners[lap_num], best_lap_corners, links
        )
        for e in effects:
            e.lap = lap_num
        all_effects[lap_num] = effects

    # Build chains: trace connected cascade effects
    # A chain is: root_corner -> corner_2 -> corner_3 -> ...
    # where each link has significant inheritance

    linked_pairs = [
        (l.corner_a, l.corner_b) for l in links
        if l.link_strength in ("tight", "moderate")
    ]

    # Group cascade effects by (source, affected) pair
    pair_effects: dict[tuple[int, int], list[CascadeEffect]] = {}
    for lap_effects in all_effects.values():
        for e in lap_effects:
            key = (e.source_corner, e.affected_corner)
            pair_effects.setdefault(key, []).append(e)

    # Build chains by following linked pairs
    chains: list[CausalChain] = []
    visited_roots: set[int] = set()

    corner_numbers = sorted({c.number for c in best_lap_corners})

    for start_corner in corner_numbers:
        if start_corner in visited_roots:
            continue

        # Try to build a chain starting from this corner
        chain_corners = [start_corner]
        current = start_corner

        while True:
            # Find next linked corner
            next_links = [
                (a, b) for a, b in linked_pairs if a == current
            ]
            if not next_links:
                break
            next_corner = next_links[0][1]

            # Check if this pair has cascade effects
            pair_key = (current, next_corner)
            if pair_key not in pair_effects:
                break

            effects = pair_effects[pair_key]
            if len(effects) < len(lap_numbers) * min_frequency:
                break

            chain_corners.append(next_corner)
            current = next_corner

        if len(chain_corners) < 2:
            continue

        # Compute chain statistics
        root = chain_corners[0]
        affected = chain_corners[1:]

        # Aggregate time costs
        total_cascade = 0.0
        root_time = 0.0
        downstream_time = 0.0
        laps_with_chain: set[int] = set()

        for pair_idx in range(len(chain_corners) - 1):
            pair_key = (chain_corners[pair_idx], chain_corners[pair_idx + 1])
            if pair_key in pair_effects:
                for e in pair_effects[pair_key]:
                    downstream_time += e.inherited_time_cost_s
                    laps_with_chain.add(e.lap)

        # Root cause time: the root corner's own deviation
        for lap_num in laps_with_chain:
            if root in {c.number for c in all_lap_corners.get(lap_num, [])}:
                lap_corner = next(
                    c for c in all_lap_corners[lap_num] if c.number == root
                )
                if root in best_map:
                    delta = best_map[root].min_speed_mps - lap_corner.min_speed_mps
                    if delta > 0:
                        corner_len = best_map[root].exit_distance_m - best_map[root].entry_distance_m
                        avg_speed = (best_map[root].min_speed_mps + lap_corner.min_speed_mps) / 2
                        if avg_speed > 0.1:
                            root_time += corner_len * delta / (avg_speed ** 2)

        total_cascade = root_time + downstream_time
        frequency = len(laps_with_chain) / len(lap_numbers) if lap_numbers else 0

        if total_cascade < min_cascade_time_s:
            continue

        # Determine root cause type
        root_cause_type = _classify_root_cause(
            all_lap_corners, best_map, root, list(laps_with_chain)
        )

        # Generate coaching summary
        summary = _generate_chain_summary(
            root, affected, root_cause_type, root_time, downstream_time, frequency
        )

        chains.append(CausalChain(
            root_cause_corner=root,
            affected_corners=affected,
            root_cause_type=root_cause_type,
            total_cascade_time_s=round(total_cascade, 3),
            root_cause_time_s=round(root_time, 3),
            downstream_time_s=round(downstream_time, 3),
            laps_affected=sorted(laps_with_chain),
            frequency=round(frequency, 2),
            coaching_summary=summary,
        ))

        visited_roots.add(root)

    # Sort by total cascade time descending
    chains.sort(key=lambda c: -c.total_cascade_time_s)
    return chains


def _classify_root_cause(
    all_lap_corners: dict[int, list[Corner]],
    best_map: dict[int, Corner],
    root_corner: int,
    affected_laps: list[int],
) -> str:
    """Determine the primary type of error at the root cause corner."""
    if root_corner not in best_map:
        return "unknown"

    best = best_map[root_corner]

    brake_late_count = 0
    apex_early_count = 0
    speed_slow_count = 0

    for lap in affected_laps:
        if lap not in all_lap_corners:
            continue
        corners = {c.number: c for c in all_lap_corners[lap]}
        if root_corner not in corners:
            continue
        c = corners[root_corner]

        # Check brake point (later = higher distance value = worse)
        if (best.brake_point_m is not None and c.brake_point_m is not None
                and c.brake_point_m > best.brake_point_m + 5):
            brake_late_count += 1

        # Check apex type
        if c.apex_type == "early" and best.apex_type != "early":
            apex_early_count += 1

        # Check speed
        if c.min_speed_mps < best.min_speed_mps * 0.95:
            speed_slow_count += 1

    # Classify by most frequent issue
    issues = {
        "late_brake": brake_late_count,
        "early_apex": apex_early_count,
        "over_slowing": speed_slow_count,
    }

    if max(issues.values()) == 0:
        return "general"

    return max(issues, key=issues.get)


def _generate_chain_summary(
    root: int,
    affected: list[int],
    cause_type: str,
    root_time: float,
    downstream_time: float,
    frequency: float,
) -> str:
    """Generate a natural-language summary for coaching prompts."""
    cause_descriptions = {
        "late_brake": "braking too late",
        "early_apex": "turning in too early (early apex)",
        "over_slowing": "over-slowing the car",
        "general": "sub-optimal technique",
    }
    cause_text = cause_descriptions.get(cause_type, cause_type)

    affected_str = ", ".join(f"T{c}" for c in affected)
    total = root_time + downstream_time
    pct = int(frequency * 100)

    return (
        f"T{root} is a root cause: {cause_text} at T{root} cascades into "
        f"{affected_str}, costing ~{total:.2f}s total "
        f"({root_time:.2f}s at T{root} + {downstream_time:.2f}s downstream). "
        f"This pattern appears in {pct}% of laps. "
        f"Fixing T{root} will automatically improve {affected_str}."
    )
```

### 7.4 Integration Points

**Where this plugs into the existing system**:

1. **`cataclysm/corner_analysis.py`**: Add `causal_chains: SessionCausalAnalysis | None` field to `SessionCornerAnalysis`
2. **`cataclysm/coaching.py`**: Include causal chain summaries in the corner analysis section of the coaching prompt
3. **`backend/api/services/pipeline.py`**: Call `detect_corner_links()` and `detect_causal_chains()` after corner analysis
4. **`backend/api/schemas/analysis.py`**: Add Pydantic models for `CausalChain` and `CornerLink`
5. **Frontend**: Show cascade indicators on corner cards and in the deep-dive view

**No new dependencies required**: Everything uses `numpy` and `scipy.stats` which are already in the project.

---

## 8. Coaching Report Integration

### 8.1 Prompt Engineering for Causal Chains

Add to the coaching system prompt (in `driving_physics.py` or as a new section):

```
## Inter-Corner Causal Chains

When causal chains are detected, you MUST:
1. Lead with the root cause corner, not the affected corners
2. Explain the mechanism: "Your late brake at T3 means you exit slow, which
   means you arrive at T4 with less speed than your best lap"
3. Quantify: "This cascade costs ~0.26s total (0.15s at T3 + 0.11s downstream)"
4. Reassure: "Fixing T3 will automatically improve T4 without extra effort"
5. Do NOT give separate coaching for affected corners if >60% of their
   time loss is inherited

Rules:
- A corner with >60% inherited time loss should be labeled "(cascading from TX)"
- The "TimeKiller" is the causal chain with the highest total_cascade_time_s
- Present at most 2 causal chains to avoid overwhelming the driver
```

### 8.2 User Prompt Section Format

In the per-corner data section sent to the LLM, add:

```
## Causal Chain Analysis (TimeKiller Detection)

### Chain 1 (TimeKiller): T3 -> T4 -> T5
- Root cause: T3 (braking too late)
- T3 direct cost: 0.15s
- T4 inherited cost: 0.08s (62% of T4's total loss is from T3)
- T5 inherited cost: 0.03s (45% of T5's total loss is from T3-T4 cascade)
- Total cascade: 0.26s across 75% of laps
- Fix: Brake 8m earlier at T3 (at the 3-board marker)

### Chain 2: T11 -> T12
- Root cause: T11 (early apex)
- T11 direct cost: 0.10s
- T12 inherited cost: 0.06s (55% of T12's loss)
- Total cascade: 0.16s across 60% of laps
- Fix: Delay turn-in at T11, aim for later apex
```

### 8.3 Frontend Visualization Concept

For the corner detail cards in the deep-dive view:

1. **Cascade badge**: Show a small chain icon on corner cards that are part of a causal chain
2. **Root cause highlight**: The root cause corner gets a red "TimeKiller" badge
3. **Inheritance bar**: On affected corners, show a split bar: "self-caused" vs "inherited" time loss
4. **Chain flow**: In the track map view, draw arrows between linked corners with line thickness proportional to cascade magnitude

---

## 9. Implementation Roadmap

### Phase 1: Corner Link Detection (Low effort, high value)
1. Implement `compute_recovery_fraction()` and `compute_exit_entry_correlation()`
2. Add `CornerLink` to the pipeline output
3. Inject link information into coaching prompts
4. **Estimated effort**: 2-3 hours
5. **Data needed**: Already available (corner entry/exit distances, min speeds)

### Phase 2: Cascade Quantification (Medium effort, high value)
1. Implement `compute_lap_cascades()` with physics-based propagation
2. Add `CascadeEffect` to per-lap analysis
3. Compute inheritance fractions per corner
4. **Estimated effort**: 3-4 hours
5. **Requires**: Phase 1

### Phase 3: Causal Chain Aggregation (Medium effort, highest value)
1. Implement `detect_causal_chains()` with chain tracing
2. Add `SessionCausalAnalysis` to pipeline
3. Integrate chain summaries into coaching prompts
4. Add "TimeKiller" detection (top chain by total impact)
5. **Estimated effort**: 3-4 hours
6. **Requires**: Phase 2

### Phase 4: Frontend Integration (Medium effort, medium value)
1. Add cascade indicators to corner cards
2. Show inheritance bars on affected corners
3. Add chain visualization to track map
4. **Estimated effort**: 4-6 hours
5. **Requires**: Phase 3 + API schema updates

### Total: ~12-17 hours of implementation

### Key Risk: Exit Speed Proxy

Our `Corner` dataclass stores `min_speed_mps` (apex speed), not exit speed. For tightly coupled corners, apex speed is a reasonable proxy for exit speed. For moderately linked corners, we should eventually compute actual exit speed from the raw telemetry data at `exit_distance_m`. This is a Phase 2 enhancement -- can be done by reading speed at the corner's `exit_distance_m` from the resampled lap DataFrame.

---

## Sources

### Racing Engineering & Corner Dependencies
- [Driver61 - Prioritising Circuit Corners](https://driver61.com/uni/prioritising-corners/)
- [Driver61 - Maximising the Exit Phase](https://driver61.com/uni/corner-exit/)
- [Driver61 - Different Corner Technique](https://driver61.com/uni/different-corner-technique/)
- [Blayze - Complex Corners](https://blayze.io/blog/car-racing/complex-corners)
- [Blayze - When To Sacrifice Speed](https://blayze.io/blog/car-racing/when-to-sacrifice-on-the-racetrack)
- [Blayze - Entry vs Exit Speed Corners](https://blayze.io/blog/car-racing/entry-vs-exit-speed-corners-which-one-is-it)
- [Allen Berg Racing Schools - Three Types of Corners](https://www.allenbergracingschools.com/expert-advice/race-tracks-three-corners-types/)
- [Speed Secrets - Entry/Exit Speed Balance](https://windingroad.com/articles/features/speed-secrets-determining-entry-exit-speed-balance/)
- [Paradigm Shift Racing - Corner Exit Drag Race](https://www.paradigmshiftracing.com/racing-basics/the-corner-exit-drag-race-racing-line-physics-explained)
- [YourDataDriven - Race Track Corner Phases](https://www.yourdatadriven.com/race-engineering-race-track-corner-phases/)
- [Race Track Driving - Sequence for Improving Lap Time](https://racetrackdriving.com/concepts/sequence-for-improving-lap-time/)

### Competitive Analysis
- [Track Titan - November 2025 Update (Coaching Flows)](https://www.tracktitan.io/post/november-2025-update-coaching-flows)
- [Track Titan - December 2025 Update](https://www.tracktitan.io/post/december-2025-track-titan-update-faster-coaching-flows-social-leaderboards-bigger-team)
- [Track Titan - How To Analyse Telemetry](https://www.tracktitan.io/post/how-to-analyse-telemetry-for-sim-racing)
- [Track Titan AI Deep Dive (Skywork)](https://skywork.ai/skypage/en/Track-Titan-An-AI-Powered-Deep-Dive-for-Sim-Racers-and-Tech-Enthusiasts/1976160936392716288)
- [Full Grip Motorsport - Telemetry Analysis](https://www.fullgripmotorsport.com/telemetry)
- [Coach Dave Academy - Delta Guide](https://coachdaveacademy.com/tutorials/a-delta-guide-understanding-telemetry-data-in-cornering-types/)
- [Sim Racing Telemetry - Analyzing Racing Lines](https://docs.simracingtelemetry.com/kb/how-to-analyze-racing-lines)

### Causal Inference & Root Cause Analysis
- [Granger Causality - Wikipedia](https://en.wikipedia.org/wiki/Granger_causality)
- [Granger Causality Review - PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC10571505/)
- [Bayesian Network RCA in Manufacturing - IEEE](https://ieeexplore.ieee.org/document/4415291/)
- [Bayesian Network Root Cause Diagnosis - ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0890695504001609)
- [Ensemble Bayesian Network for RCA - ScienceDirect](https://www.sciencedirect.com/science/article/pii/S0278612524001213)
- [Fault Tree Analysis - Wikipedia](https://en.wikipedia.org/wiki/Fault_tree_analysis)
- [Ishikawa Diagram - Wikipedia](https://en.wikipedia.org/wiki/Ishikawa_diagram)
- [Causal Discovery from Temporal Data - ACM](https://dl.acm.org/doi/10.1145/3705297)

### Python Causal Libraries
- [DoWhy - GitHub](https://github.com/py-why/dowhy)
- [DoWhy GCM Online Shop Example](https://www.pywhy.org/dowhy/v0.11.1/example_notebooks/gcm_online_shop.html)
- [DoWhy GCM Root Cause - AWS Blog](https://aws.amazon.com/blogs/opensource/root-cause-analysis-with-dowhy-an-open-source-python-library-for-causal-machine-learning/)
- [PyWhy Ecosystem](https://www.pywhy.org/)
- [causal-learn - GitHub](https://github.com/py-why/causal-learn)
- [PyRCA by Salesforce](https://www.salesforce.com/blog/pyrca/)

### Research Papers
- [AI-enabled Sim Racing Performance Prediction - ScienceDirect](https://www.sciencedirect.com/science/article/pii/S2451958824000472)
- [Racing Line Optimization - MIT](https://dspace.mit.edu/bitstream/handle/1721.1/64669/706825301-MIT.pdf)
- [Computing Racing Line with Bayesian Optimization - arXiv](https://arxiv.org/pdf/2002.04794)
- [Minimum Lap Time Optimization - UniPD](https://www.research.unipd.it/retrieve/e14fb26e-b9c2-3de1-e053-1705fe0ac030/2021%20-%20Minimum-lap-time%20optimization%20and%20simulation%20PP.pdf)
- [Visual Analytics for Causal Analysis - arXiv](https://arxiv.org/pdf/2009.02458)
- [Machine Learning for Corner Detection - Springer](https://link.springer.com/chapter/10.1007/11744023_34)

### Statistics & Correlation
- [Cross-Correlation in Python - GeeksforGeeks](https://www.geeksforgeeks.org/machine-learning/cross-correlation-analysis-in-python/)
- [Statsmodels CCF Function](https://www.statsmodels.org/dev/generated/statsmodels.tsa.stattools.ccf.html)
- [SciPy correlation_lags](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.correlation_lags.html)
- [Python Correlation Matrix - Real Python](https://realpython.com/numpy-scipy-pandas-correlation-python/)

### Visualization Research
- [RootCause.ai Causal Graph](https://docs.rootcause.ai/user-guide/digital-twin/causal-graph)
- [Causal Chain Analysis - IW:LEARN](https://iwlearn.net/manuals/tda-sap-methodology/development-of-the-tda/causal-chain-analysis/what-is-causal-chain-analysis)
