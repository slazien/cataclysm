# Cataclysm Vision Document

**Date:** 2026-03-05
**Status:** Approved
**Type:** Internal north-star for prioritization and architectural decisions
**Horizons:** Near-term (0-3mo), Mid-term (3-12mo), Long-term (1-3yr)

---

## Tagline

**"Your fastest lap is next."**

## Mission

Democratize motorsport coaching — make data-driven, personalized instruction available to every driver, not just the ones who can afford a pro coach.

---

## The Problem

Getting faster on track requires either expensive 1-on-1 coaching ($200-400/session with Blayze, $1,700+ trackside), or spending hours learning to interpret telemetry yourself. Most drivers have limited track time — maybe one event a month — and burning that time staring at speed traces instead of driving means fewer laps and slower progress.

Anyone *can* learn to read telemetry data given enough time. But track day drivers don't have enough time. They have day jobs, families, and a handful of weekends a year on track. The gap isn't intelligence — it's bandwidth. The data is there, but the hours to make sense of it aren't.

Between events — often weeks or months apart — there's no continuity. No preparation, no memory of what you were working on, no feedback loop. Every session risks feeling like starting over.

---

## The Solution

**Cataclysm is an AI driving coach that turns your telemetry into actionable coaching — instantly.** Upload your data, and within seconds get a personalized coaching report: where you're losing time, what to change, and why — grounded in established coaching methodology from Ross Bentley, Allen Berg, and professional driving instruction.

**Today:** Post-session analysis that does in seconds what takes hours with traditional tools. Corner-by-corner grades, time-gain breakdowns, driving line consistency analysis, progress tracking across sessions, and an AI chat that answers follow-up questions with your data as context.

**Tomorrow:** A real-time AI coach in your ear. Brake point beeps as you approach a corner. Voice coaching through your helmet bluetooth — "tighter entry on the next one, you're leaving half a second on the table at Turn 5." Pre-session briefings that remind you what to focus on. Post-session dopamine hits that show exactly how much you improved.

**The flywheel:** Better coaching -> faster laps -> share your results -> friends join -> more data -> smarter coaching.

---

## Target Users (Concentric Circles)

**Circle 1 — Solo track day drivers (now)**
HPDE participants and enthusiasts with a GPS data logger (RaceBox, Garmin, phone GPS). They do 5-20 track days a year, want to get faster, and don't have a personal coach. This is the beachhead — every feature must serve this user first.

**Circle 2 — Instructors and coaches (mid-term)**
HPDE instructors who work with 3-5 students per event. They want to give data-backed feedback without spending hours in Race Studio. Cataclysm becomes the tool they hand to students: "upload your data here, I'll review your report tonight." Instructor dashboards, multi-student views, shared annotations.

**Circle 3 — Teams and organizations (long-term)**
Club racing teams, arrive-and-drive series, track day organizations. Multi-driver analysis, team leaderboards, event management. The organization features and instructor roles already in the codebase are the seeds of this.

---

## Core Differentiators

### 1. AI coaching, not just charts
Competitors give you data. Cataclysm tells you what to do with it. The gap between "here's your speed trace" and "brake 10 meters later at Turn 5 and you'll gain 0.3s" is the entire product.

### 2. Instant understanding
A driver with zero telemetry experience uploads a CSV and gets a coaching report they can act on immediately. No learning curve. MoTeC i2 is powerful — and takes months to learn. Cataclysm takes seconds.

### 3. Full loop, one tool
Upload -> analysis -> coaching -> progress tracking -> sharing -> preparation for next session. Competitors do pieces. RaceChrono captures data. Blayze provides coaching. Strava tracks progress. Cataclysm does the whole loop.

### 4. Trust through transparency
Every coaching recommendation links back to the data — "you braked 12m early at Turn 5, here's the speed trace." Advice is grounded in established methodology (Allen Berg corner types, Ross Bentley principles). The AI shows its work, not just its conclusions.

### 5. Gets smarter with you
Cross-session progress tracking spots patterns a single session can't reveal. The AI learns your driving over time — not just "you were slow in Turn 5 today" but "you've been early-apexing Turn 5 for three sessions and it's costing you 0.4s each time."

### 6. A coach that never forgets
At HPDE events, you get a different instructor each time. They don't know your history, your car, your habits. Cataclysm remembers every session, every corner, every mistake and breakthrough. It knows you braked late at Turn 3 six months ago and fixed it by March. No warmup, no re-explaining — your AI coach picks up exactly where you left off.

---

## Product Roadmap (Three Horizons)

### Near-term (0-3 months): Nail the core loop

- **Onboarding overhaul** — first session to "wow" in under 60 seconds. Upload CSV, see coaching report, understand what to change. Zero friction.
- **Universal ingestion** — adapter architecture for RaceBox direct, TrackAddict, Harry's LapTimer, AiM CSV. Every new format unlocks a new user segment.
- **Mobile-first experience** — track day drivers are in the paddock on their phones. The core analysis and coaching flow must work beautifully on mobile.
- **Retention foundations** — pre-session briefings ("here's what to focus on at Barber based on your last 3 visits"), goal setting before each event, post-session improvement summaries.
- **Monetization launch** — 3 full sessions free with complete functionality. Then tiered subscriptions.

### Mid-term (3-12 months): Build the moat

- **Multi-session intelligence** — pattern recognition across sessions. "You've improved braking at Type A corners by 15% over 6 sessions, but Type C corners are stagnating."
- **Instructor tools** — instructor dashboards, student management, shared session reviews. Make Cataclysm the tool instructors hand to students.
- **Training content engine** — personalized drills and educational content tied to your specific weaknesses. "Your trail braking needs work -> here's what to practice."
- **Community & social** — track-day leaderboards, improvement rankings, share cards that make friends jealous. The atomic social unit is the track day event.
- **Trust layer** — coaching citations linking to methodology sources, progress-over-time proof that the advice works.

### Long-term (1-3 years): Real-time AI coach

- **Real-time audio coaching** — brake point beeps, synthesized voice coaching through helmet bluetooth. "Tighter entry next corner." Adapts in real-time to your driving.
- **Conversational in-car AI** — talk to your coach between sessions or on cool-down laps. "What should I focus on for the next stint?"
- **Organization platform** — track day event management, team analytics, arrive-and-drive series integration.
- **Hardware partnerships** — integration with data logger manufacturers, potential co-branded hardware.
- **Data moat** — millions of laps across hundreds of tracks create a coaching intelligence that no competitor can replicate from scratch.

---

## Monetization

### Model: Freemium with tiered subscriptions

**Free trial — 3 full sessions, no feature gates.**
New users get the complete Cataclysm experience for their first 3 sessions. Full AI coaching, progress tracking, sharing — everything. This is critical: the "aha moment" must happen before any paywall. A crippled free tier teaches users that Cataclysm is mediocre; a full-power trial teaches them it's indispensable.

**After trial — tiered subscriptions:**
- **Free** — basic upload + lap times. Useful, but missing the magic.
- **Pro** — full AI coaching, chat, progress tracking, sharing, pre-session briefings. The core product.
- **Coach** — Pro + multi-student dashboard, student management, shared reviews.
- **Team** — Coach + org management, team analytics, API access.

**Pricing TBD** — requires competitive deep-dive, willingness-to-pay research, and iteration. Key reference points: Track Titan ($8-20/mo), Blayze ($100-300/session), Garmin Vault ($10/mo). The hobby context ($300-2,000/track day) suggests significant pricing headroom.

---

## Retention & Engagement Loop

### The between-events problem
Track days happen every 2-6 weeks. Most telemetry tools go dormant between events. Cataclysm must give drivers a reason to come back.

### Five pillars of between-event engagement

**1. Preparation**
Before your next event, Cataclysm surfaces a pre-session briefing: your last performance at this track, what you were working on, 2-3 focus areas for the day. For new tracks, a novice-friendly track introduction — the digital equivalent of the HPDE classroom session.

**2. Education**
Personalized training content tied to your weaknesses. "Your trail braking drops off too early — here's why that costs you time and what to practice." Not generic YouTube videos — content selected because the AI identified a specific gap in your driving.

**3. Community**
Leaderboard updates, improvement rankings, seeing what friends did at the same track. Share cards designed for Instagram/WhatsApp that make your PB feel like an achievement worth celebrating. The atomic social unit is the track day event, not a global feed.

**4. Goals & accountability**
Set targets before your next session: "brake 5m later at Turn 5", "hit 95% consistency in the esses." Get reminded the morning of your track day. After the session, see exactly whether you hit them. The dopamine loop: set goal -> drive -> see result -> share -> set next goal.

**5. Exclusive content**
Original content that only Cataclysm users get access to. In-depth track guides with corner-by-corner strategy (not just a track map — actual coaching on each section). Video breakdowns. Live Q&A sessions with pro drivers or HPDE instructors. This content doubles as a trust builder — when a pro driver validates the same advice the AI gave you, confidence in the platform skyrockets. Also creates marketing fuel: "Join this Thursday's live session with [instructor] breaking down Barber Motorsports Park."

---

## Trust & Credibility Strategy

### The trust ladder
Drivers won't change their braking point because an app told them to — not until they trust it. Trust is built in layers:

**Layer 1: Show your work (day one)**
Every coaching recommendation links to the specific data point. "Brake 10m later at Turn 5" comes with the speed trace, the comparison to your best lap, the exact distance marker. The driver can verify every claim. No black-box pronouncements.

**Layer 2: Speak the language of real coaching (day one)**
Coaching advice is grounded in established methodology — Allen Berg corner types, Ross Bentley's "Ultimate Speed Secrets" principles, trail braking physics. When the AI says something, it's saying what a great human coach would say, because it's built on the same foundation. Cite the methodology where appropriate.

**Layer 3: Prove it with results (over time)**
Progress tracking is the ultimate trust builder. "The AI told you to brake later at Turn 5. You did. You gained 0.3s. Here's the proof." After a few sessions of this, drivers stop questioning the advice and start acting on it immediately. The data speaks louder than any endorsement.

**Layer 4: Instructor validation (earned)**
Once the product has proven itself through data, instructors will notice their students improving. Instructor endorsement comes as a *consequence* of a great product, not as a marketing tactic. The Coach tier accelerates this — instructors using Cataclysm with students see the results firsthand.

---

## Competitive Landscape

### Where Cataclysm sits

| | Data capture | Post-session analysis | AI coaching | Real-time coaching | Progress tracking | Social |
|---|---|---|---|---|---|---|
| **RaceChrono / Harry's** | Yes | Basic | No | No | No | No |
| **AiM / MoTeC** | Yes (pro hardware) | Deep but complex | No | No | No | No |
| **Garmin Catalyst** | Yes (hardware) | Moderate | No | Beeps + optimal lap | No | No |
| **Track Titan** | Sim only | Yes | Yes (sim) | No | Yes | Yes |
| **Blayze** | No (user provides video) | Human coach | Human coach | No | No | No |
| **Cataclysm (today)** | No (import) | Yes | Yes | No | Yes | Yes |
| **Cataclysm (vision)** | Universal import | Yes | Yes | Yes (AI voice + beeps) | Yes | Yes |

### Key competitive dynamics

- **Track Titan is the closest comp** — AI coaching via SaaS subscription, $5M raised, 200K+ users. Currently sim-first with stated ambitions to serve real-world drivers. Whether and when they execute on that is unclear, but the overlap in vision makes them worth watching.
- **Garmin Catalyst owns real-time today** — but it's hardware-locked ($1,200), dumb (pre-computed optimal lap, no personalization), and has no coaching intelligence. The real-time gap is Cataclysm's long-term opportunity.
- **Blayze validates willingness to pay for coaching** ($100-300/session) — Cataclysm offers similar value at a fraction of the cost, with instant delivery and unlimited access.
- **Data capture tools (RaceChrono, AiM) are partners, not competitors.** Cataclysm sits downstream — the more data sources it ingests, the more users it serves.
- **The moat is coaching intelligence.** Raw telemetry analysis is commoditizable. Knowing what to tell a specific driver based on their history, skill level, car, and the track — that's the defensible asset.

---

## Key Risks & Open Questions

### Risks

**1. Real-time coaching is hard.**
Latency, reliability, phone GPS accuracy in real-time, bluetooth audio sync, safety liability if advice is wrong at 120mph. This is a multi-year engineering challenge with no shortcut. Mitigation: build the intelligence layer now (post-session), so when the real-time delivery mechanism is ready, the coaching brain already exists.

**2. Track Titan gets to real-world first.**
They have $5M, 200K users, and stated ambitions for real-world drivers. If they nail real-world coaching before Cataclysm reaches critical mass, it's a race for market share. Mitigation: Cataclysm's real-world-first DNA means deeper domain expertise in actual telemetry — sim data is cleaner and simpler than noisy GPS data from a bumpy track.

**3. AI coaching trust ceiling.**
Some drivers may never trust AI advice over a human. Mitigation: the trust ladder (show work -> prove results -> earn instructor validation). The Coach tier turns skeptical instructors into allies.

**4. Retention between events.**
If the five engagement pillars don't work, Cataclysm becomes a tool people open 12 times a year. Mitigation: measure retention aggressively from day one. Kill what doesn't work, double down on what does.

**5. Data source fragmentation.**
Every logger has its own format, quirks, and edge cases. Universal ingestion is a never-ending maintenance burden. Mitigation: adapter architecture with community contributions. Prioritize formats by user demand, not completeness.

### Open questions

- **Pricing:** Needs dedicated research, A/B testing, willingness-to-pay interviews.
- **Real-time MVP:** What's the simplest version of in-car coaching that delivers value? Beeps only? Voice? Which hardware requirements?
- **Content strategy:** Build original content in-house, or partner with existing creators (Driver61, Blayze coaches, HPDE orgs)?
- **Mobile app vs. mobile web:** Is a native app required for real-time coaching, or can the post-session product stay web-only?
- **Data privacy:** Drivers' telemetry is sensitive competitive data. What's the privacy stance? How is data used for product improvement?

---

## Appendix: Competitive Pricing Research

Research conducted 2026-03-05. Key reference points:

| Product | Model | Price range |
|---------|-------|-------------|
| Harry's LapTimer | One-time purchase | $9-50 |
| TrackAddict | Freemium + one-time | Free / $7-10 |
| RaceChrono Pro | One-time purchase | $19 |
| Apex Pro | Hardware + subscription | $589 hardware + $99/yr |
| Garmin Catalyst 2 | Hardware + subscription | $1,200 hardware + $10/mo cloud |
| AiM Solo 2 DL | Hardware, free software | $900+ hardware |
| Track Titan | Freemium SaaS | Free / $8-20/mo |
| Blayze | Credit-based marketplace | $100-300/coaching session |

Key insight: Track day drivers spend $500-2,000 per event. A $10-20/mo subscription is a rounding error in that budget. AI coaching is the monetization sweet spot — the gap between "here's your data" (commoditized) and "here's what to do about it" (where users pay).

Sources: Track Titan (tracktitan.io), Blayze (blayze.io), Garmin (garmin.com), Apex Pro (apextrackcoach.com), Harry's LapTimer (gps-laptimer.de), RaceChrono (racechrono.com), AiM (aim-sportline.com).
