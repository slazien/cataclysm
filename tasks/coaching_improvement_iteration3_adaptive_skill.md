# Iteration 3: Adaptive Skill-Level Coaching, Motor Learning Science, and Driver Archetype Detection

**Date:** 2026-03-03
**Focus:** Deep research on scaffolding theory, driver archetype detection, external focus of attention, implicit/explicit learning, novice-to-expert progression models, and personalization without explicit skill declaration.

---

## Table of Contents

1. [Topic 1: Scaffolding Theory for Motor Skill Development](#topic-1-scaffolding-theory-for-motor-skill-development)
2. [Topic 2: Driver Archetype Detection from Telemetry](#topic-2-driver-archetype-detection-from-telemetry)
3. [Topic 3: External Focus of Attention - Implementation Depth](#topic-3-external-focus-of-attention---implementation-depth)
4. [Topic 4: Implicit vs Explicit Learning in Motorsport](#topic-4-implicit-vs-explicit-learning-in-motorsport)
5. [Topic 5: Novice-to-Expert Progression Models](#topic-5-novice-to-expert-progression-models)
6. [Topic 6: Personalization Without Explicit Skill Declaration](#topic-6-personalization-without-explicit-skill-declaration)
7. [Synthesis: Unified Adaptive Coaching Architecture](#synthesis-unified-adaptive-coaching-architecture)
8. [Implementation Roadmap](#implementation-roadmap)

---

## Topic 1: Scaffolding Theory for Motor Skill Development

### Key Findings

**Vygotsky's Zone of Proximal Development (ZPD) Applied to Motorsport**

The ZPD represents the space between what a learner can do unaided and what they can do with expert guidance. Applied to track driving, this means coaching should target the "stretch zone" -- skills the driver cannot yet execute consistently but can achieve with scaffolded support. Coaching that falls below the ZPD (e.g., telling an advanced driver to "use both hands") is wasted. Coaching above the ZPD (e.g., telling a novice to "modulate trail braking based on weight transfer balance") is incomprehensible and counterproductive.

Wood, Bruner, and Ross (1976) defined scaffolding as controlling task elements beyond the learner's current capability, then gradually withdrawing support as competence grows. In motorsport terms: early coaching constrains the problem space ("just focus on hitting the same brake marker every lap") and progressively expands it ("now vary your brake pressure based on how much rotation you need").

**Sources:**
- [Simply Psychology - ZPD](https://www.simplypsychology.org/zone-of-proximal-development.html)
- [Skillshub - ZPD and Scaffolding](https://www.skillshub.com/blog/vgotskys-zone-proximal-development-scaffolding/)
- [Frontiers - Scaffolding Theory of Maturation, Cognition, Motor Performance (2025)](https://www.frontiersin.org/journals/human-neuroscience/articles/10.3389/fnhum.2025.1631958/full)
- [Tandfonline - Scaffolding Athlete Learning in Preparation for Competition (2021)](https://www.tandfonline.com/doi/full/10.1080/21640629.2021.1991713)

**Scaffolding Frameworks for Complex Motor Skill Acquisition**

A 2025 paper in Frontiers in Human Neuroscience presents a "scaffolding theory" specifically for motor skill acquisition, demonstrating that in early learning stages, broad neural networks activate as scaffolds for new motor skills. With continued practice, this broad activation is replaced by specialized, efficient neural pathways. This has a direct coaching implication: early coaching should activate multiple sensory channels (visual references, kinesthetic cues, auditory feedback) and later coaching should narrow to refined, specific corrections.

The principle of "needs analysis" from skill training periodization research identifies the athlete's current level, determines target goals, and scaffolds appropriately between them. Movement consistency under controlled conditions serves as the trigger to advance to more complex training environments.

**Sources:**
- [Science for Sport - Skill Acquisition](https://www.scienceforsport.com/skill-acquisition/)
- [Human Kinetics - Understanding Motor Learning Stages](https://us.humankinetics.com/blogs/excerpt/understanding-motor-learning-stages-improves-skill-instruction)

**How Professional Driving Schools Structure Their Curricula**

| School | Level Structure | Key Progression Mechanism |
|--------|----------------|--------------------------|
| **Skip Barber Racing School** | 3-Day (beginner) -> 2-Day Advanced -> Advanced Coaching (1:1) | Day 1: autocross + fundamentals. Day 2: stop-box lapping with repetition. Day 3: racecraft + wheel-to-wheel. Advanced: picks up where 3-Day left off. |
| **BMW Performance Driving School** | 1-Day -> 2-Day -> M School (1-Day, 2-Day, Advanced) | Classroom + track exercises. Progressive: wet skid pad -> panic braking -> handling course -> timed laps. Two-way radio feedback during exercises. |
| **Porsche Track Experience** | DISCOVER -> LEARN -> BOOST -> RACE (4 stages) | DISCOVER: brand immersion, initial track moments. LEARN: expanding skills, precision. BOOST: driving dynamics at the limit, racing lines. RACE: comprehensive prep for racing license. |

All three schools share a pattern: **structured progression with instructor sign-off between levels**, classroom instruction before track time, immediate feedback loops, and progressive complexity.

**Sources:**
- [Skip Barber - 3 Day Racing School](https://www.skipbarber.com/courses/3-day-racing-school/)
- [Skip Barber - Advanced Coaching](https://www.skipbarber.com/courses/advanced-coaching/)
- [BMW Performance Center - Driver's School](https://bmwperformancecenter.com/driverschool/)
- [Porsche Track Experience](https://experience.porsche.com/en/track/track-experience/about-track-experience)
- [Robb Report - How BMW's Performance Driving School Fast-Tracks Aspiring Racers](https://robbreport.com/motors/cars/how-bmws-performance-driving-school-fast-tracks-aspiring-racers-1234624379/)

**NASA HPDE Run Group Skills Progression**

| Level | Who | Skills Taught | Key Requirements |
|-------|-----|---------------|------------------|
| **HPDE1** | Zero or very few track days | Flag stations, car prep, seating, car balance, driving technique basics. Passing only on straights with point-by. In-car instructor provided. | None -- entry level |
| **HPDE2** | Novice solo drivers, some track days, signed off on at least one track | Basic knowledge + comfort without instructor. Grid procedures, passing rules, flags mastered. Point-by passing on straights. | Instructor sign-off from HPDE1 |
| **HPDE3** | Intermediate, multiple HPDEs on more than one track | Variety of tracks, signed off for each. Passing with point-by anywhere on track. Technique refinement. | Written recommendation + check ride from instructor |
| **HPDE4** | Advanced, significant experience | Open passing without point-by, anywhere on track. 20+ track days. Self-sufficient. | Written recommendation + check ride |

The typical progression timeline is highly individual. Forum discussions suggest 5-15 track days to move from HPDE1 to HPDE2 (depending on prior driving experience), 15-30 total track days to reach HPDE3, and 30-50+ track days for HPDE4. These are rough estimates -- advancement is competency-based, not time-based.

**Sources:**
- [NASA HPDE Official](https://drivenasa.com/hpde/)
- [NASA HPDE - Florida Region](https://drivenasafl.com/driving/hpde/)
- [AutoInterests - Run Group Guide](https://autointerests.com/run-group-guide)
- [The Peaches - Run Groups in HPDE](https://www.thepeaches.com/HPDE/groups.htm)
- [EvolutionM Forum - HPDE1 to HPDE3/4 Timeline](https://www.evolutionm.net/forums/motor-sports/318060-nasa-hpde1-hpde-3-4-how-long-did-take.html)
- [Motorsport Safety - HPDE](https://www.motorsport-safety.org/hpde)

**Just-in-Time vs Just-in-Case Learning**

"Just-in-time" learning delivers information precisely when the learner needs it, while "just-in-case" learning front-loads everything. For track driving:

- **Novices need just-in-case basics**: flag meanings, track etiquette, fundamental concepts (racing line, braking zones) BEFORE getting on track.
- **Intermediate+ drivers benefit from just-in-time coaching**: "Your data shows you're braking 15m early at T5 -- here's a landmark to aim for." This is precisely what our AI coaching system can excel at.

The driving instructor analogy from cognitive load theory research illustrates this perfectly: instructors teach mirror, signal, manoeuvre in isolation first, then combine them into one smooth process, then combine that with other skills. This is classic scaffolding.

**Readiness Indicators for Level Progression**

From the research, the key indicators that a driver is ready for more advanced coaching:
1. **Consistency**: Lap time standard deviation drops below a threshold (e.g., < 2% of best lap)
2. **Automaticity**: Basic skills (line, brake points) executed without conscious effort -- evidenced by low variance in fundamental metrics
3. **Capacity for additional cognitive load**: Driver can maintain performance while processing new information
4. **Specific skill mastery**: Passes all criteria for current level (e.g., consistent late apex, smooth inputs)

### Recommendations for Our 3-Tier System

1. **Implement ZPD-aware coaching boundaries**: Each skill level should have explicit "DO teach" and "DO NOT teach" lists, matching the current `_SKILL_PROMPTS` structure but more granular
2. **Add progression detection**: Monitor if a driver's telemetry patterns consistently match a higher skill level's expected behaviors
3. **Scaffold drill complexity**: Current drill templates are one-size-fits-all. Create 3 variants of each drill (scaffolded for each skill level)

### Draft Coaching Language Examples

**Novice (HPDE1-2):**
> "Great job getting consistent lap times! Your data shows your brake point at Turn 5 varies by about 20 meters between laps. Pick one fixed reference point -- like the 3-board marker -- and hit it every single lap for the next 3 laps. Consistency is the foundation of speed."

**Intermediate (HPDE3):**
> "Your brake points at Turn 5 are consistent -- now let's optimize. You're braking at the 3-board but your best lap shows you can carry it to the 2-board. Try moving your brake point 3 meters closer each session until you feel the car's weight shift helping you rotate at turn-in."

**Advanced (HPDE4+):**
> "At Turn 5, your brake initiation is consistent at the 2-board, but your brake trace shows a plateau at 0.8G before tapering -- you're leaving 0.15G of deceleration on the table. The 2-board is actually 4m early for your current entry speed of {{speed:92}}. Challenge: reach threshold (0.95G+) within 0.2s of initial application, then modulate trail pressure based on rotation need."

### Proposed Telemetry-Based Skill Detection Criteria

| Metric | Novice | Intermediate | Advanced |
|--------|--------|-------------|----------|
| Lap time CV (coefficient of variation) | > 3% | 1.5-3% | < 1.5% |
| Brake point std dev (avg across corners) | > 12m | 5-12m | < 5m |
| Min speed std dev (avg across corners) | > 4 mph | 2-4 mph | < 2 mph |
| Peak brake G (session max) | < 0.5G | 0.5-0.8G | > 0.8G |
| Trail braking present (% of corners) | < 20% | 20-60% | > 60% |
| Throttle commit consistency (std dev) | > 15m | 8-15m | < 8m |

---

## Topic 2: Driver Archetype Detection from Telemetry

### Key Findings

**Driving Style Identification from Telemetry**

Research confirms that driving styles can be reliably identified from telemetry data alone. A landmark 2023 study using a professional racing simulator (Assetto Corsa Competizione) with 174 participants and 1,327 laps demonstrated that K-means clustering on telemetry features produces three distinct performance clusters. An XGBoost classifier achieved 97.19% accuracy in predicting which cluster a new lap belongs to.

Key telemetry features that differentiate drivers:
- Metrics derived from **throttle, brake, and steering angle** play a major role in racing performance
- Fast drivers: accelerate earlier and more quickly after corners, show sharper throttle and higher brake applications, demonstrate greater trail braking application
- Slow drivers: brake earlier, apply brakes right before corners but with less precision, show more throttle fluctuation

**Sources:**
- [Springer - An AI Approach for Analyzing Driving Behaviour in Simulated Racing Using Telemetry Data (2023)](https://link.springer.com/chapter/10.1007/978-3-031-49065-1_19)
- [ScienceDirect - AI-enabled prediction of sim racing performance using telemetry data (2024)](https://www.sciencedirect.com/science/article/pii/S2451958824000472)
- [Springer - A Machine Learning Approach for Modeling and Analyzing of Driver Performance in Simulated Racing](https://link.springer.com/chapter/10.1007/978-3-031-26438-2_8)
- [Springer - Data Science Applied to Vehicle Telemetry Data to Identify Driving Behavior Profiles](https://link.springer.com/chapter/10.1007/978-3-031-36121-0_52)

**Common Driver Archetypes in Track Day Driving**

Based on telemetry pattern analysis and coaching literature, we can define these archetypes:

| Archetype | Telemetry Signature | Description |
|-----------|-------------------|-------------|
| **The Early Braker** | Brake points 15-30m before optimal, low peak brake G, long coast phase before turn-in | Brakes too early and too gently. Coasts into corners. Common in novices. |
| **The Late Braker / Hero** | Late brake points but inconsistent, sometimes locks up, high variance in brake-to-apex distance | Brakes aggressively but inconsistently. Occasionally spectacular, often loses time recovering. |
| **The Coaster** | Gap between brake release and throttle application, low min-speed, late throttle commit | Releases brakes, coasts through the corner, then picks up throttle late. No trail braking. |
| **The Smooth Operator** | Consistent metrics across laps, gradual transitions, moderate G-forces, clean traces | Drives smoothly and consistently but may not be at the limit. Lap times are repeatable but potentially leaving time on the table. |
| **The Aggressive Rotator** | High lateral G, abrupt steering inputs, tight apex, aggressive throttle on exit | Forces the car to rotate aggressively. Can be fast but burns tires and risks snap oversteer. |
| **The Conservative Liner** | Very consistent line (low apex variance), but consistently early apex or wide entry | Drives the same (suboptimal) line every lap with high consistency. Needs line optimization, not consistency work. |
| **The Trail Brazer** | Strong trail braking evidence, good brake-to-turn overlap, but sometimes overdoes it (too much brake past apex) | Has learned trail braking but hasn't refined the release point. Sometimes rotates too much. |

**Sources:**
- [Driver61 - The Ultimate Guide to Braking on Track](https://driver61.com/uni/braking/)
- [Blayze - The Braking Masterclass For Racecar Drivers](https://blayze.io/blog/car-racing/braking-masterclass-for-racecar-drivers)
- [Paradigm Shift Racing - The Truth About Trail Braking](https://www.paradigmshiftracing.com/racing-basics/the-truth-about-trail-braking)
- [Elchingon Racing - Trail Braking Mastery](https://elchingonracing.com/how-to-trail-brake/)

**Machine Learning Approaches for Driver Behavior Classification**

The research literature converges on several effective approaches:

1. **K-Means Clustering** on normalized telemetry features (speed, brake, throttle, steering) -- used for unsupervised archetype discovery. Produces 3-5 natural clusters.
2. **XGBoost / Random Forest** for supervised classification once clusters are labeled -- achieves 92-97% accuracy.
3. **LSTM Networks** for capturing temporal dependencies in sequential driving data -- useful for identifying patterns that span multiple seconds (e.g., brake-to-throttle transitions).
4. **Feature subset selection**: Out of 84 telemetry features, a subset of 10 features was sufficient for accurate classification. The most predictive features were: mean throttle speed, brake point timing, peak brake pressure, throttle release timing, and steering smoothness.

**Sources:**
- [Springer Nature - Comprehensive Review on Data-driven Driver Behaviour Scoring (2025)](https://link.springer.com/article/10.1007/s44163-025-00244-6)
- [ArXiv - XAI-Driven Machine Learning System for Driving Style Recognition (2025)](https://arxiv.org/html/2509.00802)
- [MDPI - Driving Behaviour Analysis Using Machine and Deep Learning Methods](https://www.mdpi.com/1424-8220/21/14/4704)
- [PMC - Simulation-based Driver Scoring and Profiling System (2024)](https://pmc.ncbi.nlm.nih.gov/articles/PMC11600037/)

**How Professional Teams Use Data to Characterize Driver Tendencies**

Professional racing engineers compare driver telemetry overlays to identify individual tendencies:
- **Brake trace shape**: Pro drivers show nearly identical traces lap after lap (< 3% brake pressure variation). The shape reveals style: sharp spike + taper = aggressive threshold braker; gradual ramp = conservative braker.
- **Throttle application rate**: Speed of throttle application from 0% to full throttle on corner exit differentiates aggressive vs. smooth drivers.
- **Steering angle vs. speed relationship**: Reveals whether a driver fights the car (high steering corrections) or drives with it (smooth, minimal corrections).
- **Speed differential at key points**: Comparing speed at identical distance points across laps shows where a driver is consistent vs. variable.

**Sources:**
- [Full Grip Motorsport - Telemetry Analysis](https://www.fullgripmotorsport.com/telemetry)
- [HP Academy - Going Faster with Data Analysis](https://www.hpacademy.com/technical-articles/going-faster-with-data-analysis/)
- [Coach Dave Academy - Understanding Brake Traces](https://coachdaveacademy.com/tutorials/a-delta-guide-understanding-brake-traces-to-be-faster/)

### Recommendations for Our 3-Tier System

1. **Implement per-corner archetype detection**: For each corner, classify the driver's behavior into one of the archetypes above using the telemetry metrics we already compute (brake_point_m, peak_brake_g, min_speed_mps, throttle_commit_m, apex_type).
2. **Use archetypes to personalize coaching**: Instead of generic advice, tailor the tip to the specific archetype. "You're coasting into T5" is more actionable than "improve your corner entry."
3. **Track archetype shifts across sessions**: If a driver was "The Early Braker" at T5 three sessions ago and is now "The Trail Brazer," the coaching should acknowledge growth and refine the next skill.

### Draft Coaching Language Examples

**Novice - Early Braker detected at T3:**
> "At Turn 3, you're braking about 15 meters before you need to. That's totally normal -- your brain is being cautious while you learn the track. For your next session, try moving your brake point just 3 meters closer to the corner. That's about one car length. You'll be surprised how much time that finds."

**Intermediate - Coaster detected at T7:**
> "Turn 7 data shows a gap between your brake release and throttle application -- you're 'coasting' for about 40 meters. That dead zone costs you roughly 0.3s per lap. Focus on trail braking through the turn-in: as you unwind steering, progressively transition brake pressure to throttle pressure. The car should never be in neutral -- either decelerating or accelerating."

**Advanced - Trail Brazer overdoing it at T2:**
> "Your trail braking commitment at Turn 2 is strong -- brake traces show consistent overlap past turn-in. However, your brake release point is 8m past the apex on average, and you're carrying 12% brake pressure at mid-corner when the car is already rotated. This is costing you 0.08s through excess drag. Target: release all brake by the apex. Your rotation should come from the initial trail phase, not sustained pressure."

### Proposed Telemetry-Based Archetype Detection

```python
# Per-corner archetype detection logic (pseudocode)
def detect_corner_archetype(corner_data: list[Corner]) -> str:
    avg_brake_to_apex = mean(c.apex_distance_m - c.brake_point_m for c in corner_data)
    avg_peak_g = mean(c.peak_brake_g for c in corner_data)
    throttle_gap = mean(c.throttle_commit_m - c.apex_distance_m for c in corner_data)
    brake_std = stdev(c.brake_point_m for c in corner_data)
    has_trail_braking = fraction(c where brake overlaps turn-in)

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
    elif apex_consistency < 0.1 and apex_type == "early" > 50%:
        return "conservative_liner"
    else:
        return "balanced"
```

---

## Topic 3: External Focus of Attention - Implementation Depth

### Key Findings

**Wulf & Lewthwaite's External Focus Research**

The most comprehensive meta-analyses (Chua, Diaz, Lewthwaite, Kim, & Wulf, 2021) confirmed the **superiority of an external focus relative to an internal focus for both immediate performance and learning**. The effect is robust across age, health condition, and expertise level. The OPTIMAL theory of motor learning (Wulf & Lewthwaite, 2016) identifies three key factors: external focus, enhanced expectancies, and autonomy support.

**Key principle**: External focus directs attention to the intended movement effects (what happens in the environment), while internal focus directs attention to body movements. External focus consistently produces better outcomes.

**Sources:**
- [PubMed - Meta-analyses on External Attentional Focus (Chua et al., 2021)](https://pubmed.ncbi.nlm.nih.gov/34843301/)
- [Gabriele Wulf Publications Page](https://gwulf.faculty.unlv.edu/publications-2/)
- [Tandfonline - Meta-analysis on Immediate Effects of Attentional Focus (2022)](https://www.tandfonline.com/doi/abs/10.1080/1750984X.2022.2062678)
- [ScienceDirect - Golf Skill Learning: External Focus (An & Wulf, 2024)](https://www.sciencedirect.com/science/article/abs/pii/S1469029223001875)

**The Distance Effect**

Wulf's research demonstrated that **more distal external focus produces better performance than proximal external focus**. Examples:
- Dart throwing: focusing on the bullseye (distal) produced better accuracy than focusing on the dart's flight (proximal)
- Standing long jump: focusing on jumping toward a target (distal) produced longer jumps than focusing on jumping past the start line (proximal)
- Greater distance of external focus **increased automaticity in movement control**

This is explained by the "constrained action hypothesis": focusing on effects close to the body (or on the body itself) constrains the motor system, disrupting automatic control processes. More distal focus allows the motor system to self-organize optimally.

An important nuance from 2020 research: the optimal external focus distance may differ between low-skilled and high-skilled performers. High-skilled performers may benefit more from distal focus, while low-skilled performers may need a more proximal (but still external) focus to have a concrete reference.

**Sources:**
- [PubMed - Increasing the Distance of an External Focus Enhances Learning (Wulf et al., 2003)](https://pubmed.ncbi.nlm.nih.gov/12589447/)
- [ScienceDirect - The Distance Effect and Level of Expertise (2020)](https://www.sciencedirect.com/science/article/abs/pii/S0167945720305273)
- [Springer Nature - Increasing the Distance of an External Focus Enhances Learning](https://link.springer.com/article/10.1007/s00426-002-0093-6)
- [Wulf - Attentional Focus Review 2013 (PDF)](https://gwulf.faculty.unlv.edu/wp-content/uploads/2018/11/Wulf_AF_review_2013.pdf)

**External Focus Cues in Driving/Motorsport**

Racing coaching already uses external focus heavily, often without knowing the research basis:
- **"Look where you want to go"** -- the most fundamental external focus cue in driving. The car follows the eyes. Vision leads the car by 1-2 seconds.
- **"Focus on the apex cone"** -- directs attention to an external reference point rather than steering wheel movements
- **"Watch the exit curbing"** -- distal external focus (the corner exit is further away than the apex)
- **"Let the car flow to the outside"** -- focuses on the car's trajectory rather than body movements

The Speed Secrets coaching approach emphasizes that "performance or race driving is more of a mental activity than a physical one" and that the driver's focus should always be on the next reference point, never on the current one.

**Sources:**
- [Speed Secrets - Focus Your Mind Where You Want to Go](https://speedsecrets.com/focus-your-mind-where-you-want-to-go/)
- [Speed Secrets - How Performance Drivers Use Their Vision](https://speedsecrets.com/how-performance-drivers-use-their-vision/)
- [Driver61 - How to Fully Utilise Vision, Feel & Hearing](https://driver61.com/uni/utilising-senses/)
- [Blayze - How Do I Remain Focused During a Longer Stint?](https://blayze.io/blog/car-racing/remaining-focused-on-the-race-track)

**Translating Telemetry Numbers into External-Focus Language**

This is the critical gap in most telemetry-based coaching. Raw telemetry speaks in internal-focus language: "Apply 0.9G of brake force," "Your steering angle was 45 degrees." Effective coaching translates to external focus:

| Internal Focus (Bad) | External Focus (Good) |
|---------------------|----------------------|
| "Press the brake pedal harder" | "Feel the car nose-dive into the pavement -- that's the weight loading the front tires" |
| "Turn the steering wheel 15 degrees more" | "Point the car toward the apex cone; the car should track straight to it" |
| "Apply throttle at 40% first" | "Listen to the engine note rise smoothly as the car straightens" |
| "Your deceleration was only 0.6G" | "The car can stop much shorter -- feel the seatbelt pull you forward harder" |
| "Your min speed was 3 mph low" | "Carry enough speed that you barely need to add power through the apex" |

**Sources:**
- [Driver61 - How to Drive the Perfect Racing Line](https://driver61.com/uni/racing-line/)
- [Apex Pro Track Coach](https://apextrackcoach.com/)

### Recommendations for Our 3-Tier System

1. **Rewrite all coaching prompts to prefer external-focus language**: Add a system-level instruction that says "Frame all tips in terms of what the driver should see, hear, and feel -- NOT what their body should do."
2. **Use the distance effect by skill level**: Novices get proximal external cues ("focus on the brake board"), intermediate get mid-range ("focus on the apex"), advanced get distal ("focus on the exit point and where the car will be 2 seconds from now").
3. **Add external-focus translation rules to the prompt**: Include a mapping table showing the AI how to convert telemetry metrics into external-focus coaching language.

### Draft Coaching Language Examples

**Novice (proximal external focus):**
> "At Turn 5, as you approach the 3-board marker, picture the car planting its nose into the pavement. Feel the seatbelt pull you forward as you squeeze the brake. Keep your eyes locked on that apex cone -- the car will follow where you look."

**Intermediate (mid-range external focus):**
> "At Turn 5, your eyes should already be on the apex as you pass the 3-board. Feel the front of the car bite into the turn as you trail the brakes. The car should draw a smooth arc toward the apex -- if it feels like you're fighting it, you've turned in too early."

**Advanced (distal external focus):**
> "At Turn 5, your focus should be on the exit curbing before you even reach the apex. Let the car's rotation carry it from turn-in through the apex naturally. The speed you carry past the exit point is what matters -- your best laps show {{speed:97}} at track-out. Chase that number by looking further ahead."

### Proposed External Focus Integration

Add a new constant to the prompt system:

```python
EXTERNAL_FOCUS_INSTRUCTION = """
CRITICAL COACHING PRINCIPLE — External Focus of Attention:
Research shows that coaching language focused on movement EFFECTS
(what the car does, what the driver sees/feels) produces better
learning than language about body movements (what the driver's
hands/feet do).

ALWAYS frame tips in terms of:
- What the driver should SEE (reference points, trajectory)
- What the driver should FEEL (car behavior, weight shifts, g-forces)
- What the driver should HEAR (engine note, tire noise)

NEVER frame tips in terms of:
- What the driver's foot should do
- How hard to press a pedal
- Specific steering wheel angles
- Body positioning instructions

For NOVICE: Use proximal references (brake boards, nearby markers)
For INTERMEDIATE: Use mid-range references (apex, car trajectory)
For ADVANCED: Use distal references (exit point, following straight)
"""
```

---

## Topic 4: Implicit vs Explicit Learning in Motorsport

### Key Findings

**When to Use Implicit vs Explicit Coaching**

Research demonstrates that implicitly learned motor skills are more robust under pressure, fatigue, and multitasking conditions. Out of 10 studies comparing implicit and explicit learning, seven showed implicit learning resulted in better athletic performance.

The mechanism is "reinvestment theory" (Masters, 1992): under stress, athletes "reinvest" explicit knowledge into motor execution, disrupting automatized performance. If the athlete never accumulated explicit rules in the first place, there's nothing to reinvest -- and performance remains stable.

A 2025 paper in Frontiers in Psychology confirmed that "studies on task performance under pressure underscore the resilience of implicitly learned processes."

**Sources:**
- [PLOS One - Does Implicit Motor Learning Lead to Greater Automatization? (2018)](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0203591)
- [Frontiers in Psychology - Implicit and Explicit Learning Strategies and Fatigue (2025)](https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2025.1438313/full)
- [Tandfonline - An Explicit Look at Implicit Learning: An Interrogative Review (2023)](https://www.tandfonline.com/doi/full/10.1080/21640629.2023.2179300)
- [InnerDrive - Does Implicit Learning Improve Performance Under Pressure?](https://blog.innerdrive.co.uk/sports/implicit-learning-for-performance-under-pressure)
- [ResearchGate - Analogy versus Explicit and Implicit Learning (2020)](https://efsupit.ro/images/stories/septembrie2020/Art%20339.pdf)

**Analogy-Based Coaching for Motor Skills**

Analogy learning is the most consistently effective method for inducing implicit motor learning. It works by condensing multiple explicit rules into a single metaphor. Key research:

- Table tennis novices learning forehand topspin: analogy group ("draw a right triangle with the bat") performed as well as the explicit group during learning but maintained performance under stress, while the explicit group degraded.
- Analogy groups reported **less declarative knowledge** than explicit groups in all 12 comparisons that checked -- confirming they learned implicitly.
- Analogy learning **combines the benefits of implicit and explicit motor learning**, especially in novices.

Applied to driving:
- "Pour water from a pitcher" for smooth steering
- "Squeeze a sponge" for progressive brake application
- "Uncoil a spring" for throttle on exit
- "Drive like you're on ice" for smooth inputs

**Sources:**
- [PubMed - Analogy Learning: A Means to Implicit Motor Learning (Liao & Masters, 2001)](https://pubmed.ncbi.nlm.nih.gov/11354610/)
- [Sage Journals - Coaching Through Implicit Motor Learning Techniques (Poolton & Zachry, 2007)](https://journals.sagepub.com/doi/10.1260/174795407780367177)
- [Tandfonline - Analogy Learning: A Means to Implicit Motor Learning](https://www.tandfonline.com/doi/abs/10.1080/02640410152006081)
- [Perception Action Podcast - Implicit Learning & Learning By Analogy](https://perceptionaction.com/16-2/)
- [Sport Science Support - Implicit Learning](https://www.sportsciencesupport.com/implicit-learning/)
- [ITF Coaching Review - Implicit Motor Learning: Designing Practice for Performance](https://itfcoachingreview.com/index.php/journal/article/download/448/1220/1831)

**Cognitive Load and Working Memory in Driving**

Working memory capacity is approximately **4 items** (updated from Miller's classic "7 plus or minus 2" -- modern research has revised downward). Driving itself consumes significant working memory, especially at novice levels.

Key findings:
- Even adding one secondary task to driving creates "substantial cognitive strain that forces trade-offs in performance"
- Cognitive load "selectively impairs driving subtasks that rely on cognitive control but leaves automatic performance unaffected"
- Driving instructors intuitively apply cognitive load theory: they teach mirror, signal, manoeuvre in isolation first, then combine them

**Practical limit**: A novice driver can likely process **1-2 explicit coaching instructions per corner** at most. An intermediate driver can handle 2-3. An advanced driver, whose basic skills are automatized, can process 3-4 specific technical points simultaneously.

**Sources:**
- [ScienceDirect - Cognitive Load, Working Memory Capacity and Driving Performance (2022)](https://www.sciencedirect.com/science/article/pii/S1369847822002819)
- [ScienceDirect - Investigating the Influence of Working Memory Capacity When Driving](https://www.sciencedirect.com/science/article/abs/pii/S0001457513002601)
- [ScienceDirect - On the Importance of Working Memory in the Driving Safety Field (2023)](https://www.sciencedirect.com/science/article/abs/pii/S0001457523001185)
- [Wikipedia - The Magical Number Seven, Plus or Minus Two](https://en.wikipedia.org/wiki/The_Magical_Number_Seven,_Plus_or_Minus_Two)
- [Big Maths - Driving Instructors Have Cognitive Load Theory Nailed](https://www.bigmaths.com/driving-instructors-have-cognitive-load-theory-nailed/)
- [The Decision Lab - Cognitive Load Theory](https://thedecisionlab.com/reference-guide/psychology/cognitive-load-theory)

### Recommendations for Our 3-Tier System

1. **Cap the number of explicit tips per corner by skill level**: Novice gets 1 tip per corner (max 2 priority corners total), intermediate gets 1-2 tips per corner (max 3 priorities), advanced gets detailed multi-point analysis.
2. **Introduce analogy-based coaching at novice/intermediate levels**: Build a library of driving analogies and inject them into the prompt for novice and intermediate skill levels.
3. **Use implicit framing for pressure-sensitive skills**: Trail braking and threshold braking should be coached implicitly for intermediates (through analogies and feel-based cues) before being made explicit at the advanced level.

### Draft Coaching Language Examples

**Novice (1 tip per corner, analogy-based):**
> "**Turn 5 -- Brake Squeeze Drill**: Imagine squeezing a sponge when you hit the brakes -- start gentle, squeeze firmly, then slowly release as you turn in. Spend 3 laps just feeling that squeeze. Don't worry about your brake point yet."

**Intermediate (2 tips per corner, blended implicit/explicit):**
> "**Turn 5**: Your brake trace shows an abrupt release at turn-in (like dropping a sponge instead of slowly releasing it). This causes the car to 'stand up' and lose front grip. Focus on two things: (1) Feel the car's nose stay planted as you gradually release the brake through turn-in. (2) Once past the apex, progressively 'uncoil' the throttle as you unwind the steering."

**Advanced (explicit technical detail):**
> "**Turn 5**: Brake trace analysis shows your initial application reaches 0.82G in 0.15s (good attack), but you plateau at 0.82G for 40ms before trail-off begins. This suggests you're not reaching threshold. Your peak decel capacity based on tire mu and weight transfer is approximately 0.95G. The 0.13G deficit costs ~0.04s per corner. Additionally, your trail brake taper shows a step at 30% pressure rather than a linear decay -- this creates a weight transfer discontinuity at mid-corner."

### Proposed Analogy Library

```python
COACHING_ANALOGIES = {
    "brake_application": {
        "analogy": "Squeeze a sponge",
        "skill_levels": ["novice", "intermediate"],
        "explanation": "Apply brakes progressively like squeezing water from a sponge -- firm but gradual, not a sudden stomp",
    },
    "brake_release": {
        "analogy": "Lower a sleeping baby into a crib",
        "skill_levels": ["novice"],
        "explanation": "Release the brake as gently as putting down a sleeping baby -- any sudden movement disrupts the car's balance",
    },
    "throttle_exit": {
        "analogy": "Uncoil a spring",
        "skill_levels": ["novice", "intermediate"],
        "explanation": "Apply throttle progressively like a spring unwinding -- smooth and steady, matching the steering angle as it unwinds",
    },
    "steering_smoothness": {
        "analogy": "Stir a pot of soup without spilling",
        "skill_levels": ["novice"],
        "explanation": "Turn the wheel as smoothly as stirring soup -- any jerk would splash it over the edge",
    },
    "trail_braking": {
        "analogy": "Slowly open a door against a spring",
        "skill_levels": ["intermediate"],
        "explanation": "As you turn in, release the brake like you're slowly opening a spring-loaded door -- the pressure decreases naturally as the door opens wider",
    },
    "vision": {
        "analogy": "Thread a needle with your eyes first",
        "skill_levels": ["novice", "intermediate"],
        "explanation": "Your eyes should arrive at each reference point before the car does -- thread the needle with your vision, and the car follows",
    },
    "weight_transfer": {
        "analogy": "A ball rolling in a bowl",
        "skill_levels": ["intermediate"],
        "explanation": "Imagine the car's weight as a ball in a bowl -- smooth inputs keep it rolling predictably, jerky inputs make it slosh unpredictably",
    },
}
```

---

## Topic 5: Novice-to-Expert Progression Models

### Key Findings

**Dreyfus Model of Skill Acquisition Applied to Motorsport**

The Dreyfus model identifies five stages: Novice, Advanced Beginner, Competent, Proficient, and Expert (with a sixth "Mastery" stage for exceptional performers). Originally applied to driving.

| Stage | Characteristic | Motorsport Application |
|-------|---------------|----------------------|
| **Novice** | Follows context-free rules. Slow, clumsy, requires conscious effort. | "Brake at the 3-board. Turn in at the cone. Apex at the curbing." Rigid, rule-following. |
| **Advanced Beginner** | Recognizes situational aspects. Applies maxims based on experience. | "That corner felt too fast on entry -- I should brake a bit earlier next time." Starts to feel the car but still thinks about it. |
| **Competent** | Conscious planning. Overwhelmed by options but starting to prioritize. | "I need to focus on T5 and T9 because that's where I lose the most time." Makes deliberate practice decisions. |
| **Proficient** | Intuitive recognition of situations. Plans still deliberate. | "The car felt loose mid-corner at T5 -- probably too much trail brake." Recognizes problems intuitively but still consciously plans fixes. |
| **Expert** | Fluid, effortless performance. No deliberate decisions. | "Knows how to perform the act without evaluating and comparing alternatives." Drives on autopilot, adjusts smoothly to unexpected changes. |

The fundamental progression: **as experience grows, drivers gradually let go of rules and gain the ability to act fluidly, without deliberation.**

**Sources:**
- [Wikipedia - Dreyfus Model of Skill Acquisition](https://en.wikipedia.org/wiki/Dreyfus_model_of_skill_acquisition)
- [DevMts - Novice to Expert: The Dreyfus Model (PDF)](https://devmts.org.uk/dreyfus.pdf)
- [Toolshero - Dreyfus Model of Skill Acquisition](https://www.toolshero.com/human-resources/dreyfus-model-of-skill-acquisition/)
- [MindTools - The Dreyfus Model of Skill Acquisition](https://www.mindtools.com/atdbxer/the-dreyfus-model-of-skill-acquisition/)

**Fitts & Posner's Three Stages of Motor Learning**

The Fitts & Posner model is more mechanistic than Dreyfus and maps directly to coaching strategies:

| Stage | Motor Learning State | Coaching Implications |
|-------|---------------------|----------------------|
| **Cognitive** | Heavy reliance on verbal instructions and explicit feedback. Erratic performance. Large errors. High cognitive demand. | Provide clear, simple instructions. Use demonstrations. Tolerate errors. Focus on broad movement patterns, not details. Use analogies over explicit rules. |
| **Associative** | Practice reduces errors. Connections form between movements and outcomes. Consistency increases. Exploring the "solution space." | Shift to refinement. Provide specific feedback on subcomponents. Introduce variability. The driver can now process "why" explanations, not just "what" instructions. |
| **Autonomous** | Performance is automatic. Minimal cognitive processing. Can attend to strategic/tactical concerns. Stable under pressure. | Coaching focuses on micro-optimization, strategic concerns, and preventing stagnation. Explicit rules may actually hurt (reinvestment). Use challenges and constraints to maintain engagement. |

**Sources:**
- [Sport Science Insider - Fitts & Posner's Stages of Learning](https://sportscienceinsider.com/stages-of-learning/)
- [Human Kinetics - Understanding Motor Learning Stages](https://us.humankinetics.com/blogs/excerpt/understanding-motor-learning-stages-improves-skill-instruction)
- [PMC - The Role of Strategies in Motor Learning](https://pmc.ncbi.nlm.nih.gov/articles/PMC4330992/)
- [Fiveable - Fitts and Posner Model](https://fiveable.me/key-terms/cognitive-psychology/fitts-and-posner-model)

**Deliberate Practice Timelines for Motorsport**

There is no published research giving a precise "hours to mastery" figure for track driving. However, triangulating from multiple sources:

| Transition | Typical Track Days | Typical Laps | Key Milestone |
|-----------|-------------------|-------------|---------------|
| Complete novice to HPDE2 (solo-safe) | 5-15 days | 200-600 laps | Consistent line, safe at speed, no spins |
| HPDE2 to HPDE3 (intermediate) | 15-30 days | 600-1,200 laps | Multiple tracks, open passing, technique refinement |
| HPDE3 to HPDE4 (advanced) | 30-50+ days | 1,200-2,000+ laps | Open passing, consistent fast laps, self-coaching ability |
| HPDE4 to instructor/competitive | 50-100+ days | 2,000-4,000+ laps | Teaching ability, adaptability, near-limit consistency |

These are rough community estimates. The key insight: **progression is not linear**. Initial improvement is rapid, then plateaus emerge at each transition point. The transition from HPDE3 to HPDE4 often takes the longest because it requires not just technique but judgment, adaptability, and automaticity.

**Sources:**
- [NASA HPDE Official](https://drivenasa.com/hpde/)
- [No Money Motorsports - 7 Simple Tips to Move Up HPDE Ranks](https://nomoneymotorsports.com/2019/08/12/7-simple-tips-to-move-up-the-hpde-ranks-and-win-hpde-in-no-time-post-37/)
- [Driver61 - Track Day Guide](https://driver61.com/resources/track-day-guide/)
- [Grassroots Motorsports - How to Shorten Lap Times](https://grassrootsmotorsports.com/articles/how-shorten-lap-times-improving-one-section-track/)

**Telemetry Patterns Indicating Level Transitions**

Based on the research, these telemetry patterns signal a driver is transitioning between levels:

| Transition | Telemetry Signal |
|-----------|-----------------|
| Novice -> Intermediate | Lap time CV drops below 3%. Brake point std dev decreases. Consistent line emerges (apex type stabilizes). Peak brake G increases above 0.5G. |
| Intermediate -> Advanced | Trail braking evidence appears (>30% of corners). Throttle commit moves earlier. Min speed increases at corners previously feared. Brake trace shows progressive release rather than abrupt. |
| Advanced -> Expert | Brake pressure variation < 3% across laps. Composite gain drops below 0.5s. Corner grades are consistently A/B. Session-to-session improvement on the same track < 0.2s (at the limit). |

**Automaticity and Coaching Toward It**

The concept of automaticity -- performing a skill without conscious thought -- is the ultimate goal. From the research:
- "Automatized motor skills are less easily disturbed when the performer's cognitive resources are compromised, for instance due to fatigue, psychological pressure, or when concurrent tasks are performed."
- "Execution of implicitly learned motor skills is more stable in terms of intra-individual variability than explicitly learned skills."
- From the KB snippets: "The $10 attention budget" -- as corners become automatic through practice, attention frees up for refinement.

**Sources:**
- [PMC - Multiple Systems for Motor Skill Learning](https://pmc.ncbi.nlm.nih.gov/articles/PMC4346332/)
- [APA - Modeling the Distinct Phases of Skill Acquisition (PDF)](https://www.apa.org/pubs/journals/features/xlm-xlm0000204.pdf)
- [PMC - Motor Learning Unfolds over Different Timescales in Distinct Neural Systems](https://pmc.ncbi.nlm.nih.gov/articles/PMC4672876/)

### Recommendations for Our 3-Tier System

1. **Map our 3 tiers to motor learning stages**: Novice = Cognitive stage (Fitts & Posner) / Novice + Advanced Beginner (Dreyfus). Intermediate = Associative stage / Competent + Proficient. Advanced = Autonomous stage / Expert.
2. **Adjust coaching style, not just content, by stage**: Cognitive stage gets analogies and simple rules. Associative stage gets specific data-driven feedback. Autonomous stage gets micro-optimization challenges.
3. **Track automaticity metrics**: Add a "consistency score" per corner that tracks whether a skill has become automatic (low variance = automatic, high variance = still consciously managed).

### Draft Coaching Language Examples

**Novice (Cognitive Stage -- rules + analogies):**
> "Here are your three reference points for Turn 3: **Brake** at the tall white board. **Turn in** where the curbing starts to curve. **Track out** toward the dirt patch on the left. Spend 3 laps hitting these exact points. Don't worry about speed -- just hit the same marks every time. Like threading a needle: eyes first, car follows."

**Intermediate (Associative Stage -- specific data + why):**
> "Your Turn 3 reference points are consistent now (brake point std dev: 4.2m -- nice!). Time to refine: your brake trace shows you're releasing to 0% brake at turn-in, then coasting for 15m before throttle. This costs 0.15s. The physics: when you drop all brake at turn-in, the car's weight snaps rearward and the front loses grip. Try maintaining 10-15% brake past turn-in -- you'll feel the front tires bite harder through the first half of the corner."

**Advanced (Autonomous Stage -- micro-optimization + challenge):**
> "Turn 3 is your most complete corner (grade: A-). The gap to theoretical is 0.04s, coming from your trail brake release profile. Your best laps show a linear taper from 40% to 0% over 25m. Your average laps show a step to 20% then a drop -- suggesting you're momentarily holding pressure instead of continuously modulating. This is a muscle memory refinement. Drill: 5 laps at 90% pace, focusing purely on making the brake release as gradual as pouring water from a glass."

### Proposed Progression Tracking

```python
@dataclass
class SkillProgression:
    """Track skill progression metrics across sessions."""
    sessions_analyzed: int
    estimated_level: str  # "novice", "intermediate", "advanced"
    confidence: float  # 0-1

    # Per-skill mastery scores (0-1)
    line_consistency: float
    brake_point_consistency: float
    trail_braking_proficiency: float
    throttle_timing: float
    min_speed_optimization: float

    # Transition indicators
    ready_for_next_level: bool
    blocking_skills: list[str]  # skills preventing level-up

    # Historical trend
    lap_time_trend: str  # "improving", "plateau", "regressing"
    consistency_trend: str  # "improving", "stable", "declining"
```

---

## Topic 6: Personalization Without Explicit Skill Declaration

### Key Findings

**Inferring Skill Level from Telemetry Alone**

Research strongly supports that skill level can be inferred from telemetry. A 2023 study using an AI classification approach on sim racing telemetry achieved 97.19% accuracy in classifying driver performance tiers from telemetry features alone. The most discriminating features:

1. **Lap time consistency** (coefficient of variation)
2. **Brake point variance** (standard deviation across laps)
3. **Peak brake G** (how hard the driver brakes -- novices brake gently)
4. **Throttle application rate** (speed of throttle uptake on corner exit)
5. **Trail braking evidence** (brake-turn overlap)
6. **Min speed at corners** (higher = more confident)
7. **Steering smoothness** (fewer corrections = more skilled)
8. **Throttle commit distance from apex** (earlier = more skilled)
9. **Apex type distribution** (experts hit late apexes more consistently)
10. **Session-over-session improvement rate** (rapid improvement = intermediate; plateaued near limit = advanced)

**Sources:**
- [Springer - AI Approach for Analyzing Driving Behaviour in Simulated Racing (2023)](https://link.springer.com/chapter/10.1007/978-3-031-49065-1_19)
- [ScienceDirect - AI-enabled Prediction of Sim Racing Performance (2024)](https://www.sciencedirect.com/science/article/pii/S2451958824000472)
- [Full Grip Motorsport - Telemetry Analysis](https://www.fullgripmotorsport.com/telemetry)
- [HP Academy - Going Faster with Data Analysis](https://www.hpacademy.com/technical-articles/going-faster-with-data-analysis/)

**Key Metrics That Differentiate Novice from Expert**

| Metric | Novice Pattern | Expert Pattern | Detection Method |
|--------|---------------|----------------|-----------------|
| **Brake pressure traces** | Vary significantly lap to lap. Rarely reach threshold. Abrupt release. | "Almost identical lap after lap" (< 3% variation). Reach threshold. Smooth trail-off. | Compute std dev of brake_point and peak_brake_g across laps |
| **Throttle application** | Hesitant, fluctuating ("pumping"). Late commitment after apex. | Smooth, progressive, early commitment. Clean ramp from 0% to full. | Measure throttle_commit_m distance from apex, detect fluctuations |
| **Min speed at corners** | Low (over-braking), high variance | Optimized (closer to grip limit), low variance | Compare to track-specific benchmarks and compute CV |
| **Steering corrections** | Many mid-corner adjustments | Minimal corrections, one smooth arc | Count steering reversals (not currently tracked in our system) |
| **Apex distribution** | Random mix of early/late/on | Predominantly on-apex or strategically late | Compute apex_type distribution per corner |
| **Lap time progression** | Large initial improvement, then large variance | Small incremental gains, very low variance | Compute lap time trend and CV |

Professional drivers typically show brake pressure variations under 3% across multiple laps, while mid-pack drivers show significant variation in their braking points, pressure application, and release timing. Even a 5% variation in brake pressure or timing can cost multiple tenths per corner.

**Sources:**
- [Coach Dave Academy - Understanding Brake Traces](https://coachdaveacademy.com/tutorials/a-delta-guide-understanding-brake-traces-to-be-faster/)
- [ioda racing - How to Analyze Driver Performance Using Telemetry Data](https://iodaracing.com/formula-1/how-to-analyze-driver-performance-using-telemetry-data/)
- [Apex Sim Racing - Brake Consistency and Lap Performance](https://www.apexsimracing.com/blogs/sim-racing-blog/brake-consistency-secrets-h)

**Automatic Skill Level Detection in Sports**

An AI system for sports education achieved 94% accuracy in skill level classification using kinematic analysis through IMUs, visual features through computer vision, and physiological monitoring through biosensors. In basketball, a machine learning model achieved 93.19% accuracy evaluating player skills from video data.

Key approaches applicable to our system:
- **Cluster-then-classify**: First cluster drivers into natural groups, then label those groups as skill levels. This is unsupervised, so it doesn't require pre-labeled training data.
- **Feature importance ranking**: Use SHAP values or feature importance from tree-based models to understand which metrics matter most for classification.
- **Adaptive thresholds**: Rather than fixed thresholds, use percentile-based thresholds relative to the driver's own history and the track's community benchmarks.

**Sources:**
- [Nature - Intelligent Optimization of Track and Field Teaching Using ML and Wearable Sensors (2025)](https://www.nature.com/articles/s41598-025-20745-9)
- [Nature - Predictive Athlete Performance Modeling with ML and Biometric Data (2025)](https://www.nature.com/articles/s41598-025-01438-9)
- [PMC - AI and ML in Sport Research (2021)](https://pmc.ncbi.nlm.nih.gov/articles/PMC8692708/)
- [PMC - AI and ML Approaches in Sports (2024)](https://pmc.ncbi.nlm.nih.gov/articles/PMC11215955/)
- [ScienceDirect - ML Framework for Evaluating Basketball Player Skill (2025)](https://www.sciencedirect.com/science/article/pii/S1110866525001550)

**Mastery-Based Coaching: Tracking Acquired Skills**

The mastery-based approach tracks individual skill acquisition rather than assigning a global level. A driver might be "advanced" at braking but "novice" at trail braking. This produces more precise, personalized coaching.

Implementation approach:
1. Define a skill tree (braking consistency, brake pressure optimization, trail braking, throttle timing, min speed optimization, line consistency, apex selection)
2. For each skill, define mastery criteria (e.g., "brake point std dev < 5m across 3 consecutive sessions")
3. Track skill state: "not started" -> "learning" -> "developing" -> "mastered"
4. Coach the lowest-mastery skill that's within the driver's ZPD (they've mastered the prerequisite skills)

**Sources:**
- [Tandfonline - ML Approach for Classification of Sports Based on a Coaches' Perspective (2023)](https://www.tandfonline.com/doi/full/10.1080/02640414.2023.2271706)
- [Springer Nature - Methodology and Evaluation in Sports Analytics (2024)](https://link.springer.com/article/10.1007/s10994-024-06585-0)

### Recommendations for Our 3-Tier System

1. **Build an auto-detection algorithm**: Compute a composite skill score from the telemetry metrics we already extract and use it as the DEFAULT skill level (user can override).
2. **Per-skill granularity**: Instead of one global skill level, track 6-8 individual skill dimensions and coach to the weakest one that's within ZPD.
3. **Dynamic adaptation**: If auto-detected skill level differs from user-declared level by 2+ tiers, show a gentle notification ("Based on your data, our coaching thinks you might be ready for intermediate-level tips. Would you like to try them?").

### Draft Coaching Language Examples

**Auto-detected novice (user didn't declare level):**
> "Welcome! Based on your session data, I've tailored this report for a driver who's building their foundations. Your line consistency and braking smoothness show you're making great progress. I'll focus on the 1-2 things that will make the biggest difference for your next session."

**Auto-detected intermediate (upgrading from novice):**
> "Your consistency metrics have improved significantly since your last session -- your brake point variance is down 40% and your lap times are much more repeatable. I've adjusted your coaching to include some more advanced concepts like trail braking. If any of this feels too technical, you can always adjust your skill level in settings."

**Per-skill detection:**
> "Your overall driving shows strong intermediate fundamentals, but I noticed two areas where more targeted coaching could help: (1) Your trail braking at Turn 3 and Turn 7 shows a pattern of abrupt release -- this is common for drivers transitioning from 'brake-then-turn' to trail braking. (2) Your throttle timing is actually quite advanced -- you're committing to throttle earlier than most intermediate drivers. Let's focus on smoothing out that trail brake release."

### Proposed Auto-Detection Algorithm

```python
def detect_skill_level(
    all_lap_corners: dict[int, list[Corner]],
    summaries: list[LapSummary],
) -> tuple[str, float, dict[str, str]]:
    """
    Auto-detect driver skill level from telemetry.

    Returns:
        (level, confidence, per_skill_levels)
        level: "novice", "intermediate", "advanced"
        confidence: 0.0-1.0
        per_skill_levels: {"braking": "intermediate", "trail_braking": "novice", ...}
    """
    scores = {}

    # 1. Lap time consistency
    lap_times = [s.lap_time_s for s in summaries]
    cv = stdev(lap_times) / mean(lap_times) if len(lap_times) >= 3 else 0.05
    if cv > 0.03:
        scores["consistency"] = "novice"
    elif cv > 0.015:
        scores["consistency"] = "intermediate"
    else:
        scores["consistency"] = "advanced"

    # 2. Brake point consistency (avg std dev across corners)
    brake_stds = []
    for corner_data in corners_by_number.values():
        pts = [c.brake_point_m for c in corner_data if c.brake_point_m is not None]
        if len(pts) >= 3:
            brake_stds.append(stdev(pts))
    avg_brake_std = mean(brake_stds) if brake_stds else 15.0
    if avg_brake_std > 12:
        scores["braking"] = "novice"
    elif avg_brake_std > 5:
        scores["braking"] = "intermediate"
    else:
        scores["braking"] = "advanced"

    # 3. Peak brake G utilization
    peak_gs = [c.peak_brake_g for c in all_corners if c.peak_brake_g]
    max_g = max(peak_gs) if peak_gs else 0.3
    if max_g < 0.5:
        scores["brake_pressure"] = "novice"
    elif max_g < 0.8:
        scores["brake_pressure"] = "intermediate"
    else:
        scores["brake_pressure"] = "advanced"

    # 4. Trail braking evidence
    trail_braking_pct = compute_trail_braking_fraction(all_lap_corners)
    if trail_braking_pct < 0.2:
        scores["trail_braking"] = "novice"
    elif trail_braking_pct < 0.6:
        scores["trail_braking"] = "intermediate"
    else:
        scores["trail_braking"] = "advanced"

    # 5. Throttle commit timing
    throttle_gaps = []
    for corner_data in corners_by_number.values():
        gaps = [c.throttle_commit_m - c.apex_distance_m
                for c in corner_data if c.throttle_commit_m]
        if gaps:
            throttle_gaps.append(mean(gaps))
    avg_throttle_gap = mean(throttle_gaps) if throttle_gaps else 25.0
    if avg_throttle_gap > 25:
        scores["throttle"] = "novice"
    elif avg_throttle_gap > 12:
        scores["throttle"] = "intermediate"
    else:
        scores["throttle"] = "advanced"

    # 6. Min speed optimization (variance across laps per corner)
    speed_stds = []
    for corner_data in corners_by_number.values():
        speeds = [c.min_speed_mps * MPS_TO_MPH for c in corner_data]
        if len(speeds) >= 3:
            speed_stds.append(stdev(speeds))
    avg_speed_std = mean(speed_stds) if speed_stds else 5.0
    if avg_speed_std > 4:
        scores["min_speed"] = "novice"
    elif avg_speed_std > 2:
        scores["min_speed"] = "intermediate"
    else:
        scores["min_speed"] = "advanced"

    # Composite scoring
    level_values = {"novice": 0, "intermediate": 1, "advanced": 2}
    avg_score = mean(level_values[v] for v in scores.values())

    if avg_score < 0.7:
        overall = "novice"
    elif avg_score < 1.5:
        overall = "intermediate"
    else:
        overall = "advanced"

    # Confidence based on agreement
    agreement = sum(1 for v in scores.values() if v == overall) / len(scores)

    return overall, agreement, scores
```

---

## Synthesis: Unified Adaptive Coaching Architecture

### The Problem with Our Current System

Our current coaching system (`coaching.py`) has three static prompt variants selected by user-declared skill level. The key limitations:

1. **Binary level assignment**: A driver is either "novice" or "intermediate" -- no per-skill granularity.
2. **No auto-detection**: Relies entirely on the user's self-assessment, which is often inaccurate.
3. **One coaching style**: Same format (data-heavy tables, explicit tips) regardless of motor learning stage.
4. **No external focus**: Tips are largely internal-focus ("brake harder," "apply throttle earlier").
5. **No implicit learning support**: No analogies, no feel-based cues, no pressure-robust coaching.
6. **No progression tracking**: Each session is analyzed in isolation with no memory of past performance.
7. **Fixed drill templates**: Same drill language regardless of skill level.

### The Proposed Architecture

```
                    +---------------------------+
                    |   Telemetry Data Input     |
                    +---------------------------+
                              |
                    +---------------------------+
                    |   Skill Auto-Detection     |
                    | (per-skill + composite)    |
                    +---------------------------+
                              |
                    +---------------------------+
                    |   Driver Archetype         |
                    | (per-corner classification)|
                    +---------------------------+
                              |
                    +---------------------------+
                    |   Motor Learning Stage     |
                    | (Fitts & Posner mapping)   |
                    +---------------------------+
                              |
                    +---------------------------+
                    |   Coaching Strategy Layer   |
                    | - External focus level      |
                    | - Implicit/explicit ratio   |
                    | - Tip count per corner      |
                    | - Analogy injection         |
                    | - KB snippet selection      |
                    +---------------------------+
                              |
                    +---------------------------+
                    |   Prompt Assembly           |
                    | (skill-aware, archetype-    |
                    |  aware, external-focus)     |
                    +---------------------------+
                              |
                    +---------------------------+
                    |   Claude Haiku 4.5 API      |
                    +---------------------------+
                              |
                    +---------------------------+
                    |   Coaching Report           |
                    | (personalized, scaffolded)  |
                    +---------------------------+
```

### The Five Layers of Personalization

**Layer 1: Skill Auto-Detection (Topic 6)**
- Computes per-skill levels from telemetry (6 dimensions)
- Produces a composite level with confidence score
- User-declared level serves as override, not default
- If auto-detection strongly disagrees with user declaration, surface a recommendation

**Layer 2: Driver Archetype Detection (Topic 2)**
- Per-corner archetype classification (early_braker, coaster, trail_brazer, etc.)
- Archetype-specific coaching tips replace generic advice
- Tracks archetype evolution across sessions

**Layer 3: Motor Learning Stage Mapping (Topic 5)**
- Maps composite skill level to Fitts & Posner stage
- Determines coaching STYLE (not just content): analogies vs. data, feel vs. numbers

**Layer 4: External Focus Calibration (Topic 3)**
- Selects external focus distance by stage: proximal (novice), mid-range (intermediate), distal (advanced)
- Adds external-focus translation rules to the prompt
- Injects analogy library for novice/intermediate (Topic 4)

**Layer 5: Cognitive Load Management (Topic 4)**
- Caps explicit tips per corner: 1 (novice), 2 (intermediate), 3-4 (advanced)
- Caps priority corners: 2 (novice), 3 (intermediate), 3+ (advanced)
- Caps total report complexity based on estimated cognitive capacity

### Concrete Changes to `coaching.py`

**1. Enhanced `_SKILL_PROMPTS`**

Replace the current flat text prompts with structured, research-backed coaching instructions:

```python
_SKILL_PROMPTS: dict[str, str] = {
    "novice": (
        "\n## Skill Level: Novice (Cognitive Stage / HPDE Group 1-2)\n"
        "This driver is in the COGNITIVE stage of motor learning.\n"
        "Their basic driving skills are NOT yet automatic -- they are still "
        "consciously thinking about every action.\n\n"
        "COACHING STRATEGY:\n"
        "- Maximum 1 tip per corner, maximum 2 priority corners\n"
        "- Use ANALOGY-based coaching (implicit learning) -- avoid explicit "
        "rules about body movements\n"
        "- Frame ALL tips with EXTERNAL FOCUS using PROXIMAL references "
        "(brake boards, nearby landmarks, curbing)\n"
        "- Focus on: line consistency, smooth inputs, basic braking\n"
        "- DO NOT discuss: trail braking, threshold braking, weight transfer, "
        "G-forces, or any advanced concept\n"
        "- Grade trail_braking as 'N/A' (not expected at this level)\n"
        "- Use encouraging language. Celebrate progress. The driver needs "
        "CONFIDENCE before technique.\n"
        "- Respect cognitive load: they can process ~1-2 new ideas per session\n\n"
        "ANALOGY LIBRARY (use these instead of technical explanations):\n"
        "- Braking: 'Squeeze a sponge' (progressive, not stomping)\n"
        "- Brake release: 'Lower a sleeping baby' (gentle, no jerk)\n"
        "- Throttle: 'Uncoil a spring' (smooth, progressive)\n"
        "- Steering: 'Stir soup without spilling' (smooth, no jerks)\n"
        "- Vision: 'Thread a needle with your eyes first'\n"
    ),
    "intermediate": (
        "\n## Skill Level: Intermediate (Associative Stage / HPDE Group 3)\n"
        "This driver is in the ASSOCIATIVE stage of motor learning.\n"
        "Basic skills are becoming automatic. They can now refine technique "
        "and understand WHY certain approaches work.\n\n"
        "COACHING STRATEGY:\n"
        "- Maximum 2 tips per corner, maximum 3 priority corners\n"
        "- Blend implicit and explicit coaching: use analogies for new "
        "concepts, data-specific feedback for refinement\n"
        "- Frame tips with EXTERNAL FOCUS using MID-RANGE references "
        "(apex trajectory, car behavior, how the corner feels)\n"
        "- Introduce: trail braking concepts, brake optimization, throttle "
        "timing, cause-and-effect explanations\n"
        "- Show all metrics but explain what they MEAN for car behavior\n"
        "- Compare best-vs-typical performance with specific numbers\n"
        "- Can process 2-3 new concepts per session\n\n"
        "TRANSITIONAL ANALOGIES (for new concepts):\n"
        "- Trail braking: 'Slowly open a spring-loaded door'\n"
        "- Weight transfer: 'A ball rolling in a bowl'\n"
        "- Use data to validate what they FELT: 'Remember that lap that "
        "felt great? Here's why...'\n"
    ),
    "advanced": (
        "\n## Skill Level: Advanced (Autonomous Stage / HPDE Group 4+)\n"
        "This driver is in the AUTONOMOUS stage of motor learning.\n"
        "Driving skills are automatic. They have capacity for strategic "
        "thinking and micro-optimization.\n\n"
        "COACHING STRATEGY:\n"
        "- Full technical detail: 3-4 points per corner as needed\n"
        "- Frame tips with EXTERNAL FOCUS using DISTAL references "
        "(exit point, following straight, overall trajectory)\n"
        "- Focus on: micro-optimization (tenths/hundredths), composite "
        "gaps, setup correlation hints, brake trace shape analysis\n"
        "- Challenge with specific measurable targets\n"
        "- Discuss: trail brake modulation, threshold percentage, weight "
        "transfer management, tire slip angle implications\n"
        "- IMPORTANT: Avoid giving explicit step-by-step instructions "
        "for automated skills -- this can cause 'reinvestment' and "
        "actually hurt performance under pressure\n"
        "- Frame challenges as problems to solve, not rules to follow\n"
        "- Can process 3-4 technical points per corner\n"
    ),
}
```

**2. New `_ARCHETYPE_COACHING` dictionary**

```python
_ARCHETYPE_COACHING: dict[str, dict[str, str]] = {
    "early_braker": {
        "novice": "You're braking well before the corner -- that's a safe foundation! "
                  "Try moving your brake point just one car length closer next session.",
        "intermediate": "Your brake point is {delta_m:.0f}m early. Move it 3m closer "
                       "each session until you feel the car's weight load the front tires "
                       "at turn-in.",
        "advanced": "Brake initiation is {delta_m:.0f}m conservative for your entry speed "
                   "of {{speed:{entry_speed}}}. Given your tire mu of {mu:.2f}, the "
                   "optimal point is {optimal_m:.0f}m before the apex.",
    },
    "coaster": {
        "novice": "After you release the brake, feel the car glide -- then gently add "
                  "throttle like uncoiling a spring. No rush!",
        "intermediate": "There's a {coast_m:.0f}m coast zone between brake release and "
                       "throttle. Trail the brakes into the turn-in to eliminate this gap -- "
                       "the car should always be either decelerating or accelerating.",
        "advanced": "Coast phase of {coast_m:.0f}m costs approximately {coast_time_s:.2f}s. "
                   "Your brake-to-throttle transition needs to be continuous. Target: zero "
                   "time at neutral load.",
    },
    # ... additional archetypes
}
```

**3. Cognitive Load Management**

```python
_COGNITIVE_LOAD_LIMITS: dict[str, dict[str, int]] = {
    "novice": {
        "tips_per_corner": 1,
        "priority_corners": 2,
        "total_drills": 1,
        "max_report_paragraphs": 4,
    },
    "intermediate": {
        "tips_per_corner": 2,
        "priority_corners": 3,
        "total_drills": 2,
        "max_report_paragraphs": 8,
    },
    "advanced": {
        "tips_per_corner": 4,
        "priority_corners": 3,
        "total_drills": 3,
        "max_report_paragraphs": 12,
    },
}
```

---

## Implementation Roadmap

### Phase 1: Enhanced Prompts (Low effort, high impact)
**Files to change:** `cataclysm/coaching.py`
- Replace `_SKILL_PROMPTS` with the research-backed versions above
- Add `EXTERNAL_FOCUS_INSTRUCTION` to the system prompt
- Add analogy library to the novice/intermediate prompts
- Add cognitive load limits to the prompt (tip counts, priority corner counts)
- Estimated effort: 2-3 hours

### Phase 2: Skill Auto-Detection (Medium effort, high impact)
**New file:** `cataclysm/skill_detection.py`
- Implement `detect_skill_level()` function using telemetry metrics
- Integrate into `generate_coaching_report()` as default when user hasn't declared
- Add per-skill breakdown to the report
- Wire into backend API (serve auto-detected level, allow override)
- Estimated effort: 4-6 hours

### Phase 3: Driver Archetype Detection (Medium effort, medium impact)
**New file:** `cataclysm/driver_archetypes.py`
- Implement per-corner archetype classification
- Add `_ARCHETYPE_COACHING` dictionary
- Inject archetype context into the coaching prompt
- Show archetype on the UI (per-corner label)
- Estimated effort: 4-6 hours

### Phase 4: Progression Tracking (Medium effort, high long-term impact)
**Changes:** `cataclysm/coaching.py`, backend storage
- Store per-session skill scores in the database
- Compute skill deltas between sessions
- Add progression insights to the coaching report
- Track archetype evolution per corner
- Estimated effort: 6-8 hours

### Phase 5: Scaffolded Drill System (Low effort, medium impact)
**Changes:** `cataclysm/coaching.py`
- Create 3 variants of each drill template (one per skill level)
- Add analogy-based drills for novice level
- Add measurable-target drills for advanced level
- Estimated effort: 2-3 hours

### Priority Order
1. Phase 1 (prompts) -- biggest bang for the buck, pure prompt engineering
2. Phase 2 (auto-detection) -- enables personalization without user input
3. Phase 5 (drills) -- quick win after Phase 1
4. Phase 3 (archetypes) -- deepens personalization
5. Phase 4 (progression) -- requires storage infrastructure

---

## Appendix: Key Research Sources Summary

| Source | Topic | Key Finding | Year |
|--------|-------|-------------|------|
| Chua, Diaz, Lewthwaite, Kim, & Wulf | External Focus Meta-Analysis | External focus superior for both performance and learning, independent of age/expertise | 2021 |
| Wulf & Lewthwaite | OPTIMAL Theory | External focus + enhanced expectancies + autonomy support = optimal motor learning | 2016 |
| Wulf et al. | Distance Effect | More distal external focus = better performance | 2003 |
| Hojaji, Toth, Joyce, Campbell | Sim Racing AI Classification | 97.19% accuracy classifying driver performance from telemetry features | 2023-2024 |
| Masters | Reinvestment Theory | Explicit knowledge disrupts automatized performance under stress | 1992 |
| Liao & Masters | Analogy Learning | Analogy coaching produces implicit learning resistant to pressure | 2001 |
| Fitts & Posner | Motor Learning Stages | Cognitive -> Associative -> Autonomous progression | 1967 |
| Dreyfus & Dreyfus | Skill Acquisition Model | Novice -> Advanced Beginner -> Competent -> Proficient -> Expert | 1988 |
| Sweller | Cognitive Load Theory | Working memory capacity ~4 items; instructional design should minimize load | 1988 |
| Miller | Working Memory | "Magical number 7 plus or minus 2" (revised to ~4) | 1956 |
| Various | Brake Trace Analysis | Pro drivers show <3% brake pressure variation; novices show >15% | 2020-2025 |
| Frontiers in Psychology | Implicit Learning Under Fatigue | Implicitly learned skills resilient under fatigue and pressure | 2025 |
| Tandfonline | Scaffolding Athlete Learning | Movement consistency triggers progression to harder training | 2021 |

---

*This research document informs the adaptive coaching architecture for the Cataclysm platform. All recommendations are grounded in published motor learning science and motorsport coaching practice.*
