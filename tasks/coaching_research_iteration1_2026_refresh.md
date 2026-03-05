# Coaching Research — Iteration 1: 2026 Landscape Refresh + Gap Analysis

**Date**: 2026-03-04 (Iteration 1 of 3 — Ralph Loop)
**Focus**: Fresh competitive intelligence, implementation gap audit, underexplored areas
**Sources**: 20+ web searches, 3 page deep-fetches

---

## Part 1: Implementation Gap Audit

### What's Implemented (vs. Research Roadmap)

| Phase | Status | Key Modules |
|-------|--------|-------------|
| 0: Prompt Quick Wins | **DONE** | `driving_physics.py` — temperature=0.3, XML tags, OIS format, golden/anti examples, because clauses, external focus, uncertainty admission, autonomy framing |
| 1: Grading & Causal Reasoning | **DONE** | Evidence-anchored rubric, grade distribution guidance, 5-step causal reasoning, evidence-before-grading |
| 2: GPS Line Analysis | **DONE** | `gps_line.py`, `corner_line.py` — apex detection, line error classification, consistency tiers |
| 3: Causal Chains | **DONE** | `causal_chains.py` — inter-corner cascade detection, TimeKiller identification |
| 4: Adaptive Skill | **DONE** | `driver_archetypes.py` (7 archetypes), `skill_detection.py` (auto-detect) |
| 5: Frontend Line Viz | **NOT DONE** | Speed-colored track map, GPS overlay, lateral offset chart |
| 6: Longitudinal | **DONE** | `milestones.py`, `briefing.py`, `coaching_memory.py`, `corners_gained.py`, `flow_lap.py` |
| 7: GPS+IMU Fusion | **NOT STARTED** | Future enhancement |

### What's Still Missing (Not in Roadmap)

| Gap | Priority | Effort | Impact |
|-----|----------|--------|--------|
| **Structured Outputs API** | HIGH | 2-3 hours | Eliminates JSON parsing failures |
| **Coaching quality evaluation (LLM-as-judge)** | HIGH | 4-6 hours | Automated quality monitoring |
| **Few-shot example library** (dynamic retrieval) | MEDIUM | 4-6 hours | Better coaching calibration |
| **A/B testing framework** | MEDIUM | 3-4 hours | Systematic prompt improvement |
| **Audio coaching summaries** | MEDIUM | 6-8 hours | New engagement channel |
| **Drill effectiveness tracking** | MEDIUM | 4-6 hours | Closed-loop coaching |
| **Tire degradation modeling** | LOW | 3-4 hours | Fair mid-session normalization |
| **Weather normalization** | LOW | 3-4 hours | Fair cross-session comparison |
| **Multi-car coaching** (drivetrain-aware) | LOW | 2-3 hours | FWD/RWD/AWD technique differences |
| **Video integration** | LOW | 10+ hours | Dashcam annotation overlay |
| **Real-time in-car coaching** | LOW | 20+ hours | Live audio coaching during sessions |

---

## Part 2: Competitive Intelligence — March 2026

### NEW Competitors Since Last Research

#### 1. Perfect Apex (NEW — October 2025)
- **What**: Open platform for motorsport lap data analysis with AI insights
- **Data sources**: RaceChrono, TrackAddict, Racebox, LapLegend, Harry's LapTimer, Apex Pro, Circuit Storm
- **Features**: AI-powered corner-by-corner analysis, lap comparison, sharing/commenting, delta charts
- **Threat level**: MEDIUM — direct competitor to Cataclysm. Same model (upload data → AI analysis)
- **Weakness**: Still "work in progress", AI Insights described as "experimenting"
- **Source**: [Perfect Apex](https://www.perfect-apex.com/), [RaceChrono forum](http://racechrono.com/forum/discussion/2667/)

#### 2. Griiip + IturanMob + Skip Barber (NEW — Feb 2026)
- **What**: Real-time telemetry + AI coaching for real-world track day and racing
- **Hardware**: IturanMob IoT devices in cars → GriiipPerformance cloud platform
- **Partners**: Skip Barber Racing School (North America's premier), backed by Porsche Ventures
- **Features**: Real-time AI coaching, mobile dashboards, performance benchmarking, digital driver profiles
- **Target**: Thousands of connected vehicles by end of 2026
- **Threat level**: HIGH — real-world data, professional backing, hardware+software play
- **Weakness**: Requires hardware installation, likely subscription model, not phone-based
- **Source**: [PR Newswire](https://www.prnewswire.com/news-releases/ituranmob-and-griiip-to-offer-real-time-telemetry-and-ai-powered-insights-to-race-and-track-day-drivers-302689346.html)

#### 3. Formula E × Google Cloud Driver Agent (NEW — 2025-2026)
- **What**: AI coaching powered by Gemini for Formula E drivers
- **Features**: Real-time text + audio coaching from telemetry, energy strategy optimization
- **Tech**: Google Vertex AI + Gemini multimodal models
- **Plans**: "Virtual Race Engineer" fan app for real-time AI interaction
- **Threat level**: LOW (F1/FE niche) but validates the concept
- **Source**: [Google Cloud Blog](https://cloud.google.com/blog/products/ai-machine-learning/formula-e-ai-equation-a-new-driver-agent-for-the-next-generation-of-racers)

### Updated Existing Competitors

#### Track Titan (updated)
- Raised $5M seed (Dec 2025) co-led by Partech and Game Changers Ventures
- 200,000+ users, avg 0.5s improvement after first session
- Plans: Expand to real-world via hardware partnerships (steering wheels, pedals, dashboards)
- Coaching Flows feature (Nov 2025): guides through single biggest time-loss cause
- **Threat level**: MEDIUM — still sim-only, but $5M funding means they're coming for real-world
- **Source**: [Tech.eu](https://tech.eu/2025/12/04/track-titan-raises-5m-for-ai-powered-strava-for-motorsport/)

#### Coach Dave Delta 5.4 (updated)
- Major AI rework: "Auto Insights are now smarter, faster, and much more deliberate"
- Key change: **Now focuses on 1-2 meaningful improvements** instead of flooding with observations
- Achievable reference laps (not alien pro laps) — excellent UX decision
- Four-phase breakdown: Braking, Entry, Apex, Exit
- **Source**: [Coach Dave Academy](https://coachdaveacademy.com/announcements/introducing-delta-5-4-with-a-new-ui-and-smarter-ai/)

#### trophi.ai (updated)
- 1.5M+ coaching sessions delivered
- Real-time AI voice coach "Mansell" — guides through headset during laps
- Structured learning paths with specific skill development exercises
- Expert lap comparison with telemetry overlay
- **Source**: [trophi.ai](https://www.trophi.ai/sim-racing-coaching)

#### Garmin Catalyst 2
- 1440p camera (not 4K) on $1,200 device — user complaints
- $9.99/month Vault subscription required — backlash ("pay to access your own videos")
- No meaningful software feature updates mentioned
- **Source**: [Rising X Edge](https://www.risingxedge.com/quick-hits-garmin-catalyst-2-more-track-woes/), [GRM Forum](https://grassrootsmotorsports.com/forum/grm/new-garmin-catalyst-2-streamli/284888/page1/)

#### RaceChrono
- v10.0.2 (March 2026) — stability fixes, new GPS hardware support
- **No native AI coaching features** — still pure data collection
- Perfect Apex is the closest third-party AI coaching integration
- **Source**: [RaceChrono changelog](https://racechrono.com/article/2025)

### Competitive Moat Assessment (Updated)

| Feature | Cataclysm | Perfect Apex | Griiip | Track Titan | trophi.ai | Coach Dave |
|---------|-----------|-------------|--------|-------------|-----------|-----------|
| Real-world telemetry | ✅ | ✅ | ✅ | ❌ (sim) | ❌ (sim) | ❌ (sim) |
| AI coaching depth | ✅✅✅ | ✅ | ✅✅ | ✅✅ | ✅✅ | ✅✅ |
| No hardware required | ✅ | ✅ | ❌ | N/A | N/A | N/A |
| Phone-based | ✅ | ✅ | ❌ | N/A | N/A | N/A |
| RaceChrono import | ✅ | ✅ | ❌ | N/A | N/A | N/A |
| Causal chain detection | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ |
| Skill-adaptive coaching | ✅ | ❌ | ❌ | ✅ | ✅ | ❌ |
| Session memory | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ |
| Free/low-cost | ✅ | ✅ (freemium) | ❌ | Subscription | Subscription | Subscription |
| Audio coaching | ❌ | ❌ | ✅ | ❌ | ✅ | ❌ |

**Key takeaway**: Perfect Apex is our closest direct competitor (same model, same data sources). Griiip+Skip Barber is the biggest long-term threat (institutional backing + hardware). Our advantages: depth of analysis (causal chains, archetypes, milestones), no hardware requirement, and cost.

---

## Part 3: Underexplored Area — Audio Coaching

### State of the Art

**Best-in-class implementations:**
1. **trophi.ai "Mansell"** — Real-time voice coaching through headset during sim sessions. Corner-by-corner guidance on next lap based on previous lap analysis.
2. **Garmin Catalyst** — Audio coaching prompts during real driving. Limited to "brake earlier/later" style commands.
3. **Formula E Driver Agent** — Gemini-powered text-to-audio coaching insights.
4. **Running apps (Nike Run Club, Peloton, COROS)** — Audio cues during activity. Best UX pattern: short, targeted prompts at key moments.

**TTS Technology (2026 state):**
- **ElevenLabs** — Industry leader. 5,000+ voices, 70+ languages. $11B valuation. Context awareness 63%, naturalness leader.
- **OpenAI gpt-4o-mini-tts** — Better integration with AI ecosystem. Steerable pitch/speed/emotion.
- **Chatterbox TTS (open source)** — MIT license. Emotion intensity control (0.0-2.0 parameter). Voice cloning from 5s of audio. Beats ElevenLabs in blind tests.

**Audio coaching UX patterns for Cataclysm:**
1. **Post-session summary** (5-10 min) — Drive home listening. "Your session at Barber: 3 key takeaways..."
2. **Pre-session briefing** (2-3 min) — Before going out. "Today at Barber: focus on T5 brake consistency..."
3. **Corner-by-corner breakdown** (optional deep dive) — Each priority corner with data
4. **Drill reminders** — Short clips before sessions. "Remember: brake at the 2-board at T5 for 3 laps"

**Implementation approach:**
- Use ElevenLabs or Chatterbox TTS to convert coaching report text to audio
- Structure report specifically for audio: shorter sentences, more pauses, no data tables
- Audio-specific formatting: "Your best lap was one twenty-eight point three" not "1:28.3"
- Offer download as MP3 for offline listening (drive home from track)

---

## Part 4: Underexplored Area — Coaching Quality Evaluation

### LLM-as-Judge Framework for Coaching

**Recommended approach** (from Confident AI + RULERS framework):

**Evaluation criteria for coaching output:**

| Criterion | Weight | Score 1 | Score 5 |
|-----------|--------|---------|---------|
| **Data Grounding** | 25% | Generic advice with no data citations | Every claim references specific telemetry numbers |
| **Actionability** | 20% | Vague ("brake better") | Specific experiment with reference point and measurement |
| **Root Cause Depth** | 15% | Symptom-level ("exit speed is low") | Full causal chain (entry → mid → exit) |
| **Skill Calibration** | 15% | Language mismatch with driver level | Perfectly adapted communication style |
| **Grade Accuracy** | 15% | Grade inflation (all A/B) or arbitrary grades | Evidence-anchored grades matching rubric thresholds |
| **Positive Framing** | 10% | All criticism, no strengths | Strengths-first, opportunities framing |

**Implementation:**
1. Generate coaching report with current prompt
2. Pass report + original telemetry to judge model (Claude Sonnet 4.6 as judge)
3. Judge scores each criterion on 1-5 scale with chain-of-thought reasoning
4. Log scores to database for tracking over time
5. Alert when average score drops below threshold

**Best practices from research:**
- Use **pairwise comparison** for A/B testing prompts (more reliable than absolute scoring)
- Provide **few-shot examples** to judge (increases consistency from 65% → 77.5%)
- Apply **position swapping** in pairwise to mitigate bias
- Use **categorical integer scale** (1-5) not continuous scale
- Judge should reason before scoring (chain-of-thought)

---

## Part 5: Underexplored Area — Tire Degradation

### Key Findings

**Heat cycle degradation within a session:**
- A heat cycle = one session (20-30 min) for HPDE drivers
- Grippier tires (Hoosier R7) drop off quickly around 10 heat cycles
- More durable tires (Toyo RR, Nitto NT01) take 10-30 heat cycles to lose competitiveness
- Within a single session: tread temperature drops as rubber wears → rubber stiffens → less grip → more sliding → accelerates wear (vicious cycle)

**Coaching implications:**
- Lap time naturally increases later in a session ≠ technique degradation
- Coach should NOT tell driver "you're getting worse" when tires are fading
- Should detect and flag: "Lap times increased 0.8s in final 5 laps — consistent with tire degradation, not technique loss"
- Temperature effects: optimal tire temp 190-210°F (88-99°C); missing window by a few degrees costs tenths

**Implementation approach:**
- Detect tire degradation pattern: monotonic lap time increase in final 1/3 of session
- Differentiate from fatigue (which shows specific corner consistency degradation) vs tire wear (which shows uniform speed loss)
- Add flag to coaching prompt: "Note: final 5 laps show tire-degradation signature — do not attribute time loss to technique"

---

## Part 6: Underexplored Area — Weather Normalization

### Key Findings

- **Temperature**: Even 3-4°C change has noticeable lap time effect
- **Track temp vs air temp**: Track temp more important (25-40°C above ambient in sun)
- **Grip coefficient**: ~0.5-1.0% lap time change per 5°C temperature shift (varies by tire)
- **Cold air = more engine power** but less tire grip — net effect depends on car
- **Wet vs dry**: 10-30% lap time difference depending on severity
- **Wind**: Can affect lap time by 0.3-1.0s depending on straight length and wind direction

**Implementation approach:**
- Track weather via API at session time (already have `SessionConditions` dataclass)
- Normalize cross-session comparisons: "Adjusted for 8°C temperature difference, your improvement is ~0.6s (raw: 0.3s)"
- Flag unfair comparisons: "Session A was 28°C, Session B was 15°C — direct comparison unreliable"

---

## Part 7: Underexplored Area — Multi-Car Coaching

### Key Findings from Driving Instructors

**FWD coaching focus:**
- Understeer is primary challenge — trail braking is ESSENTIAL to rotate car
- "Trail braking, most times, is a must" — needed to load front and lighten rear
- Two rotation strategies: late apex + trail braking OR early apex + sacrifice mid-corner speed
- Left-foot braking useful for rotation

**RWD coaching focus:**
- Throttle control is king — oversteer on exit is primary risk
- "You are always mindful of what your right foot is doing, especially exiting corners"
- Higher learning curve, more courage required
- Wheelspin in RWD = potential spin (propulsion behind CG)

**AWD coaching focus:**
- Similar to FWD in many ways but with more traction
- AWD helps acceleration but does NOT help braking or cornering grip
- "AWD gives better traction for acceleration but does nothing for braking or cornering"

**Universal truth:**
- "At the novice level, fundamentals don't change from car to car" — basics first
- "Tire condition matters more than drivetrain type" — tires are always the limiting factor

**Implementation approach:**
- Detect drivetrain from equipment profile (already have `EquipmentProfile`)
- Add drivetrain-specific coaching notes to system prompt:
  - FWD: emphasize trail braking for rotation, warn about understeer patterns
  - RWD: emphasize throttle discipline, warn about exit oversteer
  - AWD: note that AWD helps acceleration only, don't over-rely on grip
- For novices: suppress drivetrain-specific coaching (focus on fundamentals)

---

## Part 8: Structured Outputs API

### Current State

- Anthropic launched Structured Outputs (Nov 2025) for Claude Sonnet 4.5 and Opus 4.1
- **Haiku 4.5 support coming but not yet available** — this is our blocker
- Uses constrained decoding at inference time — model literally cannot produce invalid JSON
- Zero JSON parsing errors guaranteed
- API usage: `output_format` parameter with JSON schema
- Compatible with Pydantic schemas in Python

**Current Cataclysm approach:**
- JSON parsing with fallback (regex extraction of `{...}`)
- Occasional parsing failures requiring retry
- Works with Haiku 4.5 via `temperature=0.3`

**Action:** Monitor Haiku 4.5 structured outputs availability. When available:
1. Define Pydantic schema for `CoachingReport`
2. Pass schema via `output_format` parameter
3. Remove JSON parsing fallback code
4. Can potentially increase temperature to 0.4-0.5 for more natural prose

---

## Part 9: Drill Effectiveness & Deliberate Practice

### Key Research Findings

**Deliberate practice principles for motorsport:**
- Must be "designed to improve key aspects of current performance, challenging, effortful, requires repetition and feedback"
- **Spaced repetition** combats forgetting curve — distribute practice over sessions, not cluster
- **Variability in practice** creates "more robust neural pathways" — feels harder but produces stronger skills
- Quantifiable outcomes per practice session for tracking

**Drill effectiveness tracking approach:**
1. Assign drill in coaching report (already done: `drills` field in `CoachingReport`)
2. Next session: detect if assigned metric improved
   - e.g., "Brake at 2-board at T5" → did T5 brake point std decrease?
   - "Trail brake drill for T3" → did T3 trail braking % increase?
3. Track across sessions: which drills produce measurable improvement?
4. Feed back into coaching: "Your brake consistency drill at T5 is working — std dropped from 11m to 6m over 2 sessions"

**Gamification opportunities:**
- Drill streak tracking ("3 sessions in a row working on T5 braking")
- Achievement for drill completion ("Brake Master: Hit the same brake point ±3m for 5 consecutive laps")
- Spaced reminders: "It's been 3 sessions since you worked on trail braking at T3 — try it again today"

---

## Part 10: Key Takeaways for Iteration 2

### Areas Needing Deeper Research

1. **Perfect Apex deep dive** — Their AI Insights feature is directly competitive. Need to understand depth, quality, pricing model
2. **LLM-as-judge implementation specifics** — Need concrete rubric examples and evaluation pipeline design
3. **Audio coaching pipeline** — TTS integration architecture, audio formatting rules, MP3 generation
4. **Griiip technical architecture** — What exactly does their AI coaching look like? How deep is the analysis?
5. **Structured outputs timeline** — When will Haiku 4.5 be supported?
6. **Coaching quality benchmarking** — How to measure if our coaching is actually better than competitors?

### Immediate High-Impact Actions (No More Research Needed)

1. **Migrate to Structured Outputs** when Haiku 4.5 support lands
2. **Build LLM-as-judge evaluation pipeline** — 5 criteria, pairwise comparison, logged scores
3. **Add drivetrain-aware coaching** — Simple prompt additions based on equipment profile
4. **Add tire degradation detection** — Statistical pattern detection in late-session laps
5. **Build audio coaching pipeline** — TTS integration for post-session summaries

---

## Sources

- [Track Titan $5M Raise](https://tech.eu/2025/12/04/track-titan-raises-5m-for-ai-powered-strava-for-motorsport/)
- [Track Titan Coaching Flows](https://www.tracktitan.io/post/november-2025-update-coaching-flows)
- [Griiip + IturanMob](https://www.prnewswire.com/news-releases/ituranmob-and-griiip-to-offer-real-time-telemetry-and-ai-powered-insights-to-race-and-track-day-drivers-302689346.html)
- [Skip Barber × Griiip](https://www.skipbarber.com/2025/07/14/drive-to-thrive-skip-barber-racing-school-and-griiip-launch-game-changing-tech-partnership-to-accelerate-the-future-of-motorsport-training/)
- [Formula E Driver Agent](https://cloud.google.com/blog/products/ai-machine-learning/formula-e-ai-equation-a-new-driver-agent-for-the-next-generation-of-racers)
- [Perfect Apex](https://www.perfect-apex.com/)
- [RaceChrono Forum on Perfect Apex](http://racechrono.com/forum/discussion/2667/)
- [trophi.ai](https://www.trophi.ai/sim-racing-coaching)
- [Coach Dave Delta 5.4](https://coachdaveacademy.com/announcements/introducing-delta-5-4-with-a-new-ui-and-smarter-ai/)
- [Garmin Catalyst 2 issues](https://www.risingxedge.com/quick-hits-garmin-catalyst-2-more-track-woes/)
- [LLM-as-Judge Guide](https://www.confident-ai.com/blog/why-llm-as-a-judge-is-the-best-llm-evaluation-method)
- [LLM-as-Judge 2026 Guide](https://labelyourdata.com/articles/llm-as-a-judge)
- [GER-Eval Rubric Design](https://arxiv.org/html/2602.08672v1)
- [Anthropic Structured Outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)
- [ElevenLabs v3](https://elevenlabs.io/blog/eleven-v3)
- [Chatterbox TTS](https://reviewnexa.com/chatterbox-tts-review/)
- [Tire Degradation State-Space Model](https://arxiv.org/pdf/2512.00640)
- [FWD vs RWD Techniques](https://windingroad.com/articles/features/speed-secrets-fwd-vs-rwd/)
- [Deliberate Practice Guide](https://gmb.io/motor-learning/)
- [F1 Track Temperature Effects](https://www.catapult.com/blog/how-tyre-degradation-affects-race-strategy/)
