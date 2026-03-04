# Iteration 3: Session-Over-Session Memory, Corners Gained, Flow Laps, and Longitudinal Coaching

**Research Date**: 2026-03-03
**Focus**: Cross-session intelligence, longitudinal coaching, and advanced performance decomposition

---

## Table of Contents

1. [Topic 1: LLM Memory Architectures for Coaching Applications](#topic-1-llm-memory-architectures-for-coaching-applications)
2. [Topic 2: "Corners Gained" Algorithm Design](#topic-2-corners-gained-algorithm-design)
3. [Topic 3: Flow Lap Detection Algorithm](#topic-3-flow-lap-detection-algorithm)
4. [Topic 4: Pre-Session Briefing Generation](#topic-4-pre-session-briefing-generation)
5. [Topic 5: Longitudinal Progress Visualization](#topic-5-longitudinal-progress-visualization)
6. [Topic 6: Session Comparison Intelligence](#topic-6-session-comparison-intelligence)

---

## Topic 1: LLM Memory Architectures for Coaching Applications

### Key Findings

#### 1.1 The Context Engineering Paradigm (2025-2026)

The field has shifted from "prompt engineering" to **context engineering** — treating the context window as a scarce resource and designing the entire information pipeline around it. As articulated by the LangChain team and others, the LLM is like a CPU and its context window is like RAM: the model's working memory that must be carefully managed.

Key principles from the research:

- **Token budgeting**: RAG systems perform token budgeting, deciding how much of the total context window is spent on system prompts, queries, retrieved context, and output buffers. Engineers typically keep a 10-20% buffer to avoid hitting the hard cap. The effective limit where accuracy remains stable is often 70-80% of the nominal maximum.
- **Context rot**: Performance degrades unpredictably as input context grows longer. Models may exhibit sharp drops in accuracy, ignore parts of the context, or hallucinate. This is critical for coaching: we must be selective about what history we inject.
- **Hierarchical summarization**: Condenses long interaction histories into layered summaries (like a pyramid) to preserve key information while minimizing tokens. Contextual summarization periodically compresses older conversations while keeping recent exchanges verbatim.

Sources:
- [Context Engineering - LangChain](https://blog.langchain.com/context-engineering-for-agents/)
- [Top Techniques to Manage Context Lengths in LLMs](https://agenta.ai/blog/top-6-techniques-to-manage-context-length-in-llms)
- [Building Long-Term Memories Using Hierarchical Summarization](https://pieces.app/blog/hierarchical-summarization)
- [From RAG to Context - 2025 Review](https://ragflow.io/blog/rag-review-2025-from-rag-to-context)
- [LLM Chat History Summarization Guide](https://mem0.ai/blog/llm-chat-history-summarization-guide-2025)
- [Context Engineering for Personalization - OpenAI Cookbook](https://cookbook.openai.com/examples/agents_sdk/context_personalization)

#### 1.2 How WHOOP Implements AI Memory

WHOOP's partnership with OpenAI provides the best real-world example of persistent coaching memory:

- **Architecture**: GPT-4 fine-tuned with anonymized member data + WHOOP's proprietary algorithms. User metrics are anonymized before being processed through the LLM.
- **Memory scope**: WHOOP remembers "important things about your life" — frequent travel, ongoing health concerns, having young children, specific training goals — but NOT temporary things like how you felt one morning, unless they reveal a lasting pattern.
- **Memory builds over time**: "Every interaction builds on the last, creating smarter, more relevant guidance over time."
- **Practical examples**: Adjusting sleep routines ahead of travel to reduce jet lag. Recognizing when high strain patterns mirror past fatigue episodes and suggesting rest preemptively.
- **Privacy**: Zero-retention/zero-training policy with LLM partner. Data anonymized before processing.

Sources:
- [WHOOP + OpenAI Partnership](https://openai.com/index/whoop/)
- [How WHOOP Built a Reliable GenAI Chatbot](https://www.montecarlodata.com/blog-how-whoop-built-and-launched-a-reliable-genai-chatbot/)
- [New AI Guidance from WHOOP](https://www.whoop.com/us/en/thelocker/new-ai-guidance-from-whoop/)
- [WHOOP Unveils New Coach Powered by OpenAI](https://www.whoop.com/us/en/thelocker/whoop-unveils-the-new-whoop-coach-powered-by-openai/)

#### 1.3 Memory Storage Paradigms (Research Survey)

From the 2025 survey on memory mechanisms in LLM agents:

| Paradigm | Description | Our Use Case |
|---|---|---|
| **Cumulative** | Complete historical appending | Too expensive; context rot risk |
| **Reflective/Summarized** | Periodically compressed summaries | Best for coaching history |
| **Structured** | Tables, triples, graph-based storage | Best for corner metrics history |
| **Parametric** | Embedding into model weights | Not feasible (we use vendor API) |

The recommended approach for our coaching application is a **hybrid**: structured data for metrics (stored in PostgreSQL) combined with summarized narratives for coaching context (injected into prompts).

Sources:
- [Memory Mechanisms in LLM Agents](https://www.emergentmind.com/topics/memory-mechanisms-in-llm-based-agents)
- [A-Mem: Agentic Memory for LLM Agents](https://arxiv.org/pdf/2502.12110)
- [Memory for AI Agents - The New Stack](https://thenewstack.io/memory-for-ai-agents-a-new-paradigm-of-context-engineering/)

#### 1.4 RAG vs Direct Injection for Coaching History

| Approach | Pros | Cons | Best For |
|---|---|---|---|
| **Direct injection** | Simple, reliable, low latency | Burns tokens, context rot at scale | Small history (< 10 sessions) |
| **RAG with vector search** | Scales to hundreds of sessions | Added complexity, retrieval latency, potential for irrelevant results | Large history, diverse tracks |
| **Hybrid (structured + summary)** | Best of both worlds | More engineering effort | Our recommended approach |

**Recommendation**: Start with direct injection of a structured coaching summary. Our Haiku 4.5 model has a 200k context window but we currently use ~8-12k tokens per coaching prompt. We can allocate ~2-3k tokens for session history without hitting quality degradation.

### Algorithmic Approach: Coaching Memory System

```python
@dataclass
class CoachingMemoryEntry:
    """A single session's coaching memory, stored as structured data."""
    session_id: str
    session_date: datetime
    track_name: str
    best_lap_time_s: float
    top3_avg_time_s: float

    # Per-corner summary (structured, not narrative)
    corner_grades: dict[int, dict[str, str]]  # {corner_num: {braking: "B", ...}}
    priority_corners: list[int]  # corners flagged as priorities
    corner_best_speeds_mph: dict[int, float]  # personal bests per corner

    # Session-level coaching takeaways
    key_strengths: list[str]  # max 3
    key_weaknesses: list[str]  # max 3
    drills_assigned: list[str]  # drills from this session's report

    # Conditions context
    conditions: str | None  # "dry, 25C" or "damp, 15C"
    equipment: str | None  # "RE-71RS, stock brakes"


@dataclass
class DriverCoachingProfile:
    """Longitudinal coaching profile for a driver at a specific track."""
    user_id: str
    track_name: str
    total_sessions: int
    first_session_date: datetime
    latest_session_date: datetime

    # Progression metrics
    best_ever_lap_s: float
    best_ever_session_id: str
    lap_time_progression: list[tuple[datetime, float]]  # (date, best_lap) pairs

    # Corner mastery levels
    corner_mastery: dict[int, CornerMastery]

    # Persistent coaching themes
    recurring_weaknesses: list[str]  # weaknesses that appear in 3+ sessions
    improving_areas: list[str]  # areas showing improvement trend
    plateaued_areas: list[str]  # areas showing no change over 3+ sessions

    # Latest coaching summary (for injection)
    latest_summary: str
    last_drills: list[str]


@dataclass
class CornerMastery:
    """Track mastery at a single corner across sessions."""
    corner_number: int
    sessions_seen: int
    best_min_speed_mph: float
    latest_min_speed_mph: float
    speed_trend: str  # "improving", "plateaued", "regressing"
    best_grade: str  # best-ever overall grade (A-F)
    latest_grade: str  # most recent grade
    grade_history: list[tuple[datetime, str]]  # (date, grade) pairs
```

### Token Budget Allocation

For a standard coaching prompt (~10k tokens), allocate the coaching history as follows:

| Section | Token Budget | Content |
|---|---|---|
| System prompt | ~1,500 | Coaching persona, format instructions |
| Session history injection | ~2,000 | Structured summary (see below) |
| KB snippets | ~500 | Driving technique knowledge |
| Current session data | ~5,000 | Lap times, corner KPIs, gains, analysis |
| Output buffer | ~3,000 | Reserve for response generation |
| **Total** | **~12,000** | Within safe range for Haiku 4.5 |

### Draft Prompt: Session History Injection

```
## Driver History at {track_name}

Sessions: {total_sessions} | First visit: {first_date} | Latest: {latest_date}
Best-ever lap: {best_ever_lap_s:.2f}s (session {best_ever_session_id})
Progression: {formatted_progression}

### Previous Session ({prev_date})
Best lap: {prev_best:.2f}s | Priorities: T{p1}, T{p2}, T{p3}
Drills assigned: {drills_list}
Key takeaway: {prev_summary}

### Corner Mastery Profile
{for each corner}
T{n}: Grade {latest_grade} (trend: {trend}) | Best speed: {best_mph:.1f} mph
{end for}

### Recurring Coaching Themes
- Strengths: {strengths}
- Persistent weaknesses (3+ sessions): {weaknesses}
- Improving areas: {improving}
- Plateaued areas: {plateaued}

### Coaching Instructions
- Reference the driver's history when relevant (e.g., "last session you were
  braking 10m too early at T5 — check if that improved")
- Acknowledge improvement where it occurred ("Your T3 min speed improved from
  {{speed:42}} to {{speed:45}} — great progress")
- If a weakness persists from last session, escalate coaching intensity
- If drills were assigned, check if the data shows they were attempted
```

### Data Model Recommendations

New database tables needed:

```sql
-- Coaching memory: one row per session, per user, per track
CREATE TABLE coaching_memory (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    track_name TEXT NOT NULL,
    session_date TIMESTAMPTZ NOT NULL,
    best_lap_time_s FLOAT NOT NULL,
    top3_avg_time_s FLOAT,

    -- Structured coaching data (JSONB for flexibility)
    corner_grades JSONB,        -- {1: {braking: "B", trail: "C", ...}, ...}
    priority_corners JSONB,     -- [5, 3, 1]
    corner_speeds JSONB,        -- {1: 45.2, 2: 67.8, ...}
    key_strengths JSONB,        -- ["consistent braking", ...]
    key_weaknesses JSONB,       -- ["late throttle T5", ...]
    drills_assigned JSONB,      -- ["brake marker drill T5", ...]

    -- Conditions
    conditions_summary TEXT,
    equipment_summary TEXT,

    -- AI-generated summary (compact, for injection)
    coaching_summary TEXT,       -- 2-3 sentence summary

    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(user_id, session_id)
);

CREATE INDEX ix_coaching_memory_user_track ON coaching_memory(user_id, track_name);
CREATE INDEX ix_coaching_memory_session_date ON coaching_memory(session_date);

-- Driver profile: aggregated longitudinal view, one row per user per track
CREATE TABLE driver_profiles (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    track_name TEXT NOT NULL,
    total_sessions INT DEFAULT 0,
    first_session_date TIMESTAMPTZ,
    latest_session_date TIMESTAMPTZ,
    best_ever_lap_s FLOAT,
    best_ever_session_id TEXT,

    -- Corner mastery (JSONB for per-corner data)
    corner_mastery JSONB,       -- {1: {best_speed: 45.2, trend: "improving", ...}, ...}

    -- Longitudinal patterns
    recurring_weaknesses JSONB, -- ["late throttle T5", ...]
    improving_areas JSONB,
    plateaued_areas JSONB,

    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(user_id, track_name)
);
```

---

## Topic 2: "Corners Gained" Algorithm Design

### Key Findings

#### 2.1 Mark Broadie's Strokes Gained Mathematics

The Strokes Gained formula, developed by Columbia professor Mark Broadie using the PGA Tour's ShotLink system, is:

```
Strokes Gained (shot) = Expected_Strokes(start) - Expected_Strokes(end) - 1
```

Where:
- **Expected_Strokes(start)** = average strokes to hole out from starting position
- **Expected_Strokes(end)** = average strokes to hole out from ending position
- **-1** = accounts for the shot taken

The key insight is the **baseline**: the PGA Tour has recorded millions of shots to establish what a "benchmark" player (scratch golfer = 0 handicap) would do from any position. This allows decomposition: if you gained 0.5 strokes putting but lost 1.2 strokes on approach, your net strokes gained is -0.7.

Arccos extends this by allowing any target handicap as the benchmark, using their database of 200+ million shots. They decompose into five facets: **driving, approach, chipping, sand, putting**.

Sources:
- [Strokes Gained Explained - DIY Golfer](https://www.thediygolfer.com/golf-terms/strokes-gained)
- [Arccos Strokes Gained Analytics](https://www.arccosgolf.com/pages/strokes-gained-analytics)
- [Understanding Strokes Gained - Arccos Blog](https://www.arccosgolf.com/blogs/community/understanding-strokes-gained)
- [Every Shot Counts - Mark Broadie](http://everyshotcounts.com/248-2/)
- [How to Calculate Strokes Gained](https://www.caddiehq.com/resources/how-to-calculate-strokes-gained-in-golf)

#### 2.2 Adaptation: "Corners Gained" for Motorsport

The analogy maps cleanly:

| Golf (Strokes Gained) | Motorsport (Corners Gained) |
|---|---|
| Shot | Corner traversal |
| Expected strokes from position | Expected time through corner at skill level |
| Hole | Full lap |
| Par/scratch benchmark | Personal best or population percentile |
| Five facets | Braking, trail braking, min speed, throttle application, line (apex type) |
| Strokes gained putting | "Seconds gained braking at T5" |

The formula becomes:

```
Corners Gained (T_n) = Expected_Time(T_n, skill_level) - Actual_Time(T_n)
```

Where:
- Positive = you were FASTER than expected (gained time)
- Negative = you were SLOWER than expected (lost time)
- Sum across all corners = total corners gained for the lap

#### 2.3 Establishing the Baseline

The critical challenge is establishing "expected time" at each corner. We have several options:

**Option A: Personal Best as Baseline**
```
Expected_Time(T_n) = personal_best_time(T_n)
Corners_Gained(T_n) = personal_best_time(T_n) - actual_time(T_n)
```
- Pro: Simple, always available, immediately meaningful
- Con: Only measures consistency vs self, doesn't show absolute skill level

**Option B: Population Percentile Baseline** (Arccos-style)
```
Expected_Time(T_n, skill_level) = population_percentile_time(T_n, pct=skill_level)
Corners_Gained(T_n) = expected_time - actual_time
```
- Pro: Shows where you stand vs the population
- Con: Requires population data; track day populations are small

**Option C: Hybrid Baseline** (recommended)
```
Expected_Time(T_n) = weighted_average(
    personal_top5_pct_time(T_n),  # your realistic best
    population_median_time(T_n)    # community average (when available)
)
```

**Recommendation**: Start with Option A (personal best baseline) since we have this data immediately. Add population baselines when we have enough users at each track. This mirrors Arccos's approach: they started with PGA Tour data, then expanded to amateur handicap levels as their dataset grew.

### Algorithmic Approach: Corners Gained

```python
@dataclass
class CornersGainedResult:
    """Corners Gained analysis for a single lap."""
    lap_number: int
    total_gained_s: float  # sum across all corners (positive = faster than expected)
    corner_gains: list[CornerGain]

    # Facet decomposition
    gained_braking_s: float
    gained_min_speed_s: float
    gained_throttle_s: float
    gained_line_s: float


@dataclass
class CornerGain:
    """Gain/loss at a single corner vs baseline."""
    corner_number: int
    gained_s: float  # positive = faster than expected
    expected_time_s: float
    actual_time_s: float

    # Facet breakdown (what contributed to the gain/loss)
    gained_braking_s: float  # time saved/lost from brake point
    gained_min_speed_s: float  # time saved/lost from min speed
    gained_throttle_s: float  # time saved/lost from throttle timing
    gained_line_s: float  # time saved/lost from line choice (apex type)


def compute_corners_gained(
    lap_corners: list[Corner],
    baseline: CornerBaseline,
) -> CornersGainedResult:
    """Compute Corners Gained for a single lap against a baseline.

    Algorithm:
    1. For each corner, compute actual sector time
    2. Compare against baseline expected time
    3. Decompose the difference into facets using sensitivity analysis
    4. Aggregate across corners
    """
    corner_gains = []

    for corner in lap_corners:
        expected_time = baseline.expected_time(corner.number)
        actual_time = corner.sector_time_s
        total_gain = expected_time - actual_time

        # Facet decomposition using sensitivity coefficients
        # These approximate how much each KPI contributes to time
        brake_sensitivity = baseline.brake_time_sensitivity(corner.number)
        speed_sensitivity = baseline.speed_time_sensitivity(corner.number)
        throttle_sensitivity = baseline.throttle_time_sensitivity(corner.number)

        brake_delta = (baseline.expected_brake_m(corner.number)
                      - (corner.brake_point_m or baseline.expected_brake_m(corner.number)))
        speed_delta = ((corner.min_speed_mps * MPS_TO_MPH)
                      - baseline.expected_min_speed_mph(corner.number))
        throttle_delta = (baseline.expected_throttle_m(corner.number)
                        - (corner.throttle_commit_m or baseline.expected_throttle_m(corner.number)))

        gained_braking = brake_delta * brake_sensitivity
        gained_min_speed = speed_delta * speed_sensitivity
        gained_throttle = throttle_delta * throttle_sensitivity

        # Line gain is the residual (what's not explained by the other three)
        gained_line = total_gain - gained_braking - gained_min_speed - gained_throttle

        corner_gains.append(CornerGain(
            corner_number=corner.number,
            gained_s=total_gain,
            expected_time_s=expected_time,
            actual_time_s=actual_time,
            gained_braking_s=gained_braking,
            gained_min_speed_s=gained_min_speed,
            gained_throttle_s=gained_throttle,
            gained_line_s=gained_line,
        ))

    return CornersGainedResult(
        lap_number=lap_corners[0].lap_number if lap_corners else 0,
        total_gained_s=sum(cg.gained_s for cg in corner_gains),
        corner_gains=corner_gains,
        gained_braking_s=sum(cg.gained_braking_s for cg in corner_gains),
        gained_min_speed_s=sum(cg.gained_min_speed_s for cg in corner_gains),
        gained_throttle_s=sum(cg.gained_throttle_s for cg in corner_gains),
        gained_line_s=sum(cg.gained_line_s for cg in corner_gains),
    )


@dataclass
class CornerBaseline:
    """Baseline expected performance at each corner.

    Initially built from personal bests. Later augmented with population data.
    """
    track_name: str
    baseline_type: str  # "personal_best" | "population_p50" | "hybrid"

    # Per-corner expected values
    _expected_times: dict[int, float]
    _expected_brake_m: dict[int, float]
    _expected_min_speed_mph: dict[int, float]
    _expected_throttle_m: dict[int, float]

    # Sensitivity coefficients (seconds per unit of KPI change)
    # Computed from historical data regression or physics model
    _brake_sensitivity: dict[int, float]  # seconds per meter of brake point
    _speed_sensitivity: dict[int, float]  # seconds per mph of min speed
    _throttle_sensitivity: dict[int, float]  # seconds per meter of throttle point

    @classmethod
    def from_personal_bests(
        cls,
        track_name: str,
        corner_records: list[CornerRecord],
        time_values: dict[int, TimeValue],
    ) -> CornerBaseline:
        """Build baseline from personal best corner records.

        Uses time_value data to compute sensitivity coefficients:
        - brake_sensitivity = time_per_meter at approach speed
        - speed_sensitivity = empirical (from corner_analysis correlations)
        - throttle_sensitivity = time_per_meter at exit speed
        """
        # Group by corner, take best sector time for each
        best_by_corner = {}
        for record in corner_records:
            cn = record.corner_number
            if cn not in best_by_corner or record.sector_time_s < best_by_corner[cn].sector_time_s:
                best_by_corner[cn] = record

        expected_times = {cn: r.sector_time_s for cn, r in best_by_corner.items()}
        expected_brake = {cn: r.brake_point_m for cn, r in best_by_corner.items() if r.brake_point_m}
        expected_speed = {cn: r.min_speed_mps * MPS_TO_MPH for cn, r in best_by_corner.items()}

        # Compute sensitivities from time_value data
        brake_sens = {}
        speed_sens = {}
        for cn, tv in time_values.items():
            brake_sens[cn] = tv.time_per_meter_ms / 1000.0  # convert ms/m to s/m
            # Speed sensitivity: approximate as sector_length / speed^2
            # This is a simplification; ideally derived from regression
            speed_sens[cn] = tv.time_per_meter_ms / 1000.0 * 0.5  # heuristic

        return cls(
            track_name=track_name,
            baseline_type="personal_best",
            _expected_times=expected_times,
            _expected_brake_m=expected_brake,
            _expected_min_speed_mph=expected_speed,
            _expected_throttle_m={},
            _brake_sensitivity=brake_sens,
            _speed_sensitivity=speed_sens,
            _throttle_sensitivity={},
        )

    def expected_time(self, corner_number: int) -> float:
        return self._expected_times.get(corner_number, 0.0)

    def expected_brake_m(self, corner_number: int) -> float:
        return self._expected_brake_m.get(corner_number, 0.0)

    def expected_min_speed_mph(self, corner_number: int) -> float:
        return self._expected_min_speed_mph.get(corner_number, 0.0)

    def expected_throttle_m(self, corner_number: int) -> float:
        return self._expected_throttle_m.get(corner_number, 0.0)

    def brake_time_sensitivity(self, corner_number: int) -> float:
        return self._brake_sensitivity.get(corner_number, 0.001)

    def speed_time_sensitivity(self, corner_number: int) -> float:
        return self._speed_sensitivity.get(corner_number, 0.01)

    def throttle_time_sensitivity(self, corner_number: int) -> float:
        return self._throttle_sensitivity.get(corner_number, 0.001)
```

### Cross-Session "Corners Gained" Visualization

The most powerful application is comparing Corners Gained across sessions:

```
Session 1 (March 1): Total CG = -2.4s
  T1: -0.3s  T2: +0.1s  T3: -0.8s  T4: -0.2s  T5: -1.2s

Session 2 (March 15): Total CG = -1.1s
  T1: -0.1s  T2: +0.2s  T3: -0.3s  T4: -0.1s  T5: -0.8s

Improvement: +1.3s gained | Biggest improvement: T3 (+0.5s)
```

### Data Model for Corners Gained

```sql
CREATE TABLE corners_gained (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    track_name TEXT NOT NULL,
    lap_number INT NOT NULL,

    -- Per-corner gains (JSONB array)
    corner_gains JSONB NOT NULL,  -- [{corner: 1, gained_s: -0.3, ...}, ...]

    -- Aggregated facet gains
    total_gained_s FLOAT NOT NULL,
    gained_braking_s FLOAT,
    gained_min_speed_s FLOAT,
    gained_throttle_s FLOAT,
    gained_line_s FLOAT,

    -- Baseline info
    baseline_type TEXT NOT NULL,  -- "personal_best" | "population_p50"

    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX ix_corners_gained_user_track ON corners_gained(user_id, track_name);
```

### Draft Prompt: Corners Gained Injection

```
## Corners Gained Analysis (vs Personal Best Baseline)

This session's best lap: {total_cg:+.2f}s vs your all-time best splits
{for corner in corner_gains, sorted by |gained_s| descending}
T{corner}: {gained_s:+.3f}s ({facet_breakdown})
{end for}

Facet summary:
- Braking: {gained_braking:+.2f}s (are you braking at the same point?)
- Corner speed: {gained_min_speed:+.2f}s (carrying more/less speed?)
- Throttle: {gained_throttle:+.2f}s (getting on gas earlier/later?)
- Line: {gained_line:+.2f}s (taking a better/worse line?)

Use this data to identify WHERE the driver gained or lost time and WHY.
Positive values = faster than their personal best at that corner.
Negative values = slower. Focus coaching on the largest negative values.
```

---

## Topic 3: Flow Lap Detection Algorithm

### Key Findings

#### 3.1 Csikszentmihalyi's Flow Model

Flow is a psychological state of complete immersion in an activity where the challenge level matches the skill level. According to Csikszentmihalyi's model:

- **Flow channel**: Exists when challenge matches skill. Too much challenge = anxiety. Too little = boredom.
- **Flow characteristics**: Loss of self-consciousness, distorted time perception, complete concentration, sense of control, intrinsic motivation.
- **Measurement challenge**: Across 42 studies, flow was operationalized in 24 distinct ways. No consensus on measurement.

However, a systematic review and meta-analysis found a **small to moderate positive relationship** between flow and improved performance, consistent across gaming and sport contexts, with no studies reporting negative relationships.

Sources:
- [Investigating the "Flow" Experience - PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC7033418/)
- [Flow State as a Performance Measure in Esports](https://www.redalyc.org/journal/180/18076225014/html/)
- [Flow and Performance Meta-Analysis](https://www.tandfonline.com/doi/full/10.1080/1750984X.2021.1929402)
- [Flow (Psychology) - Wikipedia](https://en.wikipedia.org/wiki/Flow_(psychology))

#### 3.2 Quantitative Proxy: Performance Data as Flow Indicator

Since we cannot ask the driver if they were in flow, we must infer it from telemetry. The key insight is that flow manifests as **high consistency at near-personal-best performance across all dimensions simultaneously**.

A "flow lap" in motorsport shows:
1. All corners within a tight band of personal best (not just one great corner)
2. Low variance in technique execution (smooth, repeatable inputs)
3. Speed that is fast but not "overdriving" (not at absolute limit)
4. Typically occurs mid-session (not first laps, not when fatigued)

#### 3.3 Plateau vs Flow Detection

Research on performance plateaus using change-point analysis is relevant. Change point detection determines specific locations in a time series when a meaningful change has occurred. We can use this to distinguish:

- **Flow state**: Performance stabilizes at a HIGH level (near personal best, low variance)
- **Plateau**: Performance stabilizes at a MIDDLING level (below capability, stagnant)
- **Overdriving**: Performance is inconsistent at the LIMITS (high speeds but high variance, big mistakes)

Sources:
- [Performance Plateau Detection - PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC8834821/)
- [Change Point Analysis in Sports Training](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0265848)
- [Tractable Algorithms for Changepoint Detection in Player Performance](https://arxiv.org/html/2510.25961v1)

### Algorithmic Approach: Flow Lap Detection

```python
@dataclass
class FlowLapResult:
    """Result of flow lap detection for a session."""
    flow_laps: list[int]  # lap numbers classified as "flow"
    flow_score_per_lap: dict[int, float]  # 0.0-1.0 flow score
    session_flow_window: tuple[int, int] | None  # (start_lap, end_lap) of flow state
    flow_quality: str  # "deep_flow" | "light_flow" | "no_flow"


def detect_flow_laps(
    all_lap_corners: dict[int, list[Corner]],
    lap_summaries: list[LapSummary],
    personal_bests: dict[int, float],  # corner_number -> best sector time
) -> FlowLapResult:
    """Detect flow laps using multi-dimensional consistency analysis.

    A flow lap must satisfy ALL of these criteria:
    1. PROXIMITY: Every corner within X% of personal best
    2. BALANCE: No single corner is an extreme outlier (no "hero corners")
    3. SMOOTHNESS: Low variance in corner execution metrics
    4. TIMING: Not the first 2 laps (warmup) or last 2 (fatigue)
    """

    # Parameters (tunable)
    PROXIMITY_THRESHOLD = 0.05  # within 5% of personal best sector time
    BALANCE_MAX_CV = 0.08  # coefficient of variation across corners
    SMOOTHNESS_PENALTY_THRESHOLD = 0.15  # max allowed technique variance
    WARMUP_LAPS = 2
    COOLDOWN_LAPS = 2
    FLOW_SCORE_THRESHOLD = 0.7

    flow_scores = {}

    valid_laps = [s.lap_number for s in lap_summaries]
    eligible_laps = valid_laps[WARMUP_LAPS:-COOLDOWN_LAPS] if len(valid_laps) > 4 else valid_laps

    for lap_num in valid_laps:
        corners = all_lap_corners.get(lap_num, [])
        if not corners:
            flow_scores[lap_num] = 0.0
            continue

        # 1. PROXIMITY SCORE: how close is each corner to personal best?
        proximity_scores = []
        for corner in corners:
            pb = personal_bests.get(corner.number)
            if pb and pb > 0:
                ratio = corner.sector_time_s / pb
                # 1.0 = at personal best, decays as you get slower
                prox = max(0.0, 1.0 - (ratio - 1.0) / PROXIMITY_THRESHOLD)
                proximity_scores.append(min(1.0, prox))

        # All corners must be near PB (use min, not average)
        proximity_component = min(proximity_scores) if proximity_scores else 0.0

        # 2. BALANCE SCORE: are all corners similarly good?
        if proximity_scores:
            mean_prox = np.mean(proximity_scores)
            std_prox = np.std(proximity_scores)
            cv = std_prox / mean_prox if mean_prox > 0 else 1.0
            balance_component = max(0.0, 1.0 - cv / BALANCE_MAX_CV)
        else:
            balance_component = 0.0

        # 3. SMOOTHNESS SCORE: technique consistency within the lap
        min_speeds = [c.min_speed_mps for c in corners if c.min_speed_mps]
        if len(min_speeds) >= 2:
            speed_cv = np.std(min_speeds) / np.mean(min_speeds)
            smoothness_component = max(0.0, 1.0 - speed_cv / SMOOTHNESS_PENALTY_THRESHOLD)
        else:
            smoothness_component = 0.5  # neutral if not enough data

        # 4. TIMING BONUS: mid-session laps get a small boost
        timing_bonus = 0.1 if lap_num in eligible_laps else 0.0

        # Composite flow score
        flow_score = (
            0.45 * proximity_component +
            0.25 * balance_component +
            0.20 * smoothness_component +
            0.10 * timing_bonus
        )

        flow_scores[lap_num] = min(1.0, flow_score)

    # Identify flow laps
    flow_laps = [
        lap for lap, score in flow_scores.items()
        if score >= FLOW_SCORE_THRESHOLD
    ]

    # Detect flow window (consecutive flow laps)
    flow_window = _find_longest_flow_window(flow_laps)

    # Classify overall session flow quality
    if len(flow_laps) >= 3 and flow_window and (flow_window[1] - flow_window[0]) >= 2:
        flow_quality = "deep_flow"
    elif len(flow_laps) >= 1:
        flow_quality = "light_flow"
    else:
        flow_quality = "no_flow"

    return FlowLapResult(
        flow_laps=sorted(flow_laps),
        flow_score_per_lap=flow_scores,
        session_flow_window=flow_window,
        flow_quality=flow_quality,
    )


def _find_longest_flow_window(flow_laps: list[int]) -> tuple[int, int] | None:
    """Find the longest run of consecutive flow laps."""
    if not flow_laps:
        return None

    sorted_laps = sorted(flow_laps)
    best_start = best_end = sorted_laps[0]
    curr_start = curr_end = sorted_laps[0]

    for i in range(1, len(sorted_laps)):
        if sorted_laps[i] == curr_end + 1:
            curr_end = sorted_laps[i]
        else:
            curr_start = curr_end = sorted_laps[i]

        if (curr_end - curr_start) > (best_end - best_start):
            best_start, best_end = curr_start, curr_end

    return (best_start, best_end) if best_start != best_end else None
```

### Data Model for Flow Detection

```sql
-- Flow analysis results per session
CREATE TABLE flow_analysis (
    id SERIAL PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    track_name TEXT NOT NULL,

    flow_laps JSONB,              -- [4, 5, 6, 7]
    flow_score_per_lap JSONB,     -- {4: 0.85, 5: 0.91, ...}
    flow_window_start INT,
    flow_window_end INT,
    flow_quality TEXT,            -- "deep_flow" | "light_flow" | "no_flow"

    -- For tracking flow frequency over time
    flow_lap_count INT,
    total_laps INT,
    flow_ratio FLOAT,             -- flow_laps / total_laps

    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(session_id)
);
```

### Draft Prompt: Flow Lap Injection

```
## Flow State Analysis

{if flow_quality == "deep_flow"}
This session showed DEEP FLOW: Laps {flow_window_start}-{flow_window_end} were
a sustained run of near-personal-best performance across all corners.
Flow score peaked at {max_score:.0%} on L{peak_lap}.
This is a sign of excellent focus and skill-challenge balance.

Coaching note: The driver's performance during the flow window represents their
TRUE current ability level. Grade based on this window, not warmup/cooldown laps.
{elif flow_quality == "light_flow"}
The driver showed MOMENTS of flow (L{flow_laps}), but did not sustain it.
This suggests the challenge level is slightly above their comfort zone —
they can reach the performance but cannot maintain it consistently yet.
{else}
No flow laps detected. The driver may have been pushing beyond their current
ability (overdriving), dealing with distractions, or still learning the track.
Focus coaching on building consistency before speed.
{end if}
```

---

## Topic 4: Pre-Session Briefing Generation

### Key Findings

#### 4.1 Human Coaching Preparation Patterns

Research on how human coaches prepare pre-session briefings reveals a consistent structure:

1. **Review previous session data** - what happened last time at this track?
2. **Identify top 2-3 focus areas** - not everything, just the highest-leverage items
3. **Set specific, measurable goals** - not "brake better" but "hit the 3-board consistently at T5"
4. **Mental priming** - positive framing, confidence building, reminders of past successes
5. **Conditions check** - weather, track conditions, tire compound, any changes

Sources:
- [Embracing AI - Coach's Guide](https://simplifaster.com/articles/embracing-ai-a-coachs-guide-to-transforming-your-practice/)
- [How AI Is Used in Sports](https://getstream.io/blog/ai-sports/)
- [How Sports Coaches Can Utilize AI](https://www.microsoft.com/en-us/microsoft-365-life-hacks/everyday-ai/how-sports-coaches-can-utilize-ai)

#### 4.2 Goal Setting Theory (Locke & Latham)

Locke and Latham's goal-setting theory is the gold standard for performance improvement:

- **Specific goals outperform vague goals**: "Hit the 3-board at T5 every lap" beats "brake better"
- **Challenging but attainable**: Goals should stretch the driver but remain achievable
- **Performance goals + outcome goals together**: "Carry 2 mph more through T3" (performance) + "Break 1:38" (outcome) work better than outcome goals alone
- **For complex tasks at early learning stages**: LEARNING goals ("focus on feeling brake trail-off") outperform PERFORMANCE goals ("hit X speed")
- **Feedback is essential**: Goals without feedback on progress are ineffective

Critical finding: "Goal-setting theory now suggests that performance goals may hinder performance when an individual is at the early stages of learning a new, complex task and learning goals may be more appropriate."

Sources:
- [Goal Setting Theory Application in Sport - Systematic Review](https://www.tandfonline.com/doi/full/10.1080/1750984X.2021.1901298)
- [Locke's Goal Setting Theory - Positive Psychology](https://positivepsychology.com/goal-setting-theory/)
- [Performance and Psychological Effects of Goal Setting - Meta-Analysis](https://www.tandfonline.com/doi/full/10.1080/1750984X.2022.2116723)
- [Building a Practically Useful Theory of Goal Setting](https://med.stanford.edu/content/dam/sm/s-spire/documents/PD.locke-and-latham-retrospective_Paper.pdf)

#### 4.3 Pre-Performance Priming Effectiveness

Research supports that pre-performance information priming improves outcomes when:
- It is specific and actionable (not generic)
- It references the athlete's own data (personalized)
- It is limited in scope (2-3 items, not a data dump)
- It includes both what to DO and what to FEEL (technique + mindset)

### Algorithmic Approach: Pre-Session Briefing

```python
@dataclass
class PreSessionBriefing:
    """A personalized briefing for the driver before a session."""
    track_name: str
    session_date: datetime

    # Personalized greeting
    greeting: str

    # Focus areas (max 3, selected by algorithm)
    focus_areas: list[FocusArea]

    # Goals (matched to skill level)
    goals: list[SessionGoal]

    # Quick reference card
    corner_reminders: dict[int, str]  # {corner_num: "1-line reminder"}

    # Confidence builder
    recent_wins: list[str]  # things they've improved recently


@dataclass
class FocusArea:
    """A single coaching focus for the session."""
    corner_number: int | None  # None for session-wide focus
    category: str  # "braking" | "trail_braking" | "min_speed" | "throttle" | "consistency"
    description: str  # "Your brake point at T5 has been inconsistent..."
    target: str  # "Hit the 3-board every lap before thinking about braking later"
    measurement: str  # "Success = brake point std < 5m"


@dataclass
class SessionGoal:
    """A specific goal for the session."""
    goal_type: str  # "learning" | "performance" | "outcome"
    description: str
    measurable_target: str | None


def generate_pre_session_briefing(
    driver_profile: DriverCoachingProfile,
    latest_memory: CoachingMemoryEntry | None,
    conditions: SessionConditions | None,
    skill_level: str,
) -> PreSessionBriefing:
    """Generate a pre-session briefing from coaching history.

    Focus area selection algorithm:
    1. Start with previous session's priority corners
    2. Filter to those still showing weakness (not already improved)
    3. Rank by: (a) persistence (how many sessions it's been a problem),
                (b) time cost (how much time it's costing),
                (c) coachability (is it actionable?)
    4. Take top 2-3

    Goal type selection:
    - Novice: learning goals ("focus on feeling smooth brake release")
    - Intermediate: performance goals ("carry 2 mph more through T3")
    - Advanced: outcome goals ("break 1:38") + performance micro-goals
    """

    focus_areas = _select_focus_areas(driver_profile, latest_memory, max_areas=3)
    goals = _generate_goals(driver_profile, focus_areas, skill_level)
    corner_reminders = _build_corner_reminders(driver_profile, focus_areas)
    recent_wins = _identify_recent_wins(driver_profile)

    greeting = _build_greeting(
        driver_profile,
        conditions,
        latest_memory,
    )

    return PreSessionBriefing(
        track_name=driver_profile.track_name,
        session_date=datetime.now(),
        greeting=greeting,
        focus_areas=focus_areas,
        goals=goals,
        corner_reminders=corner_reminders,
        recent_wins=recent_wins,
    )


def _select_focus_areas(
    profile: DriverCoachingProfile,
    latest: CoachingMemoryEntry | None,
    max_areas: int = 3,
) -> list[FocusArea]:
    """Select the highest-leverage focus areas using a scoring algorithm."""

    candidates = []

    for corner_num, mastery in profile.corner_mastery.items():
        if mastery.speed_trend == "improving":
            continue  # skip corners that are already improving

        # Score based on: persistence, time cost, trend
        persistence_score = min(mastery.sessions_seen / 5.0, 1.0)

        # Time cost from latest session
        time_cost = 0.0
        if latest and latest.corner_grades.get(corner_num):
            grades = latest.corner_grades[corner_num]
            grade_cost = {"A": 0, "B": 0.2, "C": 0.5, "D": 0.8, "F": 1.0}
            time_cost = max(grade_cost.get(g, 0.5) for g in grades.values())

        # Plateaued areas get extra weight
        plateau_bonus = 0.3 if mastery.speed_trend == "plateaued" else 0.0

        score = persistence_score * 0.3 + time_cost * 0.5 + plateau_bonus * 0.2

        candidates.append((corner_num, mastery, score))

    # Sort by score descending, take top N
    candidates.sort(key=lambda x: x[2], reverse=True)

    focus_areas = []
    for corner_num, mastery, score in candidates[:max_areas]:
        # Determine the weakest facet for this corner
        category = _weakest_facet(mastery)

        focus_areas.append(FocusArea(
            corner_number=corner_num,
            category=category,
            description=f"T{corner_num} has been a {mastery.speed_trend} area for "
                       f"{mastery.sessions_seen} sessions",
            target=_generate_target(corner_num, category, mastery),
            measurement=_generate_measurement(category, mastery),
        ))

    return focus_areas
```

### Data Model for Briefings

```sql
CREATE TABLE pre_session_briefings (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    track_name TEXT NOT NULL,

    -- Generated briefing content (JSONB)
    briefing_json JSONB NOT NULL,

    -- Tracking: was the briefing viewed? Did the session follow?
    viewed_at TIMESTAMPTZ,
    followed_session_id TEXT,  -- the session that followed this briefing

    -- Was the briefing effective? (post-session check)
    focus_area_results JSONB,  -- {T5: "improved", T3: "no_change"}

    created_at TIMESTAMPTZ DEFAULT now()
);
```

### Draft Prompt: Pre-Session Briefing LLM Generation

```
## Pre-Session Briefing Request

Generate a personalized pre-session briefing for this driver.

### Driver Profile
Track: {track_name}
Sessions here: {total_sessions}
Best-ever lap: {best_ever_lap_s:.2f}s
Skill level: {skill_level}

### Previous Session Summary
Date: {prev_date}
Best lap: {prev_best:.2f}s
Priorities coached: T{p1}, T{p2}, T{p3}
Drills assigned: {drills}

### Selected Focus Areas (algorithm-selected)
{for area in focus_areas}
- T{area.corner_number} ({area.category}): {area.description}
  Target: {area.target}
{end for}

### Recent Wins
{for win in recent_wins}
- {win}
{end for}

### Current Conditions
{conditions_summary}

### Instructions
Write a concise, encouraging pre-session briefing that:
1. Starts with a personalized greeting referencing their history
2. Lists exactly {len(focus_areas)} focus areas with specific, measurable targets
3. Includes one confidence-building reminder of recent improvement
4. Ends with a session-wide goal appropriate for their skill level
5. Total length: 150-200 words (driver should read this in under 1 minute)
6. Tone: like a trusted driving coach walking up to the car at pit lane

{if skill_level == "novice"}
Use LEARNING goals (focus on feel and process, not numbers).
{elif skill_level == "intermediate"}
Use PERFORMANCE goals (specific KPI targets per corner).
{else}
Use OUTCOME goals with micro-performance targets.
{end if}
```

---

## Topic 5: Longitudinal Progress Visualization

### Key Findings

#### 5.1 How Fitness Platforms Visualize Progress

**Strava Athlete Intelligence** (2025):
- Progress summary chart with comparison mode: contrast recent activities against past time ranges
- AI spots personal records and celebrates milestones
- Segment-level progress tracking across activities
- Training Focus recommendations based on longitudinal patterns

**WHOOP**:
- Flexible goal-setting based on 30-day baselines
- Patterns detected across sleep, strain, recovery over time
- Monthly Performance Assessment summarizing trends

**Garmin Connect+**:
- 120+ premade charts for progress visualization
- Personal Records tracking across activities
- Badge/achievement system (100+ badges)
- Performance dashboard with customizable trend graphs

Sources:
- [Strava Athlete Intelligence](https://support.strava.com/hc/en-us/articles/26786795557005-Athlete-Intelligence-on-Strava)
- [Strava Revamps Progress Analytics](https://endurance.biz/2025/industry-news/strava-revamps-athlete-intelligence-leaderboards-flyovers-and-progress-analytics/)
- [WHOOP 2025 Roadmap](https://www.whoop.com/us/en/thelocker/inside-look-whats-next-for-whoop-in-2025/)
- [Garmin Connect Performance Dashboard](https://www.garmin.com/en-US/blog/fitness/what-is-the-garmin-connect-performance-dashboard/)
- [Garmin Badge Database](https://garminbadges.com/faq.php)
- [Fitness App Engagement Strategies](https://orangesoft.co/blog/strategies-to-increase-fitness-app-engagement-and-retention)

#### 5.2 The Progress Principle (Amabile & Kramer)

Teresa Amabile and Steven Kramer's research on 12,000+ diary entries from 238 knowledge workers found:

- **The single most important factor** for motivation and engagement was making progress in meaningful work
- Even **minor steps forward** triggered outsize positive reactions: 28% of incidents with minor project impact had MAJOR impact on feelings
- The most common "best day" trigger was ANY progress; the most common "worst day" trigger was a setback
- **Six enablers**: clear goals, autonomy, resources, ample time, support, expertise

This has direct implications for our progress visualization: we should design visualizations that **surface small wins prominently**, even when the driver isn't setting personal bests.

Sources:
- [The Power of Small Wins - HBR](https://hbr.org/2011/05/the-power-of-small-wins)
- [Amabile and Kramer's Progress Theory](https://www.mindtools.com/arzm8fy/amabile-and-kramers-progress-theory/)
- [Using Small Wins to Enhance Motivation](https://cleverism.com/amabile-and-kramers-progress-theory-using-small-wins-to-enhance-motivation/)

#### 5.3 Handling Regressions

Bad sessions are inevitable. Research and UX best practices suggest:

- **Normalize regressions**: Show them in context ("5 out of 6 sessions showed improvement")
- **Attribute regressions**: Automatically flag condition differences (rain, heat, tired tires)
- **Show trend lines, not just points**: A regression on a rising trend line is less discouraging
- **"Range of performance" visualization**: Show the band of typical performance, not just best/worst
- **Recovery framing**: "You had a tough session, but your next 3 at this track showed a 2.1s improvement"

### Algorithmic Approach: Milestone Detection

```python
@dataclass
class Milestone:
    """A detected achievement milestone."""
    milestone_type: str  # categories below
    description: str  # human-readable description
    session_id: str
    session_date: datetime
    value: float  # the numeric value that triggered the milestone
    previous_value: float | None  # for comparison
    significance: str  # "major" | "minor" | "micro"


# Milestone categories
MILESTONE_TYPES = {
    # Lap time milestones
    "personal_best_lap": "New personal best lap time",
    "time_barrier_broken": "Broke through a time barrier (e.g., sub-1:40)",
    "top3_avg_improvement": "Top-3 average improved",

    # Corner milestones
    "corner_personal_best": "New personal best at a specific corner",
    "corner_grade_upgrade": "Corner grade improved (e.g., C -> B)",
    "all_corners_B_or_better": "All corners graded B or better",

    # Consistency milestones
    "consistency_improvement": "Lap-to-lap consistency improved",
    "first_sub_X_consistency": "First session with consistency score > threshold",

    # Flow milestones
    "first_flow_lap": "First detected flow lap at this track",
    "flow_window_extended": "Longest sustained flow window",

    # Session milestones
    "session_count": "Nth session at this track (5th, 10th, 25th, 50th)",
    "streak": "Consecutive sessions with improvement",

    # Corners Gained milestones
    "positive_corners_gained": "First session with positive overall Corners Gained",
    "all_corners_positive": "All corners at or better than personal best baseline",
}


def detect_milestones(
    current_session: SessionSummary,
    session_history: list[SessionSummary],
    driver_profile: DriverCoachingProfile,
) -> list[Milestone]:
    """Detect milestones by comparing current session against history.

    Algorithm:
    1. Check each milestone type against current session data
    2. Compare with historical values from driver_profile
    3. Classify significance:
       - Major: personal best lap, time barrier broken, streak milestone
       - Minor: corner improvement, consistency improvement
       - Micro: small wins (0.1s improvement at a corner, etc.)
    """
    milestones = []

    # Personal best lap
    if current_session.best_lap_time_s < driver_profile.best_ever_lap_s:
        improvement = driver_profile.best_ever_lap_s - current_session.best_lap_time_s
        milestones.append(Milestone(
            milestone_type="personal_best_lap",
            description=f"New PB! {current_session.best_lap_time_s:.2f}s "
                       f"({improvement:.2f}s faster)",
            session_id=current_session.session_id,
            session_date=current_session.session_date,
            value=current_session.best_lap_time_s,
            previous_value=driver_profile.best_ever_lap_s,
            significance="major",
        ))

    # Time barrier broken (e.g., first time under 1:40, 1:35, etc.)
    barriers = _compute_time_barriers(driver_profile.best_ever_lap_s)
    for barrier in barriers:
        if current_session.best_lap_time_s < barrier <= driver_profile.best_ever_lap_s:
            minutes = int(barrier // 60)
            seconds = int(barrier % 60)
            milestones.append(Milestone(
                milestone_type="time_barrier_broken",
                description=f"Broke the {minutes}:{seconds:02d} barrier!",
                session_id=current_session.session_id,
                session_date=current_session.session_date,
                value=current_session.best_lap_time_s,
                previous_value=barrier,
                significance="major",
            ))

    # Corner personal bests
    for corner_num, mastery in driver_profile.corner_mastery.items():
        current_speed = current_session.corner_speeds.get(corner_num)
        if current_speed and current_speed > mastery.best_min_speed_mph:
            milestones.append(Milestone(
                milestone_type="corner_personal_best",
                description=f"New best speed at T{corner_num}: "
                           f"{current_speed:.1f} mph (+{current_speed - mastery.best_min_speed_mph:.1f})",
                session_id=current_session.session_id,
                session_date=current_session.session_date,
                value=current_speed,
                previous_value=mastery.best_min_speed_mph,
                significance="minor",
            ))

    # Session count milestones
    count = driver_profile.total_sessions + 1
    if count in {5, 10, 25, 50, 100}:
        milestones.append(Milestone(
            milestone_type="session_count",
            description=f"Session #{count} at {driver_profile.track_name}!",
            session_id=current_session.session_id,
            session_date=current_session.session_date,
            value=count,
            previous_value=None,
            significance="minor",
        ))

    return milestones


def _compute_time_barriers(best_time_s: float) -> list[float]:
    """Generate meaningful time barriers near the driver's pace.

    For a 1:42 driver, barriers would be: 1:42, 1:41, 1:40, 1:39, etc.
    We only care about round-number barriers (multiples of 5 seconds
    when above 2:00, multiples of 1 second when below).
    """
    barriers = []
    base = int(best_time_s)

    # Check every second below current best
    for target in range(base, base - 10, -1):
        if target > 0 and target < best_time_s:
            # Only include "round" barriers (divisible by 5 or exactly on the minute)
            secs = target % 60
            if secs % 5 == 0 or secs == 0:
                barriers.append(float(target))

    return barriers
```

### Visualization Design Recommendations

Based on the research, here is the recommended visualization hierarchy for our progress page:

```
+----------------------------------------------------------+
| HERO: Latest Session Summary                              |
| "Session 12 at Barber: 1:38.2 (PB!) | 3 Milestones"     |
+----------------------------------------------------------+
|                                                           |
| SECTION 1: Milestones Timeline                            |
| [Medal] Broke 1:40 barrier    [Star] PB at T5            |
| [Fire] 3-session improvement streak                       |
|                                                           |
+----------------------------------------------------------+
|                                                           |
| SECTION 2: Lap Time Trend                                 |
| Line chart: best_lap and top3_avg over sessions           |
| Show trend line + "range of performance" band             |
| Highlight PB sessions and regression sessions differently |
|                                                           |
+----------------------------------------------------------+
|                                                           |
| SECTION 3: Corner Mastery Heatmap                         |
| Rows: Sessions (dates)  |  Cols: Corners (T1-T11)        |
| Color: grade (green=A, yellow=C, red=F)                   |
| Shows where improvement is happening corner by corner     |
|                                                           |
+----------------------------------------------------------+
|                                                           |
| SECTION 4: Corners Gained Waterfall                       |
| Stacked bar: which corners gained/lost time vs baseline   |
| Compare across last 3 sessions                            |
|                                                           |
+----------------------------------------------------------+
|                                                           |
| SECTION 5: Flow Lap Frequency                             |
| Bar chart: % of laps in flow state per session            |
| Shows: "You're spending more time in the zone"            |
|                                                           |
+----------------------------------------------------------+
```

### Data Model for Progress

The existing `sessions` table already stores most needed fields (`best_lap_time_s`, `top3_avg_time_s`, `consistency_score`). New tables:

```sql
CREATE TABLE milestones (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    track_name TEXT NOT NULL,

    milestone_type TEXT NOT NULL,
    description TEXT NOT NULL,
    value FLOAT,
    previous_value FLOAT,
    significance TEXT NOT NULL,  -- "major" | "minor" | "micro"

    -- For display
    icon TEXT,
    celebrated BOOLEAN DEFAULT FALSE,  -- user saw the celebration animation

    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX ix_milestones_user_track ON milestones(user_id, track_name);
```

### Draft Prompt: Progress Context Injection

```
## Longitudinal Progress Context

{if milestones}
### Recent Milestones
{for m in milestones}
- [{m.significance.upper()}] {m.description}
{end for}

Acknowledge these achievements in your coaching! Celebrate improvement.
{end if}

### Trend Analysis
Lap time trend over {n_sessions} sessions: {trend_direction}
- Best ever: {best_ever_s:.2f}s ({best_ever_date})
- Last 3 avg: {last3_avg_s:.2f}s
- Improvement rate: ~{improvement_rate_s:.2f}s per session

{if regressions}
Note: Session on {regression_date} showed a regression ({regression_time_s:.2f}s).
Likely cause: {regression_attribution} (do NOT blame the driver's technique
unless the data clearly supports it).
{end if}
```

---

## Topic 6: Session Comparison Intelligence

### Key Findings

#### 6.1 Normalization Challenges in Motorsport

Several factors affect lap times independently of driver technique:

| Factor | Impact | Measurability |
|---|---|---|
| **Track temperature** | 0.1-0.5s per 10C change | Moderate (can estimate from weather API) |
| **Tire degradation** | 0.1-0.3s per session quarter | Moderate (detectable from lap time trend) |
| **Track rubber** | 0.1-0.5s improvement through day | Low (requires multiple sessions same day) |
| **Fuel load** | Negligible for track days | N/A |
| **Wind** | 0.1-0.3s depending on track | Low (variable across the lap) |
| **Humidity** | 0.05-0.1s (affects engine power) | Moderate (weather API) |

Key research finding from ACC (sim racing) analysis: "A change in temperature of even a couple of degrees in circuit asphalt temperature can cost tenths of a second on each lap." In real racing, moving outside the tire's operating window by a few degrees can shift performance significantly.

Sources:
- [Track Surface & Temperature Impact on F1](https://www.catapult.com/blog/race-strategy-f1-track-surface)
- [ACC Track Temperature Impact on Lap Times](https://solox.gg/acc-track-temperatures/)
- [Effect of Track Temperature on Tire Degradation](https://www.prismaelectronics.com/en/blog/effect-track-temperature-tire-degradation)
- [Context Normalization in Sports Analytics](https://www.nature.com/articles/s41598-022-05089-y)
- [Weather Impact on Sports Performance](https://blog.weatherapplied.com/modeling-the-impact-of-the-atmosphere-on-sport/)

#### 6.2 Normalization Approaches from Sports Analytics

Research identifies several applicable normalization strategies:

1. **Z-score normalization**: Normalize metrics to athlete- and session-specific baselines
2. **Context-specific preprocessing**: Use domain-specific factors (like tire compound) as normalizing factors
3. **Residual analysis**: Fit a model to predict expected performance given conditions, then analyze residuals (technique component)
4. **Paired comparison**: Compare same-condition sessions only, flag different-condition comparisons

#### 6.3 Session Quality Score

A "session quality score" should factor in:
- How close the driver got to their potential (adjusted for conditions)
- Consistency within the session
- Improvement trajectory within the session
- Flow state metrics
- How conditions affected the raw times

### Algorithmic Approach: Condition-Normalized Comparison

```python
@dataclass
class ConditionNormalization:
    """Factors for normalizing lap times across different conditions."""
    temperature_adjustment_s: float  # estimated time impact from temp difference
    track_condition_adjustment_s: float  # dry vs damp vs wet
    tire_degradation_adjustment_s: float  # based on position in session
    total_adjustment_s: float
    confidence: float  # 0.0-1.0, how reliable is this adjustment
    explanation: str  # human-readable explanation


@dataclass
class SessionQualityScore:
    """Composite session quality metric (0-100)."""
    overall_score: float  # 0-100

    # Component scores (each 0-100)
    pace_score: float  # how close to personal best (condition-adjusted)
    consistency_score: float  # how consistent were the laps
    improvement_score: float  # did the driver improve through the session
    flow_score: float  # what % of laps were in flow
    technique_score: float  # average corner grades

    # Condition context
    condition_adjustment_s: float  # total condition adjustment applied
    condition_confidence: float


def compute_condition_normalization(
    session_a_conditions: SessionConditions | None,
    session_b_conditions: SessionConditions | None,
    track_name: str,
) -> ConditionNormalization:
    """Estimate time adjustment between two sessions' conditions.

    Uses simple heuristics based on motorsport engineering knowledge.
    These are rough estimates, not precise physics models.
    """
    if session_a_conditions is None or session_b_conditions is None:
        return ConditionNormalization(
            temperature_adjustment_s=0.0,
            track_condition_adjustment_s=0.0,
            tire_degradation_adjustment_s=0.0,
            total_adjustment_s=0.0,
            confidence=0.0,
            explanation="Conditions data not available for comparison",
        )

    # Temperature adjustment
    # Rough heuristic: ~0.05s per degree C for a typical 1:30-2:00 lap
    # Cooler track = less grip = slower (positive adjustment = slower expected)
    temp_diff = 0.0
    if (session_a_conditions.ambient_temp_c is not None and
        session_b_conditions.ambient_temp_c is not None):
        temp_diff = session_a_conditions.ambient_temp_c - session_b_conditions.ambient_temp_c
    temperature_adj = temp_diff * 0.05  # seconds per degree

    # Track condition adjustment
    CONDITION_FACTORS = {
        "dry": 0.0,
        "damp": 3.0,  # ~3 seconds slower in damp
        "wet": 8.0,   # ~8 seconds slower in wet
    }
    cond_a = CONDITION_FACTORS.get(session_a_conditions.track_condition.value, 0.0)
    cond_b = CONDITION_FACTORS.get(session_b_conditions.track_condition.value, 0.0)
    condition_adj = cond_a - cond_b

    total = temperature_adj + condition_adj

    # Confidence based on how much data we have
    confidence = 0.3  # base confidence for heuristic model
    if session_a_conditions.ambient_temp_c and session_b_conditions.ambient_temp_c:
        confidence += 0.2
    if session_a_conditions.track_condition and session_b_conditions.track_condition:
        confidence += 0.3

    explanation_parts = []
    if abs(temperature_adj) >= 0.1:
        explanation_parts.append(
            f"Temperature difference: {abs(temp_diff):.0f}C "
            f"(~{abs(temperature_adj):.1f}s impact)"
        )
    if abs(condition_adj) >= 0.5:
        explanation_parts.append(
            f"Track condition: {session_a_conditions.track_condition.value} vs "
            f"{session_b_conditions.track_condition.value} "
            f"(~{abs(condition_adj):.1f}s impact)"
        )

    return ConditionNormalization(
        temperature_adjustment_s=temperature_adj,
        track_condition_adjustment_s=condition_adj,
        tire_degradation_adjustment_s=0.0,
        total_adjustment_s=total,
        confidence=min(1.0, confidence),
        explanation="; ".join(explanation_parts) if explanation_parts else "Similar conditions",
    )


def compute_session_quality_score(
    session: SessionData,
    driver_profile: DriverCoachingProfile,
    flow_result: FlowLapResult,
    condition_adjustment_s: float = 0.0,
) -> SessionQualityScore:
    """Compute a composite session quality score (0-100).

    Each component is scored independently and weighted:
    - Pace (30%): how close to PB, adjusted for conditions
    - Consistency (25%): coefficient of variation of lap times
    - Improvement (15%): did laps get faster through the session
    - Flow (15%): percentage of laps in flow state
    - Technique (15%): average corner grades
    """

    # Pace score: 100 = at PB, decays linearly
    adjusted_best = session.best_lap_time_s + condition_adjustment_s
    pace_gap = adjusted_best - driver_profile.best_ever_lap_s
    pace_score = max(0.0, 100.0 - pace_gap * 20.0)  # lose 20pts per second

    # Consistency score: based on CV of clean lap times
    if session.lap_times and len(session.lap_times) >= 3:
        cv = np.std(session.lap_times) / np.mean(session.lap_times)
        consistency_score = max(0.0, 100.0 - cv * 500.0)  # 2% CV = 90, 4% CV = 80
    else:
        consistency_score = 50.0

    # Improvement score: compare first half vs second half avg
    if session.lap_times and len(session.lap_times) >= 4:
        mid = len(session.lap_times) // 2
        first_half = np.mean(session.lap_times[:mid])
        second_half = np.mean(session.lap_times[mid:])
        improvement = first_half - second_half  # positive = improved
        improvement_score = 50.0 + improvement * 30.0  # gain 30pts per second of improvement
        improvement_score = max(0.0, min(100.0, improvement_score))
    else:
        improvement_score = 50.0

    # Flow score
    flow_ratio = len(flow_result.flow_laps) / max(1, len(session.lap_times))
    flow_score = min(100.0, flow_ratio * 200.0)  # 50% flow laps = 100

    # Technique score: average grades
    grade_values = {"A": 100, "B": 80, "C": 60, "D": 40, "F": 20}
    if session.corner_grades:
        all_grades = []
        for grades in session.corner_grades.values():
            for grade in grades.values():
                all_grades.append(grade_values.get(grade, 50))
        technique_score = np.mean(all_grades) if all_grades else 50.0
    else:
        technique_score = 50.0

    # Weighted composite
    overall = (
        pace_score * 0.30 +
        consistency_score * 0.25 +
        improvement_score * 0.15 +
        flow_score * 0.15 +
        technique_score * 0.15
    )

    return SessionQualityScore(
        overall_score=round(overall, 1),
        pace_score=round(pace_score, 1),
        consistency_score=round(consistency_score, 1),
        improvement_score=round(improvement_score, 1),
        flow_score=round(flow_score, 1),
        technique_score=round(technique_score, 1),
        condition_adjustment_s=condition_adjustment_s,
        condition_confidence=0.5,
    )
```

### Tire Degradation Detection

```python
def detect_tire_degradation(
    lap_times: list[float],
    min_laps: int = 6,
) -> tuple[float, bool]:
    """Detect tire degradation from lap time trend.

    Returns (degradation_rate_s_per_lap, is_significant).

    Algorithm:
    1. Fit a linear regression to lap times (excluding first 2 warmup laps)
    2. If slope is positive and significant, tires are degrading
    3. A positive slope > 0.1s/lap is considered significant for track days
    """
    if len(lap_times) < min_laps:
        return 0.0, False

    # Skip first 2 laps (warmup)
    analysis_times = lap_times[2:]
    x = np.arange(len(analysis_times))

    # Linear regression
    slope, intercept = np.polyfit(x, analysis_times, 1)

    # Significance: is the R^2 reasonable?
    predicted = slope * x + intercept
    ss_res = np.sum((analysis_times - predicted) ** 2)
    ss_tot = np.sum((analysis_times - np.mean(analysis_times)) ** 2)
    r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else 0

    is_significant = slope > 0.1 and r_squared > 0.3

    return slope, is_significant
```

### Data Model for Session Comparison

```sql
-- Session comparison results
CREATE TABLE session_comparisons (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_a_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    session_b_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    track_name TEXT NOT NULL,

    -- Normalization
    condition_adjustment_s FLOAT,
    condition_confidence FLOAT,
    normalization_explanation TEXT,

    -- Session quality scores
    session_a_quality JSONB,
    session_b_quality JSONB,

    -- Corner-by-corner comparison
    corner_comparison JSONB,  -- [{corner: 1, time_delta: -0.3, speed_delta: 2.1, ...}]

    -- AI-generated narrative
    comparison_narrative TEXT,

    created_at TIMESTAMPTZ DEFAULT now()
);
```

### Draft Prompt: Session Comparison Intelligence

```
## Cross-Session Comparison Context

### Session A: {date_a} (reference)
Best lap: {best_a:.2f}s | Quality score: {quality_a}/100
Conditions: {conditions_a}

### Session B: {date_b} (current)
Best lap: {best_b:.2f}s | Quality score: {quality_b}/100
Conditions: {conditions_b}

### Condition Normalization
{normalization_explanation}
Adjusted delta: {adjusted_delta:+.2f}s (confidence: {confidence:.0%})
{if confidence < 0.5}
WARNING: Condition adjustment has LOW confidence. Be cautious attributing
time differences to technique vs conditions.
{end if}

### Corner-by-Corner Deltas (Session B - Session A)
{for corner in corner_comparisons}
T{corner.number}: {corner.time_delta:+.3f}s | Speed: {corner.speed_delta:+.1f} mph |
  Brake: {corner.brake_delta:+.0f}m
{end for}

### Tire Degradation
{if degradation_detected}
Session B showed tire degradation of ~{deg_rate:.2f}s/lap after lap {onset_lap}.
Discount late-session lap times accordingly.
{end if}

### Coaching Instructions
1. When comparing these sessions, always account for the condition difference
2. Focus on TECHNIQUE changes (brake point, line, throttle timing) not raw times
3. Celebrate improvements even if raw times are slower (conditions may explain it)
4. If a corner improved in technique metrics but not time, the conditions likely masked it
```

---

## Implementation Roadmap

### Phase 1: Foundation (Week 1-2)
1. **Database migrations**: Add `coaching_memory`, `driver_profiles`, `milestones` tables
2. **Coaching memory extraction**: After each coaching report, extract and persist structured memory
3. **Driver profile builder**: Aggregate coaching memories into longitudinal profiles
4. **Memory injection into prompts**: Add session history section to `_build_coaching_prompt()`

### Phase 2: Corners Gained (Week 2-3)
1. **Baseline builder**: Build personal best baselines from `corner_records` table
2. **Corners Gained calculator**: Implement the algorithm above
3. **Frontend: Corners Gained waterfall chart**: D3 visualization
4. **Inject into coaching**: Add Corners Gained section to prompts

### Phase 3: Flow + Milestones (Week 3-4)
1. **Flow lap detector**: Implement and add to session processing pipeline
2. **Milestone detector**: Implement and trigger post-upload
3. **Frontend: Milestone celebrations**: Confetti/badge UI
4. **Frontend: Flow indicator**: Show flow laps on speed trace

### Phase 4: Briefings + Comparison (Week 4-5)
1. **Pre-session briefing generator**: LLM-powered with focus area selection
2. **Session comparison normalization**: Condition adjustment algorithms
3. **Session quality score**: Compute and display
4. **Frontend: Pre-session briefing card**: Show when driver returns to a track

### Phase 5: Refinement (Week 5-6)
1. **Population baselines**: As user count grows, add community percentile baselines
2. **Sensitivity coefficient calibration**: Use actual data to tune time-per-KPI sensitivities
3. **A/B test briefing effectiveness**: Track if briefed drivers improve more
4. **Flow threshold tuning**: Calibrate based on user feedback

---

## Integration with Existing Codebase

### Key Files to Modify

| File | Changes |
|---|---|
| `cataclysm/coaching.py` | Add `_format_session_history()`, modify `_build_coaching_prompt()` to accept history |
| `backend/api/db/models.py` | Add `CoachingMemory`, `DriverProfile`, `Milestone`, `FlowAnalysis` models |
| `backend/api/services/coaching_store.py` | Add memory extraction after report storage |
| `backend/api/routers/coaching.py` | Add `/briefing` endpoint, `/milestones` endpoint |
| `cataclysm/gains.py` | Add `CornersGained` alongside existing gain tiers |
| `cataclysm/corner_analysis.py` | Add flow detection to session analysis pipeline |

### New Files to Create

| File | Purpose |
|---|---|
| `cataclysm/coaching_memory.py` | Memory extraction and profile building |
| `cataclysm/corners_gained.py` | Corners Gained algorithm |
| `cataclysm/flow_detection.py` | Flow lap detection algorithm |
| `cataclysm/milestones.py` | Milestone detection |
| `cataclysm/session_comparison.py` | Condition normalization and quality scoring |
| `cataclysm/briefing.py` | Pre-session briefing generation |
| `backend/api/routers/progress.py` | Progress/milestone API endpoints |
| `frontend/src/components/CornersGainedChart.tsx` | Waterfall visualization |
| `frontend/src/components/MilestoneCard.tsx` | Milestone celebrations |
| `frontend/src/components/FlowIndicator.tsx` | Flow state visualization |
| `frontend/src/components/PreSessionBriefing.tsx` | Briefing card component |

### Token Budget Validation

With all new context sections, the prompt budget for a full coaching report with history:

| Section | Tokens (est.) |
|---|---|
| System prompt | 1,500 |
| Session history (Topic 1) | 2,000 |
| Corner analysis | 3,000 |
| Lap times + KPIs | 2,000 |
| Corners Gained (Topic 2) | 800 |
| Flow analysis (Topic 3) | 400 |
| Gains (existing) | 600 |
| Landmarks (existing) | 500 |
| Equipment/Weather | 300 |
| Format instructions | 900 |
| **Total input** | **~12,000** |
| Output budget | ~4,000 |
| **Total** | **~16,000** |

This is well within Haiku 4.5's 200k context window and keeps the effective usage in the accuracy-stable range (< 80% of window).

---

## Summary of Key Architectural Decisions

1. **Hybrid memory**: Structured data in PostgreSQL + summarized narrative for prompt injection. No vector DB needed initially.

2. **Personal best baseline first**: Start Corners Gained with personal bests, add population baselines when data allows. Mirrors Arccos's growth strategy.

3. **Flow as a composite score**: Rather than binary flow/not-flow, use a 0-1 score that accounts for proximity, balance, smoothness, and timing.

4. **Learning goals for novices**: Follow Locke & Latham — novice drivers get process-focused goals, not performance targets.

5. **Condition normalization with confidence**: Always show how confident we are in the adjustment. Low-confidence adjustments get flagged in the prompt so the LLM doesn't over-attribute to technique.

6. **Small wins celebration**: Following Amabile's Progress Principle, surface minor improvements prominently. A 0.1s corner improvement matters.

7. **Token-conscious injection**: Every section has a token budget. History doesn't crowd out current session data.
