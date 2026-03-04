# AI Coaching System: Iteration 3 Final Synthesis — Implementation-Ready Research

**Date**: 2026-03-04
**Iteration**: 3 of 3 (Ralph Loop — Final)
**Research scope**: 100+ web searches, 30+ deep page fetches across 4 parallel research agents
**Total research corpus**: ~10,000 lines across 3 iterations, 8 agent reports, 200+ unique sources

---

## Executive Summary

Three iterations of deep research have produced a complete blueprint for transforming Cataclysm's AI coaching from "good automated analysis" into "better than AiM Solo + a dedicated coach." The research converges on **five major capability gaps** that, when closed, create an insurmountable competitive moat:

1. **Prompt architecture** — Temperature, XML tags, golden examples, and causal reasoning instructions (hours of work, massive quality uplift)
2. **Inter-corner causal chains** — Detect cascading errors, identify root causes, match Track Titan's TimeKiller (our #1 competitive gap)
3. **Adaptive skill-level coaching** — Auto-detect driver skill from telemetry, tailor language/depth/focus per archetype
4. **Longitudinal intelligence** — Session memory, Corners Gained, flow lap detection, pre-session briefings
5. **Evidence-anchored grading** — RULERS-style rubrics with measurable thresholds, preventing grade inflation

This synthesis distills all four Iteration 3 deep-dives into a unified, prioritized implementation roadmap.

---

## Part 1: Convergent Findings Across All Research Streams

### Finding 1: The "Known Physics" Advantage

All four research streams converge on this: **our problem domain has known physics**. Unlike generic AI coaching where causal discovery is hard, motorsport telemetry has:
- Known temporal ordering (T3 always precedes T4)
- Known physical mechanisms (v² = v₀² + 2ad)
- Pre-computed numerical analysis (corner stats already extracted)

This means we DON'T need heavyweight ML/causal-inference libraries (DoWhy, Bayesian networks, Granger causality). Simple statistics + physics equations outperform learned models at our data scale (8-20 laps per session). This is a major architectural simplification.

### Finding 2: The Haiku 4.5 Sweet Spot

Research confirms our model choice is correct, but we're underutilizing Haiku 4.5's capabilities:
- **Temperature**: Currently unset (defaults to 1.0 — far too high). Setting to 0.3 is the single highest-impact change
- **XML tags**: Claude was specifically trained to parse XML. Switching from markdown headers to XML tags improves parsing by ~30%
- **Data ordering**: Anthropic's own testing shows 30% quality improvement with data-first, instructions-last
- **Golden examples**: 2-3 examples is the sweet spot for Haiku (too many degrades via "few-shot dilemma")
- **Structured outputs**: Available on Haiku 4.5, guarantees JSON validity independent of temperature

### Finding 3: External Focus Trumps Internal at ALL Skill Levels

The motor learning literature is unambiguous across hundreds of studies:
- External focus ("the car should slow more aggressively") > internal focus ("press the brake harder") at EVERY skill level
- The "distance effect" — novices benefit from proximal external cues, experts from distal ones
- Our current prompt sometimes uses internal focus language. This is fixable in hours.

### Finding 4: Less Feedback = Better Retention (The Guidance Hypothesis)

Counter-intuitive but well-established: drivers who receive feedback on 33% of items outperform those receiving 100% feedback on retention tests. This scientifically validates our existing 3-priority-corner approach AND suggests:
- **Novices**: 1-2 priorities (align with Ross Bentley's 2-directive rule)
- **Intermediate**: 2-3 priorities
- **Advanced**: 3-4 priorities with inter-corner chain analysis

### Finding 5: Warmth Instructions Degrade Accuracy

The Oxford 2025 study is alarming: adding "be warm and empathetic" to LLM instructions increases error rates by 10-30%. Our current instruction "be encouraging but honest" is borderline safe, but we should:
- Replace "be encouraging" with "cite specific data-backed strengths"
- Let positive tone come from OIS structure (observations lead with strengths)
- NEVER add explicit warmth instructions

### Finding 6: The Autonomy-Support Effect

OPTIMAL Theory (Wulf & Lewthwaite 2016) shows three factors work additively for motor learning:
1. Enhanced Expectancies (growth mindset framing — we partially do this)
2. Autonomy Support (giving choices — we DON'T do this)
3. External Focus (referencing environment — we partially do this)

For intermediate+ drivers, framing tips as experiments ("Try braking at the 3-board for 3 laps and compare your data") instead of commands ("Brake at the 3-board") significantly improves learning outcomes.

### Finding 7: "Because" Clauses Increase Acceptance by 41%

Bank of America's AI coaching research: explaining WHY a recommendation is made increases user acceptance by 41%. Every coaching tip should include a data-backed "because" clause:
- BAD: "Try braking later at T5"
- GOOD: "Try braking at the 2-board at T5, because your current brake point (3-board) leaves 8m of unused straight-line braking, costing ~0.3s per lap"

---

## Part 2: The Four Capability Pillars (Deep-Dive Summaries)

### Pillar 1: Prompt Architecture Overhaul
**Source document**: `coaching_prompt_engineering_iteration3.md` (565 lines)

**Key deliverables**:

| Change | Impact | Current State |
|--------|--------|---------------|
| Set temperature=0.3 | Consistency + accuracy | Unset (defaults to 1.0) |
| XML tag restructuring | ~30% parsing improvement | Markdown headers |
| Data-first, instructions-last | ~30% quality improvement | Interleaved |
| 2 golden examples (gold + anti) | Calibrates grading, tone, causal reasoning | No examples |
| 5-step causal chain decomposition | Prevents symptom-as-cause coaching | No causal instruction |
| Evidence-anchored rubric (RULERS) | Prevents grade inflation | Vague rubric |
| Grade distribution expectations | Bell curve around B/C, not A/B | No distribution guidance |
| Evidence-before-grading instruction | More reliable grading | Grade-then-justify |
| Uncertainty admission | "Data inconclusive" > hallucinated causes | No uncertainty instruction |

**Golden example design**:
- Example A: Full gold-standard report for intermediate driver at Barber — OIS format, calibrated grades, causal patterns, landmark references, kinesthetic language
- Example B: Contrastive anti-example with `[WRONG]` and `[BETTER]` annotations showing grade inflation, vague tips, missing causation, internal focus

**Grading rubric overhaul** (per-criterion, evidence-anchored):
- BRAKING: A = std < 3m + peak G within 0.05G ... F = no consistent brake point
- TRAIL BRAKING: A = present 90%+ of laps ... D = no trail braking detected ... N/A = kinks/lifts
- MIN SPEED: A = std < 1.0 mph + within 1 mph target ... F = 5+ mph below target
- THROTTLE: A = commit std < 5m + progressive ... D = std > 15m + abrupt on/off

### Pillar 2: Inter-Corner Causal Chain Detection
**Source document**: `coaching_improvement_iteration3_causal_chains.md` (1,107 lines)

**The problem**: We grade corners independently. Track Titan's TimeKiller traces cascading errors across corners. This is our #1 competitive gap.

**The solution** (no new dependencies — numpy + scipy only):

**Stage 1 — Corner Link Detection**:
- Physics-based: `recovery_fraction` algorithm using v² = v₀² + 2ad
- Data-driven: Pearson correlation between T[n] exit speed and T[n+1] min speed
- Classification: tight (<0.3 recovery), moderate (0.3-0.7), weak (0.7-0.9), independent (>0.9)

**Stage 2 — Per-Lap Cascade Quantification**:
- For each linked pair: propagate speed deficit through gap using physics
- Decompose: `T4_total_loss = T4_self_caused + T4_inherited_from_T3`
- If inheritance > 60%, label corner as "(cascading from TX)"

**Stage 3 — Session-Level Causal Chain Aggregation**:
- Trace connected linked pairs into chains: T3 → T4 → T5
- Identify the "TimeKiller" (chain with highest total cascade impact)
- Generate natural-language coaching summary per chain
- Root cause classification: late brake, early apex, over-slowing

**New data structures**: `CornerLink`, `CascadeEffect`, `CausalChain`, `SessionCausalAnalysis` (complete Python sketches provided)

**Prompt integration**:
```
## Causal Chain Analysis (TimeKiller Detection)
### Chain 1 (TimeKiller): T3 -> T4 -> T5
- Root cause: T3 (braking too late)
- Total cascade: 0.26s (0.15s at T3 + 0.11s downstream) across 75% of laps
- Fix: Brake 8m earlier at T3 → T4 and T5 improve automatically
```

### Pillar 3: Adaptive Skill-Level Coaching
**Source document**: `coaching_improvement_iteration3_adaptive_skill.md` (1,094 lines)

**Driver archetype detection** (7 types with telemetry signatures):

| Archetype | Telemetry Signature | Coaching Focus |
|-----------|-------------------|----------------|
| Early Braker | Brake point 15+ m early, high brake G | Confidence building, later braking |
| Late Braker/Hero | Late brake, low min speed, early apex | Patience, trail braking |
| Coaster | Long coast phase before throttle | Commitment, corner flow |
| Smooth Operator | Low variance, moderate speed | Pushing limits, precision gains |
| Aggressive Rotator | High yaw rate, abrupt inputs | Smoothness, car control |
| Conservative Liner | Tight line, low speed utilization | Track width usage, apex positioning |
| Trail Brazer | Strong trail braking, good rotation | Fine-tuning, consistency |

Auto-detection algorithm: 6-dimension scoring (brake timing, brake force, coast duration, speed utilization, input smoothness, consistency) — uses metrics we already compute.

**Scaffolding theory applied** (Vygotsky's ZPD):
- Zone of Proximal Development = just-beyond-current-skill challenges
- Cognitive load limits per level: Novice 1-2 instructions/corner, Intermediate 2-3, Advanced 3-4
- Skip Barber / BMW / Porsche curricula mapped to our 3-tier system

**External focus translation table**:

| Internal Focus (BAD) | External Focus (GOOD) | Skill Level Modifier |
|---|---|---|
| "Press the brake harder" | "The car should slow more aggressively before the marker" | All |
| "Turn the wheel earlier" | "Point the car toward the inside curb sooner" | All |
| "Squeeze the throttle" | "Let the car accelerate as you unwind the wheel" | Int/Adv |
| "Relax your hands" | "Let the car talk to you through the wheel" | Advanced |

**Implicit learning for novices** (analogy library):

| Technique | Analogy | Scientific Basis |
|-----------|---------|-----------------|
| Trail braking | "Like squeezing water from a sponge — gradual release, not sudden" | Liao & Masters 2001 |
| Weight transfer | "Imagine the car is a bowl of soup — keep it from spilling" | Embodied cognition |
| Racing line | "Like skiing — set up wide, carve through the apex" | Skill transfer |
| Throttle application | "Like accelerating in the rain — progressive, not sudden" | Risk calibration |

**Progression model** (Dreyfus + Fitts-Posner mapped to telemetry):

| Transition | Telemetry Indicators | Actions |
|-----------|---------------------|---------|
| Novice → Intermediate | Brake variance < 10m, min speed CV < 8%, 5+ track sessions | Unlock inter-corner coaching, add patterns |
| Intermediate → Advanced | Brake variance < 5m, min speed CV < 5%, within 5% of track record, 15+ sessions | Unlock causal chains, archetype insights, setup hints |

### Pillar 4: Longitudinal Intelligence
**Source document**: `coaching_improvement_iteration3_longitudinal.md` (1,810 lines)

**Session memory architecture** (hybrid structured + summarized):
- **Structured data**: PostgreSQL `coaching_memory` table with per-session metrics (priority corners, grades, brake points, focus areas, milestones)
- **Narrative context**: Summarized to ~2,000 tokens for prompt injection using hierarchical pyramid: per-session summary → per-track summary → overall driver summary
- **No vector DB needed initially** — structured retrieval with summarization sufficient at our scale

**Corners Gained algorithm** (adapted from Arccos Golf "Strokes Gained"):
- Target-based decomposition: "To reach 1:40 from 1:42, focus on T5 braking (0.8s), T1 entry (0.4s), consistency (0.6s)"
- Multi-facet sensitivity: each corner decomposed into braking, min speed, throttle, line components
- Personal best baseline first; population baselines when data allows

**Flow lap detection** (4-criteria composite score):
- Proximity to PB (weight 0.45): all corners within X% of best
- Balance (0.25): no single corner dominates the deficit
- Smoothness (0.20): low variance in driving inputs
- Timing (0.10): lap placement in session (mid-session more likely)
- Score 0-1; threshold ≥0.75 = flow lap
- Coaching use: "Laps 8, 12, 14 were your flow laps — what were you feeling?"

**Pre-session briefing generation**:
- When driver returns to a track, generate a focus briefing from session history
- Learning goals for novices (process-focused), performance goals for advanced
- "Today at Barber: your T5 brake point has moved 15m later over 4 sessions. Focus on consistency at the 2-board marker."

**Milestone detection** (15+ types):
- First-ever PB, corner-specific PB, consistency milestone, brake point improvement, sub-X lap time, technique unlock, flow state achievement
- Progress Principle (Amabile & Kramer): 28% of minor progress events had major emotional impact → celebrate small wins

**Token budget with all new sections**: ~12,000 input tokens + ~4,000 output = ~16,000 total — well within Haiku's 200k context window.

---

## Part 3: Unified Implementation Roadmap

### Phase 0: Prompt Quick Wins (2-3 hours) — DO FIRST
*Highest ROI, no architecture changes*

| # | Change | File | Impact |
|---|--------|------|--------|
| 1 | Set `temperature=0.3` | `coaching.py` | Consistency + accuracy (1 line change) |
| 2 | Add uncertainty admission instruction | `driving_physics.py` | Reduces hallucinated causation |
| 3 | Replace markdown headers with XML tags | `coaching.py` | ~30% parsing improvement |
| 4 | Move data to top, instructions to bottom | `coaching.py` | ~30% quality improvement |
| 5 | Replace "be encouraging" with "cite data-backed strengths" | `driving_physics.py` | Prevents warmth/accuracy tradeoff |
| 6 | Add "because" clause requirement | `driving_physics.py` | +41% recommendation acceptance |
| 7 | Add external focus language requirement | `driving_physics.py` | Motor learning improvement |
| 8 | Add kinesthetic sensation vocabulary | `driving_physics.py` | Bridges data→execution gap |
| 9 | Add autonomy-supportive framing for intermediate+ | `driving_physics.py` | OPTIMAL Theory compliance |
| 10 | Reduce priority_corners to 2 for novice | `coaching.py` | Guidance hypothesis alignment |

### Phase 1: Grading & Causal Reasoning (3-4 hours)
*Quality of analysis leap*

| # | Change | File | Impact |
|---|--------|------|--------|
| 11 | Evidence-anchored rubric (per-criterion thresholds) | `driving_physics.py` | Prevents grade inflation |
| 12 | Grade distribution expectations | `driving_physics.py` | Bell curve around B/C |
| 13 | Evidence-before-grading instruction | `driving_physics.py` | RULERS framework compliance |
| 14 | 5-step causal reasoning decomposition | `driving_physics.py` | Root cause > symptom coaching |
| 15 | Create Golden Example A (intermediate @ Barber) | `driving_physics.py` | Calibrates all output qualities |
| 16 | Create Golden Example B (contrastive anti-example) | `driving_physics.py` | Shows what NOT to do |

### Phase 2: Inter-Corner Causal Chains (8-12 hours)
*Our #1 competitive gap — matches Track Titan*

| # | Change | File | Impact |
|---|--------|------|--------|
| 17 | `CornerLink` + `recovery_fraction()` + correlation | New: `causal_chains.py` | Detect linked corners |
| 18 | `CascadeEffect` + per-lap propagation | `causal_chains.py` | Quantify cascading errors |
| 19 | `CausalChain` + session aggregation + TimeKiller | `causal_chains.py` | Root cause identification |
| 20 | Integrate into pipeline + coaching prompt | `corner_analysis.py`, `coaching.py` | LLM receives chain data |
| 21 | Frontend: cascade badges + inheritance bars | Corner cards, deep-dive | Visual cascade display |
| 22 | Add causal chain instruction to system prompt | `driving_physics.py` | LLM uses chain data correctly |

### Phase 3: Adaptive Skill Detection (6-8 hours)
*Personalization without explicit setup*

| # | Change | File | Impact |
|---|--------|------|--------|
| 23 | 7-archetype detection from telemetry | New: `driver_archetypes.py` | Auto-classify driving style |
| 24 | Archetype-specific coaching language | `coaching.py`, `driving_physics.py` | Tailored tips per archetype |
| 25 | Auto skill level detection (6-dimension) | New: `skill_detection.py` | No explicit skill declaration needed |
| 26 | External focus translation (skill-level-aware) | `driving_physics.py` | Proximal→distal by skill |
| 27 | Implicit learning analogies for novices | `driving_physics.py` | Reduce cognitive load |
| 28 | Cognitive load limits per skill level | `coaching.py` | Right amount of detail |

### Phase 4: Longitudinal Intelligence (12-16 hours)
*Session-over-session intelligence*

| # | Change | File | Impact |
|---|--------|------|--------|
| 29 | `coaching_memory` + `driver_profiles` DB tables | `models.py` | Structured memory storage |
| 30 | Memory extraction after report generation | New: `coaching_memory.py` | Auto-persist session insights |
| 31 | Hierarchical summarization for prompt injection | `coaching_memory.py` | ~2,000 token history context |
| 32 | Corners Gained algorithm | New: `corners_gained.py` | Target-based improvement path |
| 33 | Flow lap detection | `corner_analysis.py` or new | Identify peak performance laps |
| 34 | Pre-session briefing generation | New: `briefing.py`, API endpoint | Focus guidance before driving |
| 35 | Milestone detection + celebration | New: `milestones.py`, frontend | Progress Principle engagement |
| 36 | Session comparison with condition normalization | New: `session_comparison.py` | Fair cross-session comparison |

### Phase 5: Structured Outputs Migration (2-3 hours)
*Technical debt reduction*

| # | Change | File | Impact |
|---|--------|------|--------|
| 37 | Define Pydantic schema for coaching report JSON | `coaching.py` | Type-safe output |
| 38 | Migrate to structured outputs API parameter | `coaching.py` | 100% JSON conformance |
| 39 | Relax temperature to 0.4-0.5 | `coaching.py` | Better prose with guaranteed JSON |

### Phase 6: Validation & Tuning (ongoing)

| # | Change | Impact |
|---|--------|--------|
| 40 | A/B test old vs new prompt on 20 sessions | Measure quality delta |
| 41 | Validate grade distribution (should be bell curve B/C) | Prevent inflation |
| 42 | Review causal reasoning quality in outputs | Verify WHY not WHAT |
| 43 | Tune archetype detection thresholds on real data | Accuracy validation |
| 44 | Calibrate flow detection threshold | User feedback loop |
| 45 | Iterate golden examples based on output quality | Continuous improvement |

---

## Part 4: The "Holy Shit" Feature Stack (Updated)

### For Novices (HPDE 1-2 drivers):
1. **Plain English coaching** with analogies — "like squeezing water from a sponge"
2. **1-2 priorities only** — don't overwhelm, celebrate what they're doing right
3. **Visual landmarks** — "brake at the 3-board" not "brake point at 142.5m"
4. **Growth trajectory** — "You improved 0.8s. At this rate, you'll break 1:45 in 2 sessions"
5. **External focus only** — "the car should..." never "you should press..."
6. **Pre-session briefing** — "Today: focus only on T5 braking consistency"
7. **Milestone celebrations** — confetti for first PB, consistency achievement
8. **Flow lap identification** — "Laps 8 and 12 were your best — what did that feel like?"

### For Advanced (experienced racers):
1. **Root cause chains** — "Your T4 problem starts at T3. Fix the brake point and T4 improves automatically."
2. **TimeKiller detection** — "Your biggest cascade: T3→T4→T5, costing 0.26s total"
3. **Archetype insights** — "Your data shows a 'Coaster' pattern. Here's how to convert coast to commitment."
4. **Corners Gained decomposition** — "To break 1:38: T5 braking (0.3s), T1 entry (0.2s), T8 consistency (0.15s)"
5. **Session memory** — "Your T5 brake point moved 15m later over 4 sessions. Consistency improved 0.8s."
6. **Evidence-anchored grades** — "T5 Braking: B (std 4.2m, peak G within 0.08G). Trail Braking: C (present 65% of laps)"
7. **Setup hints** — "T2 and T6 both show understeer signatures — consider adding front grip"
8. **Experiment-framed tips** — "Try braking 5m deeper at T5 for 3 laps and compare your data"

### For Everyone:
1. **< 30-second analysis** — upload CSV → full coaching report instantly
2. **Follow-up chat** — "Why should I brake later?" → physics-backed explanation
3. **Shareable session cards** — one tap to Instagram
4. **Audio summary** — listen during drive home
5. **No hardware** — $30 RaceChrono vs $1,199 Garmin
6. **"Because" clauses on every tip** — trust through data transparency

---

## Part 5: Competitive Gap Analysis (Final)

### vs Track Titan ($5M funded, sim-only)
| Capability | Track Titan | Cataclysm (Current) | Cataclysm (Post-Research) |
|-----------|------------|---------------------|--------------------------|
| Inter-corner causation | TimeKiller (physics sim) | None | Causal chains (Phase 2) |
| Root cause coaching | Coaching Flows | Independent corners | 5-step causal decomposition |
| Skill adaptation | Basic novice/pro | 3 tiers (novice/int/adv) | 7 archetypes + auto-detect |
| Session memory | Limited | None | Full longitudinal intelligence |
| Real-world telemetry | No (sim only) | Yes | Yes |
| Hardware required | PC + sim rig | Phone + RaceChrono ($30) | Phone + RaceChrono ($30) |
| Coaching methodology | Physics simulation | LLM + pre-computed analysis | LLM + physics + motor learning science |

### vs Garmin Catalyst 2 ($1,199)
| Capability | Catalyst 2 | Cataclysm (Post-Research) |
|-----------|-----------|--------------------------|
| Coaching depth | "Brake earlier" | Root cause chains, evidence-anchored |
| Personalization | Minimal | Archetype + skill-adaptive |
| Price | $1,199 + subscription | Free / cheap |
| Session memory | Basic trend lines | Full longitudinal intelligence |
| AI coaching | Rule-based | LLM-powered with physics guardrails |

### vs Human Coach ($150-300/hour)
| Capability | Human Coach | Cataclysm (Post-Research) |
|-----------|-----------|--------------------------|
| Availability | Track day only | Anytime, anywhere |
| Consistency | Variable quality | Consistent, evidence-anchored |
| Data depth | Watches 1-2 corners | Analyzes every corner, every lap |
| Session memory | Notes, varies | Perfect recall |
| Cost per session | $150-300 | ~$0.04 (Haiku API cost) |
| Emotional intelligence | Strong | Moderate (OIS + growth framing) |
| Novel insight | Sometimes genius | Data-driven, never subjective |

---

## Part 6: Research Completeness Assessment

### What We've Covered (Comprehensive)
- **LLM prompt engineering**: Temperature, XML tags, golden examples, structured outputs, CoT alternatives, data ordering, calibration, few-shot optimization
- **Motor learning science**: OPTIMAL Theory, external focus (meta-analysis, hundreds of studies), guidance hypothesis, scaffolding, chunking, deliberate practice, flow state
- **Professional coaching methods**: Ross Bentley (Speed Secrets), Skip Barber, BMW, Porsche curricula, F1 race engineer debriefs, SBI/OIS feedback models, Driver 61, Blayze
- **Competitive landscape**: Track Titan (deep dive), Garmin Catalyst 2, Griiip, Full Grip, Bosch TPA, AiM Solo, MoTec
- **Performance psychology**: Growth mindset, self-determination theory, autonomy support, Progress Principle, flow state, confidence cascades
- **Causal analysis**: Granger causality, Bayesian networks, fault tree analysis, DoWhy evaluation, cross-correlation, physics-based propagation — all evaluated for fit
- **Driver archetypes**: ML classification (97%+ accuracy reported), telemetry signatures, archetype-specific coaching language
- **Coaching psychology**: Warmth/reliability tradeoff, sycophancy risk, "because" clause effectiveness, Socratic questioning, reflective practice
- **Longitudinal intelligence**: LLM memory architectures, Arccos Strokes Gained adaptation, session comparison normalization, milestone psychology

### What's NOT Worth Further Research (Diminishing Returns)
- **More motor learning papers**: We have the key frameworks (OPTIMAL, Guidance Hypothesis, Fitts-Posner, Dreyfus). Additional papers would add nuance but not change implementation.
- **More competitive analysis**: Track Titan is the only serious threat, and we've studied them deeply. The others are in different segments.
- **Advanced causal ML**: DoWhy, causal-learn, Bayesian networks — we've evaluated and correctly rejected them for our data scale. Simple physics + correlation is the right approach.
- **Coaching certification curricula**: We've studied Skip Barber, BMW, Porsche, Allen Berg, and professional race engineering methods. The patterns are consistent across all of them.

### What COULD Be Researched Further (But Implementation is Higher Priority)
- **Tire degradation modeling**: How tire wear within a session affects coaching (addressed briefly but not deeply)
- **Weather normalization**: Fair comparison between wet and dry sessions (addressed in session comparison but deserves more)
- **Multi-car coaching**: How advice differs for Miata vs GT3 vs Formula (partially addressed via equipment-aware coaching)
- **Instructor/coaching marketplace integration**: How to combine AI + human coaching (identified as Tier 3 feature)
- **Audio coaching UX research**: Best practices for audio coaching summaries (mentioned but not deeply researched)

### Verdict: The Research Phase is Complete

The three iterations have produced more than enough actionable intelligence to implement a coaching system that would genuinely impress both novices and professionals. **Further research has diminishing returns. The priority is now implementation.**

The research corpus includes:
- 200+ unique sources (academic papers, industry reports, competitor analysis, product reviews, coaching books)
- Complete algorithm designs with Python pseudocode for every major feature
- Specific prompt text ready to paste into `driving_physics.py` and `coaching.py`
- Data structures and integration points for all architectural additions
- Estimated effort for every phase (total: ~35-45 hours across all phases)

---

## Part 7: Master Source Index (Iteration 3 — New Sources)

### Prompt Engineering
- [Anthropic: Use XML Tags](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/use-xml-tags)
- [Anthropic: Long Context Tips](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/long-context-tips)
- [Anthropic: Structured Outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)
- [PromptHub: Few-Shot Guide](https://www.prompthub.us/blog/the-few-shot-prompting-guide)
- [The Few-Shot Dilemma (2025)](https://arxiv.org/html/2509.13196v1)
- [Finding Golden Examples (Towards Data Science)](https://towardsdatascience.com/finding-golden-examples-a-smarter-approach-to-in-context-learning/)
- [LLMs are Contrastive Reasoners (2024)](https://arxiv.org/html/2403.08211v2)
- [RULERS: Locked Rubrics (2026)](https://arxiv.org/abs/2601.08654)
- [AutoRubric (2026)](https://arxiv.org/html/2603.00077)
- [Rubric Is All You Need (2025)](https://arxiv.org/html/2503.23989v1)
- [Evaluating Scoring Bias in LLM-as-Judge (2025)](https://arxiv.org/html/2506.22316v1)
- [Too Nice to Be True: Warmth Degrades Reliability (Oxford 2025)](https://arxiv.org/abs/2507.21919)
- [Mind Your Tone (2025)](https://arxiv.org/abs/2510.04950)
- [Wharton: Decreasing Value of Chain of Thought (2025)](https://gail.wharton.upenn.edu/research-and-insights/tech-report-chain-of-thought/)
- [The Order Effect in LLMs (2025)](https://arxiv.org/html/2502.04134v2)
- [Temperature Guide (Tetrate)](https://tetrate.io/learn/ai/llm-temperature-guide)
- [Causal Reasoning Addresses LLM Limitations (InfoQ)](https://www.infoq.com/articles/causal-reasoning-observability/)

### Causal Chain Detection
- [Driver61: Prioritising Corners](https://driver61.com/uni/prioritising-corners/)
- [Blayze: Complex Corners](https://blayze.io/blog/car-racing/complex-corners)
- [Allen Berg: Three Corner Types](https://www.allenbergracingschools.com/expert-advice/race-tracks-three-corners-types/)
- [Track Titan: Coaching Flows (Nov 2025)](https://www.tracktitan.io/post/november-2025-update-coaching-flows)
- [Track Titan AI Deep Dive (Skywork)](https://skywork.ai/skypage/en/Track-Titan-An-AI-Powered-Deep-Dive-for-Sim-Racers-and-Tech-Enthusiasts/1976160936392716288)
- [Full Grip Telemetry Analysis](https://www.fullgripmotorsport.com/telemetry)
- [DoWhy: Root Cause Analysis (AWS Blog)](https://aws.amazon.com/blogs/opensource/root-cause-analysis-with-dowhy-an-open-source-python-library-for-causal-machine-learning/)
- [PyRCA: Salesforce AIOps](https://www.salesforce.com/blog/pyrca/)
- [Visual Analytics for Causal Analysis](https://arxiv.org/pdf/2009.02458)

### Adaptive Skill-Level Coaching
- [Vygotsky's ZPD + Motor Learning](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5056258/)
- [External Focus Meta-Analysis (Nature 2025)](https://www.nature.com/articles/s41598-025-19862-2)
- [Implicit vs Explicit Motor Learning (Liao & Masters)](https://pubmed.ncbi.nlm.nih.gov/11411779/)
- [Dreyfus Model of Skill Acquisition](https://en.wikipedia.org/wiki/Dreyfus_model_of_skill_acquisition)
- [Fitts & Posner Three-Stage Model](https://www.sciencedirect.com/topics/psychology/fitts-law)
- [Progress Principle (Amabile & Kramer)](https://hbr.org/2011/05/the-power-of-small-wins)
- [Self-Determination Theory in Sport](https://www.frontiersin.org/articles/10.3389/fpsyg.2020.00849/full)

### Longitudinal Intelligence
- [Arccos Golf: Strokes Gained Analytics](https://www.arccosgolf.com/pages/strokes-gained-analytics)
- [LLM Memory Architectures (LangChain)](https://blog.langchain.com/)
- [Context Engineering (2025-2026)](https://www.anthropic.com/engineering)
- [Flow State (Csikszentmihalyi)](https://www.amazon.com/Flow-Psychology-Experience-Perennial-Classics/dp/0061339202)
- [Locke & Latham Goal Setting Theory](https://www.sciencedirect.com/science/article/abs/pii/S0090261602000129)

### Iteration 3 Supporting Documents
- `tasks/coaching_prompt_engineering_iteration3.md` (565 lines — golden examples, XML, temperature, grading)
- `tasks/coaching_improvement_iteration3_causal_chains.md` (1,107 lines — inter-corner detection, algorithms)
- `tasks/coaching_improvement_iteration3_adaptive_skill.md` (1,094 lines — archetypes, scaffolding, focus)
- `tasks/coaching_improvement_iteration3_longitudinal.md` (1,810 lines — memory, Corners Gained, flow, briefings)

### Previous Iterations
- `tasks/coaching_improvement_research.md` (Iteration 1 — system assessment, 12 gaps, 20-item roadmap)
- `tasks/coaching_improvement_iteration2_synthesis.md` (Iteration 2 — 10 discoveries, 30-item roadmap)
- `tasks/coaching_science_deep_research.md` (motor learning, deliberate practice, psychology)
- `tasks/competitive-deep-dive-iteration2.md` (Track Titan, AI coaching, market analysis)
- `tasks/coaching-knowledge-literature-review.md` (60+ sources catalogued)
