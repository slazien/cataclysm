# Competitive & UX Analysis: Motorsport Telemetry Landscape

**Date:** 2026-02-23
**Purpose:** Comprehensive competitive intelligence and UX research to inform Cataclysm's UI redesign for novice-to-advanced US HPDE drivers.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Target Audience: HPDE Driver Personas](#2-target-audience-hpde-driver-personas)
3. [Competitive Landscape Matrix](#3-competitive-landscape-matrix)
4. [Competitor Deep Dives](#4-competitor-deep-dives)
   - 4.1 Phone Apps (RaceChrono, Harry's LapTimer, TrackAddict)
   - 4.2 Pro Telemetry (AiM Race Studio, MoTeC i2, Cosworth Pi Toolbox)
   - 4.3 Coaching Devices (Garmin Catalyst, APEX Pro, Porsche PTPA)
   - 4.4 Software/SaaS (Track Titan, VRS, Blayze, Track Attack)
5. [Common UI/UX Patterns in Telemetry Software](#5-common-uiux-patterns-in-telemetry-software)
6. [UX Best Practices for Data Dashboards](#6-ux-best-practices-for-data-dashboards)
7. [AI Coaching: What Works](#7-ai-coaching-what-works)
8. [Market Gap Analysis](#8-market-gap-analysis)
9. [Design Recommendations for Cataclysm](#9-design-recommendations-for-cataclysm)
10. [Sources](#10-sources)

---

## 1. Executive Summary

### The Core Problem

Most HPDE drivers collect telemetry data but **never analyze it**. The funnel is broken at interpretation — tools show *what happened* but not *why* or *what to do differently*. AiM Race Studio requires a laptop and hours of learning. Phone apps give lap times but no coaching. Garmin Catalyst provides coaching but costs $1,200 and has shallow analysis.

### The Market Opportunity

- **Racing telemetry market**: $579.5M (2025) → $1,489.5M by 2035 (9.9% CAGR)
- **Private equity invested $210M+** in motorsport analytics startups in 2023
- **Track Titan** (sim-first AI coaching) raised **$5M seed** in Dec 2025 with 200K+ users
- **Cloud-based storage** now used by 47% of racing operations
- **No web-based, hardware-agnostic AI coaching tool exists for real-world track driving**

### Where Cataclysm Fits

Cataclysm fills the intersection of three unserved gaps:

```
                    ┌─────────────────────┐
                    │  AI COACHING         │
                    │  (Track Titan,       │
                    │   Garmin Catalyst)   │
                    └────────┬────────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
   ┌──────────▼───┐  ┌──────▼──────┐  ┌───▼──────────┐
   │ REAL-WORLD   │  │ CATACLYSM   │  │ WEB-BASED    │
   │ TRACK DATA   │  │ (fills all  │  │ ANALYSIS     │
   │ (RaceChrono, │  │  3 gaps)    │  │ (none exist  │
   │  AiM, etc.)  │  └─────────────┘  │  for real    │
   └──────────────┘                    │  driving)    │
                                       └──────────────┘
```

**Key stat**: A driver spending $1,500/day on track time is not price-sensitive to a $10-30/month tool that extracts measurable improvement. The cost of NOT improving (wasted track time) is the real pain.

---

## 2. Target Audience: HPDE Driver Personas

### Demographics (US)

- **Age**: 30s-50s core, 18-34 overrepresented online
- **Gender**: ~66% male
- **Education**: 70% some college, 24% bachelor's/master's
- **Income**: $72K-$100K+ household (varies by car platform)
- **Tech profile**: Comfortable with apps and GPS devices; impatient with complex desktop software; want "it just works"
- **Spending**: $1,500/event typical; $5-$1,200 on timing/data technology
- **Organizations**: NASA, SCCA, PCA, BMW CCA, regional clubs

### Persona Breakdown by Run Group

| Dimension | Group 1-2 (Novice) | Group 3 (Intermediate) | Group 4 (Advanced) |
|-----------|-------------------|----------------------|-------------------|
| **Track days/year** | 2-8 | 8-20 | 15-30+ |
| **Primary need** | "Am I improving?" | "Where am I losing time?" | "How do I find the last tenths?" |
| **Data literacy** | Cannot read speed traces | Can compare two laps | Can correlate multi-channel data |
| **Tool today** | Phone app or nothing | RaceChrono + Garmin Catalyst | AiM Solo 2 + Race Studio |
| **What overwhelms them** | Any raw telemetry | 30+ channels without guidance | Nothing — but time is scarce |
| **Ideal output** | Session score + "you improved" | Top 3 corner priorities with context | Detailed KPIs with multi-session trends |
| **Coaching style** | Directive ("brake at the 3 board") | Contextual ("you braked 15m early in T5") | Comparative ("T5 entry speed 2mph below your PR") |
| **Willingness to pay** | Low ($0-10/mo) | Medium ($10-20/mo) | High ($20-40/mo) |

### What They All Share

1. **Time-poor at the track** — 5-15 min between sessions to analyze
2. **Want actionable insight, not raw data** — "tell me what to do differently"
3. **Celebrate improvement** — personal bests and progress matter enormously
4. **Social comparison** — want to compare with friends, instructors, benchmarks
5. **Async coaching is acceptable** — don't need real-time, post-session is fine

---

## 3. Competitive Landscape Matrix

### Full Comparison

| Product | Type | Price | AI Coaching | Corner Analysis | Trends | Web-Based | Real-World Data | Learning Curve |
|---------|------|-------|-------------|-----------------|--------|-----------|-----------------|----------------|
| **Cataclysm** | Web app | TBD | Yes (Claude) | Yes (auto-detect) | Yes | Yes | Yes (CSV) | Low |
| RaceChrono Pro | Phone app | $20 | No | No | No | No | Yes | Low-Med |
| Harry's LapTimer | Phone app | $9-28 | No | No | No | No | Yes | High |
| TrackAddict | Phone app | Free-$20 | No | No | No | No | Yes | Medium |
| AiM Race Studio 3 | Desktop | Free* | No | Manual splits | Limited | No | Yes (hardware) | High |
| MoTeC i2 | Desktop | Free-$939/yr* | No | Manual | Limited | No | Yes (hardware) | Very High |
| Garmin Catalyst | Device | $1,200 | Rudimentary | No | Basic | No | Yes | Very Low |
| APEX Pro | Device | $489 | Grip model | No | No | No | Yes | Low |
| Porsche PTPA | Phone app | Free** | Basic | No | Yes | No | Yes (Porsche only) | Low |
| Track Titan | Web/app | $0-20/mo | Yes | Yes | Yes | Yes | No (sim only) | Low |
| VRS | Web | Subscription | Yes | Yes | Yes | Yes | No (sim only) | Low |
| Blayze | Service | $8-10/session | Human | Verbal | No | Web portal | Yes (video) | Very Low |
| Track Attack | Web | Free-paid | No | Segments | Limited | Yes | No (sim mainly) | Medium |

*\*Requires proprietary hardware ($800-$7,500)*
*\*\*Requires Porsche with Sport Chrono*

### Key Insight: Nobody Does All Three

No product combines (1) real-world track data, (2) AI coaching, and (3) web-based accessibility. Every competitor is missing at least one pillar.

---

## 4. Competitor Deep Dives

### 4.1 Phone Apps

#### RaceChrono Pro — The Data Collection Standard

**What Cataclysm's users already use.** RaceChrono is the most popular phone-based telemetry recorder among US HPDE drivers.

- **Strengths**: Best-in-class analysis for a phone app (speed trace overlays, delta-T, g-g plots, synchronized video), broadest hardware ecosystem (GPS, OBD2, CAN bus, GoPro), one-time $20 purchase, rock-solid reliability
- **Weaknesses**: UI is its #1 complaint ("5 stars for features, 1 for UI"), no corner detection, no coaching, no cross-session trends, no cloud platform, controls too small for gloved use
- **UX Pattern**: Functional/utilitarian, synchronized scrolling panels (graph + map + video), dark theme
- **Users**: 100K+ active across iOS/Android
- **Export**: CSV v3 (what Cataclysm ingests), VBO, NMEA, ODS
- **Relevance**: Cataclysm's primary data source. The typical workflow is: record in RaceChrono → quick analysis on phone at track → export CSV → deeper analysis in Cataclysm at home

#### Harry's LapTimer — Feature-Rich but Complex

- **Strengths**: Most comprehensive feature set among phone apps (video overlay, multi-cam, online racing, 1,300+ tracks), track map with color-coded g-force overlay is "universally praised" (Grassroots Motorsports), 15+ years of development, $9-28 one-time
- **Weaknesses**: Steep learning curve ("over complicated, counterintuitive"), video workflow is fragile and frustrating, no coaching/interpretation, no corner analysis, no trend tracking
- **UX Pattern**: Engineering-focused, data-dense, hierarchical navigation
- **Key Quote**: "You are on your own to export and run through something like Circuit Tools to find improvement" — this is precisely the gap Cataclysm fills

#### TrackAddict — Video-First Budget Option

- **Strengths**: Free tier, good video overlay via RaceRender, HP Tuners backing, refreshed UI (Feb 2025), supports autocross/rally/drift/drag
- **Weaknesses**: Phone GPS accuracy ("hot laggy garbage"), OBD2 connectivity issues, no desktop analysis, no coaching
- **UX Pattern**: Streamlined home screen, mobile-optimized, reduced clutter

### 4.2 Professional Telemetry Software

#### AiM Race Studio 3 — Club Racing Standard

**The tool Cataclysm doesn't need to replicate but should respect.**

- **UI Layout**: Channel list (left) + Time-Distance graph (center) + Track Map + Video + StoryBoard (lap selector). Vertically stacked traces with synchronized cursor across all panels
- **Key Features**: 12+ layout types, math channels, 4,000+ pre-loaded tracks, SmartyCam video integration, up to 7 lap overlay
- **What Makes It the Standard**: Free software, broad hardware ecosystem ($800-$2,900), adequate for 90%+ of club needs
- **Weaknesses**: Windows-only, no mobile app, poor documentation, sluggish cursor, RS2→RS3 migration frustrates users, buggy track mapping
- **Learning Curve**: High — most users exploit <10% of capabilities
- **Relevance**: Sets the UI expectations for "serious" telemetry analysis. Cataclysm should feel modern compared to RS3's 2010s-era interface

#### MoTeC i2 Pro — The Gold Standard

- **UI Layout**: Project > Workbook > Worksheet hierarchy, customizable panels, dual cursors with automatic differential calculation
- **Key Features**: Time Variance Plot (F3), "rainbow track map" showing gain/loss as color gradient, on-demand math calculation, unlimited worksheets/components (Pro)
- **Strengths**: Most powerful analysis engine, best documentation and support among pro tools, used at the highest levels (F1, IndyCar, WEC)
- **Weaknesses**: Very steep learning curve, expensive hardware ($1,770-$7,510), Pro license $500-$939/yr
- **Key Design Pattern**: The "rainbow track map" — showing the derivative of time variance mapped as a color gradient onto the circuit outline — is the most intuitive gain/loss visualization in any telemetry tool

#### Cosworth Pi Toolbox — F1-Grade (Aspirational Only)

- **20+ display types**, SDK-extensible, real-time telemetry support
- **New subscription model**: Free (Lite) to $600/yr (Ultra) for iRacing
- **Not relevant for HPDE** — "not geared to a club racing audience," minimal amateur support
- **Relevance**: Represents the ceiling of what's possible; useful for UI inspiration only

### 4.3 Coaching Devices

#### Garmin Catalyst — The UX Gold Standard for HPDE

**The product Cataclysm should study most carefully for UX principles.**

- **Price**: $999 (original) / $1,199 (Catalyst 2, Feb 2026)
- **Core Innovation**: "True Optimal Lap" — physically possible composite of your best segments (not just fastest sector times added up)
- **Coaching**: Audio cues after 3 laps ("brake later," "turn in earlier"), auto-identifies top 3 improvement opportunities, affirmation ("good job")
- **UX Philosophy**: No squiggly lines. No laptop. No configuration. Auto-starts at 30mph. Shows actionable opportunities, not raw data
- **Endorsement**: Ross Bentley (former pro driver, Speed Secrets founder) found 0.9 seconds after focusing on Catalyst's 3 identified opportunities
- **Strengths**: Zero-friction setup, instant post-session review on device, consistent user praise ("best thing I've purchased for dropping lap times")
- **Weaknesses**: Coaching is **generic and rudimentary** for intermediate+ drivers ("brake later" lacks specificity), no tire degradation awareness, no OBD2 data, limited data export, Catalyst 2 has only 45-min battery + subscription model for cloud video
- **Target**: Novice-to-intermediate HPDE — explicitly fills the gap when the instructor leaves the right seat

#### APEX Pro — Grip-Based Visual Coaching

- **Price**: $489
- **How It Works**: 12 RGB LEDs show grip margin in real-time. Green = near the limit (good), Red = unused potential (push harder). Built-in 9-axis IMU + 10Hz GPS builds a car-specific grip model over 1-2 laps
- **Key Insight**: Reframing data as "potential you're leaving on the table" (red lights) instead of "things you're doing wrong" is psychologically powerful
- **Companion App**: Speed traces, scatter plots, lap replay with animated dots, live telemetry streaming for trackside coaching
- **Strengths**: Small/portable, 6+ hour battery, fast setup, excellent build quality, automatic track recognition
- **Weaknesses**: LEDs hard to monitor during active driving, requires phone for data logging, no coaching advice (just grip indicators)
- **Target**: Intermediate club racers who have seat-of-pants feel and want data to confirm/guide it

#### Porsche Track Precision App — OEM Advantage

- **Price**: Free (requires Sport Chrono Package)
- **Killer Feature**: Reads **30+ channels directly from vehicle ECU** — brake pressure in PSI, steering angle, throttle position, traction control state, slip angles. No aftermarket tool can match this
- **Performance Coach**: Auto-evaluates laps, provides tips on braking points and turn-in
- **Weaknesses**: Porsche-only, phone overheating after 2-3 sessions, basic coaching depth
- **Relevance**: Shows the value of having rich telemetry + coaching together in one place

### 4.4 Software/SaaS Platforms

#### Track Titan — The Closest Competitor (Sim-First)

- **Users**: 200,000+, $5M seed funding (Dec 2025)
- **Vision**: "Strava for Motorsport" — social + AI coaching + telemetry
- **AI Features**: "Coaching Flows" guide through biggest mistakes, turn-by-turn analysis, personalized insights vs. pro reference laps
- **Pricing**: Free (unlimited laps) → $7.99/mo (AI tips) → $16.99/mo (instructor coaching) → $19.99/mo (pro setups)
- **Sims**: iRacing, ACC, Assetto Corsa, F1, Forza
- **Real-world**: Professional teams integrating for off-track training
- **Relevance**: Validates the AI coaching + telemetry market with $5M in funding. But sim-only — no real-world CSV import

#### VRS (Virtual Racing School) — "Designed for Drivers, Not Engineers"

- **Philosophy**: Continuously simplified UI; auto-highlights biggest improvement opportunities; lap comparison against pro reference laps
- **AI**: Analyzes telemetry + historical patterns, develops individualized improvement programs
- **Relevance**: Their design philosophy is what Cataclysm should emulate for real-world data

#### Blayze — Human Coaching at Scale

- **Model**: Upload video → receive coaching from professional driver ($8-10/session)
- **SCCA's official coaching partner**
- **Results**: Users report 3-5 second improvements in 2 sessions
- **Relevance**: Proves async coaching is acceptable; conversational coaching language works; low barrier to entry matters

---

## 5. Common UI/UX Patterns in Telemetry Software

### The Standard Analysis Layout

All professional tools converge on this layout:

```
┌──────────────┬────────────────────────────────────────────┐
│ Channel List │                                            │
│ (left)       │   Speed Trace          ───────────────     │
│              │   Throttle/Brake       ───────────────     │
│ - Speed      │   Lateral G            ───────────────     │
│ - Throttle % │   Delta-T              ───────────────     │
│ - Brake      │                                            │
│ - Steering   │         X-axis: DISTANCE (meters)          │
│ - Lat G      │                    ↕ cursor                │
│ - Long G     ├────────────────────┬───────────────────────┤
│ - RPM        │ Track Map          │ Lap List / Selector   │
│ - Gear       │ (color-coded)      │                       │
└──────────────┴────────────────────┴───────────────────────┘
```

### Universal Conventions

| Convention | Details |
|-----------|---------|
| **X-axis** | Distance, not time. Allows spatial comparison regardless of speed differences |
| **Speed trace position** | Top or most prominent — "the ultimate judge of performance" |
| **Channel stacking** | Vertically stacked with synchronized cursor across all panels |
| **Color: brake** | **Red** (universal across all platforms) |
| **Color: throttle** | **Green** (universal across all platforms) |
| **Color: gaining time** | Green/blue shades |
| **Color: losing time** | Red/orange shades |
| **Color: personal best** | Purple (F1 convention, widely adopted) |
| **Delta-T** | Visually emphasized — "defines the utility of the entire display" |
| **Track map** | Color-gradient overlay showing channel value mapped onto circuit outline |
| **Lap overlay** | Each lap gets a distinct color, consistent across all panels |
| **Dual cursors** | Two independent cursors for measuring delta between any two points |

### What "Good" Telemetry UI Looks Like (Professional Consensus)

1. Distance-based X-axis for meaningful spatial comparison
2. Vertically stacked, synchronized traces with a linked cursor
3. Prominent Delta-T trace — the first chart you see
4. Top-to-bottom hierarchy: Speed → Driver inputs → Derived channels → Vehicle channels
5. Track map colored by performance data (not just a static outline)
6. Multi-lap overlay with clear, consistent color coding
7. Customizable layouts for different analysis tasks
8. On-demand math channels (computed when viewed, not on load)
9. Split/segment awareness with per-segment statistics
10. Responsive cursor tracking (sluggish cursor breaks analysis flow)

---

## 6. UX Best Practices for Data Dashboards

### Progressive Disclosure — The #1 Pattern

> "Designs that go beyond two disclosure levels typically have low usability."

- Reduces error rates by **89%**
- Cuts cognitive load by **40%**
- Increases user involvement by **24%**

**For Cataclysm:**
- **Level 1**: Session summary — best lap, session score, top 3 AI coaching insights, lap time chart
- **Level 2**: Detailed analysis — corner-by-corner breakdown, speed traces, track maps, delta-T, full coaching report

### Information Hierarchy

Users scan dashboards in **F and Z patterns**:
- Most critical metrics (best lap, improvement) in **top-left**
- Interactive analysis (charts, maps) in the **middle**
- AI coaching report and export options at the **bottom**
- The further down, the less users read the full width

### Dashboard Design Principles

| Principle | Application |
|-----------|------------|
| **Sparklines** | Compact trend alongside metrics (lap time progression) |
| **Delta indicators** | +/- change at a glance per corner |
| **Skeleton UI** | Animated placeholders during CSV processing |
| **Expandable cards** | Corner details that collapse/expand |
| **Tooltips** | Explain jargon on hover ("Trail braking: gradually releasing brake...") |
| **Comparative baselines** | Optimal lap time as a reference line |
| **Micro-history** | Lap-by-lap progression within a session |

### Dark Mode Best Practices

- Avoid pure black (#000000) — use dark grays/navy (Cataclysm uses `#0e1117`)
- Avoid pure white text — use off-whites (Cataclysm uses `#ddd`)
- Lower saturation colors in dark mode
- Minimum 4.5:1 contrast ratio (WCAG 2.1)
- Vibrant accent colors sparingly for key data points
- Dark UIs reduce eye fatigue during extended analysis

### Mobile vs Desktop

- **At the track (mobile)**: Quick session summary, lap times, biggest improvement opportunity. 5-15 min between sessions
- **At home (desktop)**: Full telemetry overlays, multi-session comparison, detailed coaching reports
- Mobile: limit to ~5 visible metrics, stack cards vertically
- Desktop: multi-panel layouts with linked interactions

---

## 7. AI Coaching: What Works

### The OIS Format (Research-Backed Optimal Structure)

Every coaching insight should follow:

1. **Observation**: "You braked 12m early into Turn 5"
2. **Impact**: "This cost you 0.4 seconds per lap"
3. **Suggestion**: "Try braking at the 100m marker instead of the 112m marker"

### Presentation Principles

| Principle | Details |
|-----------|---------|
| **3 priorities per session** | Not 20 things to fix. Garmin Catalyst proved this is the right number |
| **Positive framing first** | Lead with what went well (80-85%) before improvement areas |
| **Conversational format** | Interactive dialogue > static reports. Users can explore and ask follow-ups |
| **Visual anchoring** | Tie every coaching comment to a track position or speed trace moment |
| **Specificity** | "Brake 15m later into Turn 5" >> "improve your braking" |
| **Difficulty-adaptive language** | Adjust vocabulary based on skill level |
| **Longitudinal tracking** | "Your Turn 5 braking improved by 0.8s over 3 sessions" |
| **Actionable, not analytical** | "What to do differently" >> "what happened" |

### AI vs Human Coaching

- **AI excels at**: Pattern recognition, consistency tracking, micro-optimizations, 24/7 availability, instant results
- **Humans excel at**: Motivation, contextual judgment, adapting to emotional state, explaining with analogies
- **Optimal**: "AI proposes, human disposes" — AI as navigation system, human as driver
- **Key finding**: AI coaching produces greater gains for **novice** drivers than advanced ones
- **Blayze validates**: Async coaching at $8-10/session is accepted and effective

### What Novice vs Advanced Users Need from AI

| Skill Level | Coaching Format |
|------------|----------------|
| Novice | Directive: "Brake at the 3-board marker" + encouragement |
| Intermediate | Contextual: "You braked 15m early in T5, costing 0.4s" + technique explanation |
| Advanced | Comparative: "T5 entry speed was 2mph below your session PR" + multi-session trend |

---

## 8. Market Gap Analysis

### Five Unserved Gaps

#### Gap 1: Hardware-Agnostic Web Analysis for Real-World Racing

No platform exists where an HPDE driver can upload data from ANY source and get interactive web-based analysis. Every solution is either hardware-locked, sim-only, desktop-only, or phone-only.

**Cataclysm fills this**: Already ingests RaceChrono CSV v3, could expand to AiM VBO, Garmin FIT.

#### Gap 2: AI Coaching for Real-World Track Driving

AI coaching is proven in sim racing ($5M invested in Track Titan) but **nobody delivers it for real-world HPDE data**. Closest is Garmin Catalyst ($1,200, rudimentary coaching) and Blayze ($8-10/session, human).

**Cataclysm fills this**: Claude-powered coaching with corner-specific insights.

#### Gap 3: Automated Corner Detection and Per-Corner KPIs

No phone app or consumer tool automatically detects corners, extracts apex type, measures brake points, calculates throttle commit distance, or grades corners A-F. AiM/MoTeC allow manual segment creation but don't auto-detect.

**Cataclysm fills this**: Heading-rate-based corner detection with per-corner KPIs is a core feature.

#### Gap 4: Cross-Session Trend Analysis

Most tools analyze single sessions in isolation. HPDE drivers want to see improvement over weeks and months. VRS does this for sim racing. Garmin has leaderboards. No tool does this for real-world data with per-corner resolution.

**Cataclysm fills this**: Multi-session trend analysis with milestone detection.

#### Gap 5: "Strava for Real-World Track Days"

Track Titan's entire thesis is "Strava for Motorsport" — but they are sim-first. There is no social platform where real-world HPDE drivers share laps, compare with friends, and have a feed of track day activity.

**Cataclysm could fill this**: Future opportunity once core coaching is proven.

---

## 9. Design Recommendations for Cataclysm

### Priority 1: Insight Over Data

> Never show a chart without explaining what it means. Every visualization should answer "so what?"

The Garmin Catalyst succeeded by eliminating squiggly lines. Track Titan raised $5M by translating telemetry into coaching. The pattern is clear: **interpretation is the product, not visualization**.

**Concrete changes:**
- Every chart panel should have a 1-line AI insight summary above it
- The Overview tab should lead with a "Session Score" (0-100) and "Top 3 Opportunities"
- Corner analysis should show grades (A/B/C/D/F) before detailed KPIs
- Trends should highlight milestones and breakthroughs, not just raw data

### Priority 2: Progressive Disclosure (Exactly 2 Levels)

**Level 1 — Glanceable Summary (default view):**
- Session Score (0-100)
- Best lap time + delta from previous session
- Top 3 coaching priorities (OIS format)
- Lap time bar chart
- Simple track map (speed-colored)

**Level 2 — Detailed Analysis (on drill-in):**
- Corner-by-corner breakdown with expandable cards
- Speed trace with multi-lap overlay
- Delta-T visualization
- Full AI coaching report
- Traction circle
- Consistency analysis
- Multi-session trends

### Priority 3: Coach, Don't Report

Frame all AI output as coaching, not analysis:
- Use OIS format: Observation → Impact → Suggestion
- Lead with 80% positive, then improvement areas
- Limit to 3 priority items per session
- Use difficulty-adaptive language based on skill level setting
- Make coaching conversational (the existing chat feature is the right approach)
- Tie every insight to a track position or chart element

### Priority 4: Celebrate Improvement

Strava proves this drives engagement:
- Highlight personal bests prominently (green accent, notification)
- Show improvement delta from previous session at the same track
- Progress bars toward milestones ("2 more sessions to average sub-1:50")
- "Best corner" / "most improved corner" callouts
- Multi-session trend with milestone markers

### Priority 5: Zero-Friction Data Flow

Upload-to-insight time should be **under 30 seconds**:
- Drag-and-drop CSV upload
- Auto-detect track (already implemented via track_db)
- Auto-detect laps and filter anomalies (already implemented)
- Show session score and top insights immediately
- No configuration, no track selection (auto), no manual lap splitting

### Priority 6: Persona-Adaptive UI

The Skill Level selector (already in sidebar) should **meaningfully change the experience**:

| Novice | Intermediate | Advanced |
|--------|-------------|----------|
| Session score + improvement | Corner-by-corner breakdown | Full KPI tables |
| Simple track map | Speed trace overlays | Multi-channel telemetry |
| "You improved by 2 seconds!" | "Turn 5 cost 0.4s — brake later" | "T5 entry: 62mph vs 64mph PR, -0.12s" |
| Coaching in plain English | Coaching with technique context | Coaching with quantified targets |
| Hide: traction circle, g-forces | Show: speed trace, delta-T, corner details | Show: everything |

### Priority 7: Visual Design Refinements

Based on competitor analysis and dashboard best practices:
- **F/Z scan pattern**: Put session score and best lap top-left, AI insights top-right
- **Color conventions**: Green = gaining/good, Red = losing/attention, Purple = personal best (F1 convention)
- **Track map prominence**: The color-coded track map is "universally praised" — make it a focal point, not tucked in a card
- **Reduce chart-to-insight distance**: Every chart should have a text annotation explaining the takeaway
- **Expandable corner cards**: Show grade + corner name collapsed; brake/throttle/apex KPIs on expand
- **Responsive layout**: Stacked cards on mobile, multi-panel on desktop

### Priority 8: Competitive Positioning to Communicate

| Message for Marketing | Backed By |
|----------------------|-----------|
| "AI coaching from your existing data — no new hardware" | Gap 2: No competitor does this |
| "Upload a CSV, get coaching in 30 seconds" | Gap 1: No web tool for real-world data |
| "Know exactly which corner costs you the most time" | Gap 3: No auto corner detection elsewhere |
| "Track your improvement across every session" | Gap 4: No cross-session trends for real data |
| "Garmin Catalyst coaching without the $1,200 price tag" | Price anchoring against closest competitor |

---

## 10. Sources

### Phone Apps
- [RaceChrono Official](https://racechrono.com/), [RaceChrono Forum](https://racechrono.com/forum/), [RaceChrono App Store](https://apps.apple.com/us/app/racechrono-pro/id1129429340)
- [Harry's LapTimer Official](https://www.gps-laptimer.de/products), [Harry's Documentation](https://www.gps-laptimer.de/documentation), [Harry's App Store](https://apps.apple.com/us/app/harrys-laptimer-grand-prix/id363556704)
- [HP Tuners TrackAddict](https://www.hptuners.com/product/trackaddict-app/), [TrackAddict UI Refresh](https://www.hptuners.com/articles/hp-tuners-refreshes-trackaddict-app-with-updated-mobile-interface-and-expanded-hardware-support/)

### Professional Telemetry
- [AiM Race Studio 3](https://www.aim-sportline.com/docs/racestudio3/manual/html/analysis.html), [AiM Shop RS3 Analysis](https://www.aimshop.com/pages/race-studio-3)
- [MoTeC i2 Features](https://www.motec.com.au/i2/i2features/), [MoTeC i2 Highlights](https://www.motec.com.au/i2/i2highlights/)
- [Cosworth Pi Toolbox](https://www.cosworth.com/motorsport/products/pi-toolbox/), [Pi Toolbox iRacing Tiers](https://boxthislap.org/cosworth-enhances-pi-toolbox-for-iracing-with-paid-membership-levels/)

### Coaching Devices
- [Garmin Catalyst](https://www.garmin.com/en-US/p/690726/), [Garmin Catalyst 2](https://www.garmin.com/en-US/newsroom/press-release/automotive/optimize-time-on-the-track-with-the-cutting-edge-garmin-catalyst-2/)
- [APEX Pro Gen II](https://apextrackcoach.com/product/apex-pro-gen-2/), [Rennlist APEX Review](https://rennlist.com/forums/data-acquisition-and-analysis-for-racing-and-de/1005167-apex-pro-digital-driving-coach-review.html)
- [Porsche Track Precision](https://newsroom.porsche.com/en/2021/innovation/porsche-track-precision-app-panamera-cayenne-taycan-26649.html)

### Software/SaaS
- [Track Titan](https://www.tracktitan.io/), [Track Titan $5M Funding](https://tech.eu/2025/12/04/track-titan-raises-5m-for-ai-powered-strava-for-motorsport/)
- [VRS](https://vrs.racing/), [Coach Dave Delta](https://coachdaveacademy.com/delta/)
- [Blayze](https://blayze.io/), [Blayze Pricing](https://blayze.io/car-racing/pricing)
- [Track Attack](https://trackattack.io/), [Racemake](https://www.racemake.com/), [RaceData AI](https://www.racedata.ai/)
- [Podium Live](https://podium.live/features), [TracFerme AI](https://tracferme.com/), [MyRaceLab](https://myracelab.com/)

### UX/Design Research
- [Pencil & Paper Dashboard Patterns](https://www.pencilandpaper.io/articles/ux-pattern-analysis-data-dashboards)
- [Smashing Magazine Real-Time Dashboards](https://www.smashingmagazine.com/2025/09/ux-strategies-real-time-dashboards/)
- [UX Planet Progressive Disclosure](https://uxplanet.org/design-patterns-progressive-disclosure-for-mobile-apps-f41001a293ba)
- [Interaction Design Foundation](https://www.interaction-design.org/literature/topics/progressive-disclosure)
- [Toptal Mobile Dashboard UI](https://www.toptal.com/designers/dashboard-design/mobile-dashboard-ui)
- [CleanChart Dark Mode](https://www.cleanchart.app/blog/dark-mode-charts)

### Community & Demographics
- [Grassroots Motorsports Forum](https://grassrootsmotorsports.com/forum/), [Rennlist Forum](https://rennlist.com/forums/)
- [NASA HPDE](https://drivenasa.com/hpde), [AutoInterests Run Group Guide](https://autointerests.com/run-group-guide)
- [Data Driven MQB](https://www.datadrivenmqb.com/driver/laptimers), [Data Driven Coaching](http://datadrivencoaching.net/the-challenge/)
- [Race Track Driving Analysis](http://racetrackdriving.com/data-analysis/)
- [Lockton Motorsports Costs](https://locktonmotorsports.com/costs-of-a-typical-track-day/)

### AI Coaching
- [WSC Sports AI Coaching](https://wsc-sports.com/blog/industry-insights/the-2-5b-secret-how-ai-coaching-is-transforming-elite-sports-performance/)
- [Speed Secrets Garmin Catalyst](https://speedsecrets.com/q-can-you-tell-me-about-the-garmin-catalyst/)
- [PresentCoach Research](https://arxiv.org/html/2511.15253v1)

### Market Data
- [Racing Telemetry Market (market.us)](https://market.us/report/racing-telemetry-market/)
- [Racing Data Acquisition Market (MarketReportsWorld)](https://www.marketreportsworld.com/market-reports/racing-data-acquisition-system-market-14715790)
- [Strava Gamification Case Study](https://trophy.so/blog/strava-gamification-case-study)
- [Oura UX Case Study](https://somesaltwater.com/oura-case-study)
