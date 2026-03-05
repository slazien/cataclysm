# Skill Level System: Research & Improvement Plan

**Date:** 2026-03-05
**Sources:** 3 parallel research agents (60+ web searches, 80+ pages), 6 prior deep-research documents
**Purpose:** Guide improvements to skill-level-differentiated coaching, UI/UX, and report regeneration

---

## Part 1: How Professional Motorsport Coaching Maps to Our Three Levels

### HPDE Group Structure → Cataclysm Mapping

| HPDE Level | Track Days | PCA Color | Cataclysm Level | Key Focus |
|---|---|---|---|---|
| Group 1 | 0-3 | Green | **Novice** | Safety, school line, smooth inputs |
| Group 2 | 3-10 | Yellow/Blue | **Novice** | Solo driving, car dynamics, visual training |
| Group 3 | 10-30 | White | **Intermediate** | Trail braking, data analysis, plateau-breaking |
| Group 4+ | 30+ | Black/Red | **Advanced** | Micro-sector, consistency, setup correlation |

### What Each Level ACTUALLY Needs (From Pro Coaches)

#### Novice (0-10 track days)

**Content they need:**
- Consistency of lap times (not fastest lap)
- Whether they're driving the school line
- Smooth input metrics (brake/throttle transition analysis)
- ONE focus area per session

**Content that overwhelms them:**
- Trail braking concepts
- Corner grades (too many sub-grades)
- Brake pressure analysis
- G-force data
- Delta time analysis
- Detailed corner-by-corner breakdown of all corners
- Any mention of "threshold braking", "rotation", or "slip angle"
- Lap times as competitive metric

**Communication style:**
- Commands: "brake," "turn," "wait"
- Sensory language: "feel the nose dip"
- Metaphors: "squeeze the brake like a sponge"
- Forward-only: what to do next, never past mistakes
- Celebrate completions and small wins

**Key quote:** *"Someone that's never used data before is going to get so much information from just a speed trace. It'll be like a revelation."* — Jeremy Lucas, FastTech

#### Intermediate (10-30 track days)

**Content they need:**
- Speed trace + delta time + corner comparison
- Exit speed priority ("corner exit speed is more important than entry speed")
- Trail braking introduction (the "hockey stick" pattern)
- "No dead time" detection (flat lines = neither braking nor accelerating)
- U-shaped vs V-shaped speed traces in corners
- Self-directed goal setting
- Comparison against their OWN best execution

**Plateau-breaking techniques:**
- Isolate ONE variable, exaggerate it, then dial back
- Socratic questioning: "What felt different on L7?"
- Experiments: "Try braking 3m later for 3 laps, then compare"

**Key insight:** The plateau is real. Kenton Koch found that even experienced drivers' primary issue was often "the application and release of the brake pedal" — something they'd never consciously considered.

#### Advanced (30+ track days, competitive)

**Content they need:**
- Micro-sector analysis (entry/mid/exit phases)
- Consistency metrics (standard deviation, not just best-lap speed)
- Brake release RATE analysis (shape of deceleration curve)
- Corner exit speed compounding: "1 mph more at exit = 0.15s on the straight"
- Speed trade-off analysis across connected corners
- Setup correlation hints
- Mental performance: trigger words, trust in subconscious

**Key metric:** F1-level consistency = 0.2s std dev; backmarker = 0.7s std dev.

### The Universal Rule: 1-2 Items Maximum

**Every source converges on this.** Blayze: "Pick one or a maximum of two things." Garmin Catalyst: exactly 3 "Opportunities." Ross Bentley: "What starts as 'brake at this point, come off the brake here, turn here' becomes 'brake...ease...turn.'"

Research from "The Racer's Mind" (Frontiers in Psychology, 2018): Expert drivers use "chunking" (like chess grandmasters) to compress complex track geometry into reference point patterns. Novices haven't developed these chunks — they're at cognitive capacity just driving the line. Adding data analysis is counterproductive.

---

## Part 2: UI/UX Progressive Disclosure Research

### Core Principle

NN/Group research confirms: "People understand a system **better** when you help them prioritize features and spend more time on the most important ones." Progressive disclosure improves learnability, efficiency, and error rate.

### Rule: Max 2 Disclosure Levels

NN/Group: "Never exceed 2 disclosure levels — designs with 3+ levels have low usability."

For Cataclysm: Summary view (actionable insights) → Detail view (underlying data). Not 3+ nested levels.

### Simplification > Hard Gating

Research strongly favors **simplification over hiding**:
- A/B tests: simplified process → 20% higher completion rate, 15% better week-1 retention
- "Never hard-gate features by skill level. Use simplification + optional depth."
- Reserve hard gating for monetization only

**WHOOP model:** Shows everyone a simple 0-100% Recovery score (green/yellow/red). Advanced users can expand to see HRV, RHR, respiratory rate. Same feature, different depth.

**For Cataclysm:** Don't hide the Corner Tab entirely for novices. Show it with simplified content (min speed, overall grade, one-sentence tip). Advanced users see the full 4-sub-grade breakdown, line analysis, etc.

### Progressive Unlock Examples

| App | Pattern | Lesson for Cataclysm |
|---|---|---|
| **Zwift** | Level-gated areas; XP unlocks | Could unlock "Advanced" features after N sessions |
| **Duolingo** | Mastery levels (Not Started → Mastered) | Auto-detect skill from telemetry (already have this) |
| **Khan Academy** | Skip-ahead if proficient | Allow manual override of auto-detected level |
| **Garmin Connect** | Sensors → metrics appear | GPS quality → line analysis appears (already do this) |
| **WHOOP** | Simple score → expandable detail | Coaching summary → expandable corner detail |

---

## Part 3: Coaching Language Adaptation Research

### The Problem with Our Current Approach

Our `_SKILL_PROMPTS` already differentiate content focus and communication style per level. But the **frontend doesn't adapt the PRESENTATION** of coaching output — the same coaching JSON is rendered the same way regardless of level.

### What Should Change Per Level (Beyond Prompt)

| Dimension | Novice | Intermediate | Advanced |
|---|---|---|---|
| **Priority corners** | 1-2 max | 2-3 | 3-4 |
| **Corner grades** | Hide sub-grades, show overall only | Show all sub-grades | Show sub-grades + line analysis |
| **Metrics shown** | Lap time consistency only | Speed + delta + brake point | All metrics + micro-sector |
| **Coaching language** | "Try braking a bit earlier" | "Your speed trace shows a flat spot — try staying on throttle until braking" | "Brake release rate of 0.3G/s vs 0.5G/s on L4 — progressive release gave 0.8mph more" |
| **GlossaryTerm** | Always show with novice explanation | Show with standard definition | Hide completely (they know) |
| **Drills** | 1 drill, simple format | 1-2 drills, experiment format | Exploration drills with self-discovery |
| **Grade explanations** | Show for every grade | Hide (they understand) | Hide |
| **Line analysis** | Hide | Show (entry/apex/exit offsets) | Show + consistency tier + line error type |
| **Heatmap/Boxplot** | Hide | Show | Show |
| **G-force analysis** | Hide | Hide | Show |
| **Keyboard shortcuts** | Hide | Hide | Show |
| **Raw data table** | Hide | Hide | Show |
| **Coaching report structure** | Celebration → 1 priority → 1 drill | Strengths → 2-3 priorities → experiments | Analysis → 3-4 priorities → exploration drills |

---

## Part 4: Report Regeneration UX (Option 4 Implementation)

### Research Consensus

**All major AI products agree: Manual/on-demand regeneration is strongly preferred** when the operation has meaningful cost.

- ChatGPT: Does NOT auto-regenerate when custom instructions change
- Notion AI: Never auto-regenerates; presents "Accept, Discard, Try again"
- Jasper: New settings apply to new content only; existing content unchanged
- SAP Fiori: Regenerate button close to content with overwrite warning

### Recommended Pattern for Cataclysm

1. **Store generation metadata** with each report: `skill_level`, `generated_at`
   - ✅ Already stored: `skill_level` column in `coaching_reports` table

2. **On settings change**: Save immediately. Show a toast: "Settings updated."
   - ✅ Already works: `uiStore.setSkillLevel()` persists immediately

3. **On report view**: Compare `report.skill_level` vs `uiStore.skillLevel`. If mismatched, show an amber inline banner:
   ```
   ⚠️ This report was generated for [Intermediate]. Your current level is [Advanced].
   [Regenerate Report]
   ```
   - 🔨 NEW: Add banner component to coaching report display
   - 🔨 NEW: Add comparison logic in `useAutoReport` or report component

4. **On "Regenerate" click**: Clear existing report, trigger generation with current skill level. Show loading state.
   - ✅ Mostly exists: `useGenerateReport` mutation already accepts `skillLevel`
   - 🔨 NEW: Need to clear existing report before regenerating (call `clear_coaching_data` first)

5. **Metadata subtitle**: Show "Generated Mar 3 | Intermediate | Haiku 4.5" on each report.
   - 🔨 NEW: Add subtle provenance line to report header

### Implementation Details

**Backend changes needed:**
- Add `POST /{session_id}/report/regenerate` endpoint that clears existing report then triggers generation
- OR: Modify existing `POST /{session_id}/report` to accept `force_regenerate=true` parameter

**Frontend changes needed:**
- `useAutoReport`: Add skill level mismatch detection
- New `SkillLevelMismatchBanner` component
- Add `generated_at` display to report header
- Wire "Regenerate" button to clear + re-trigger flow

---

## Part 5: Revised Feature Matrix (Research-Informed)

### Current vs Proposed

| Feature | Current Novice | Proposed Novice | Rationale |
|---|---|---|---|
| `sectors_tab` | ❌ hidden | ❌ hidden | Correct — too complex |
| `custom_tab` | ❌ hidden | ❌ hidden | Correct — advanced only |
| `replay_tab` | ❌ hidden | ✅ **show** (simplified) | Visual replay helps novices understand the line |
| `heatmap` | ❌ hidden | ❌ hidden | Correct — too abstract for novices |
| `boxplot` | ❌ hidden | ❌ hidden | Correct — statistical analysis overwhelms |
| `absolute_distances` | ❌ hidden | ❌ hidden | Correct — novices think in terms of landmarks |
| `relative_distances` | ✅ shown | ✅ shown | Correct — relative is more intuitive |
| `grade_explanations` | ✅ shown | ✅ shown | Correct — novices need context |
| `guided_prompts` | ✅ shown | ✅ shown | Correct — helps novices ask right questions |
| `raw_data_table` | ❌ hidden | ❌ hidden | Correct |
| `keyboard_overlay` | ❌ hidden | ❌ hidden | Correct |
| `delta_breakdown` | ❌ hidden | ❌ hidden | Correct — too detailed for novices |
| `gforce_analysis` | ❌ hidden | ❌ hidden | Correct |
| `line_analysis` | ❌ hidden | ❌ hidden | Correct — GPS line too abstract |
| `optimal_comparison` | ❌ hidden | ❌ hidden | Correct |

**New features to add to the matrix:**

| Feature | Novice | Intermediate | Advanced | Description |
|---|---|---|---|---|
| `corner_sub_grades` | ❌ | ✅ | ✅ | Show braking/trail/speed/throttle sub-grades |
| `corner_overall_grade_only` | ✅ | ❌ | ❌ | Show only the worst-of-4 overall grade |
| `speed_trace_simplified` | ✅ | ❌ | ❌ | Speed trace without overlaid brake/throttle channels |
| `celebration_mode` | ✅ | ❌ | ❌ | Extra celebration of PBs and completions |
| `session_count_badge` | ✅ | ✅ | ❌ | "Session #3 at Barber" counter |

### Key Insight: Don't Over-Gate

The replay tab is currently hidden from novices, but visual replay of their line would be incredibly valuable for understanding "did I drive the school line?" — it's the most intuitive visualization we have. Research supports this: novices learn best from visual reference, not data tables.

---

## Part 6: Action Items (Prioritized)

### Phase 1: Report Regeneration (Option 4) — 4-6 hours

1. Add `SkillLevelMismatchBanner` component
2. Add mismatch detection in report view (`report.skill_level !== uiStore.skillLevel`)
3. Add `force_regenerate` parameter to POST report endpoint
4. Wire banner's "Regenerate" button to clear + re-trigger
5. Add provenance subtitle ("Generated Mar 3 | Intermediate")
6. Tests

### Phase 2: Coaching Report Structure by Level — 3-4 hours

1. Add `corner_sub_grades` and `corner_overall_grade_only` to feature matrix
2. Modify `CornerDetailPanel` to show simplified grades for novices
3. Modify `PriorityCardsSection` to show fewer cards for novices
4. Add `celebration_mode` feature flag for extra PB celebration
5. Ensure report summary rendering adapts to level

### Phase 3: Frontend Presentation Adaptation — 4-6 hours

1. Revisit replay tab gating (consider showing for novices)
2. Add speed trace simplified mode (no brake/throttle overlay for novices)
3. Improve MetricsGrid novice view (consistency-focused, not speed-focused)
4. Add session counter ("Session #3 at Barber")
5. Ensure CornerQuickCard adapts to skill level

### Phase 4: Coaching Prompt Refinement — 2-3 hours

1. Add "Celebration first" instruction for novice prompts
2. Add controlled variability drill format for advanced
3. Add Socratic questioning examples for intermediate
4. Refine drill templates per level
5. Test with LLM-as-judge evaluation

---

## Sources

### Motorsport Coaching
- [NASA HPDE Program](https://drivenasa.com/hpde/)
- [Race & Track Driving - Run Group Criteria](http://racetrackdriving.com/promotion-checklist/)
- [Instructing Novices](https://racetrackdriving.com/instructor/instructing-novices/)
- [Trail Braking Progression](https://racetrackdriving.com/driving-technique/trailbraking/)
- [NASA Speed News - Transcending the Plateau](https://nasaspeed.news/columns/driver-instruction/transcending-the-plateau/)
- [Blayze Coaching Methodology](https://blayze.io/blog/car-racing/blayze-motorsports-coaching-methodology)
- [Speed Secrets Coaching](https://speedsecrets.com/coaching/)
- [Occam's Racer - Experience Level vs Lap Times](https://occamsracers.com/2023/11/30/how-experience-level-affects-lap-times/)
- [Ross Bentley - Another Catalyst for Change](https://rossbentley.substack.com/p/another-catalyst-for-change)
- [Frontiers - The Racer's Mind (2018)](https://pmc.ncbi.nlm.nih.gov/articles/PMC6099114/)
- [Grassroots Motorsports - Demystify Data](https://grassrootsmotorsports.com/articles/how-demystify-data-acquisition/)
- [Grassroots Motorsports - Diagnose Data Traces](https://grassrootsmotorsports.com/articles/how-to-diagnose-those-data-traces/)
- [PCA Chicago - Run Groups](https://pca-chicago.org/drivers-ed-run-groups/)
- [Riesentöter PCA - Promotion Criteria](https://rtr-pca.org/index.php/menu-activities/menu-drivers-education/menu-promotion-criteria)
- [Clip The Apex - F1 Lap Time Analysis](https://cliptheapex.com/threads/beyond-the-wins-poles-podiums-points-glory-race-lap-time-analysis.6462/)

### UI/UX Progressive Disclosure
- [NN/Group - Progressive Disclosure](https://www.nngroup.com/articles/progressive-disclosure/)
- [IxDF - Progressive Disclosure](https://ixdf.org/literature/topics/progressive-disclosure)
- [Shape of AI - Regenerate Pattern](https://www.shapeof.ai/patterns/regenerate)
- [SAP Fiori - Regenerate Pattern](https://www.sap.com/design-system/fiori-design-web/_article-updates/v1-130/ai-design/ai-design_ready-for-review/regenerate/usage)
- [InfoQ - Stale-While-Revalidate UX](https://www.infoq.com/news/2020/11/ux-stale-while-revalidate/)
- [NN/Group - Confirmation Dialogs](https://www.nngroup.com/articles/confirmation-dialog/)
- [Toptal - Settings UX](https://www.toptal.com/designers/ux/settings-ux)
- [Carbon Design - Notification Patterns](https://carbondesignsystem.com/patterns/notification-pattern/)
- [O'Reilly - 101 UX Principles: Hide Advanced Settings](https://www.oreilly.com/library/view/101-ux-principles/9781788837361/ch26.html)

### AI Content Regeneration
- [Fix It, Tweak It, Transform It (Medium, 2026)](https://medium.com/ui-for-ai/fix-it-tweak-it-transform-it-a-new-way-to-refine-ai-generated-content-dc53fd9d431f)
- [OpenAI - ChatGPT Custom Instructions](https://help.openai.com/en/articles/8096356-chatgpt-custom-instructions)
- [Moesif - AI Cost Analysis](https://www.moesif.com/blog/technical/api-development/The-Ultimate-Guide-to-AI-Cost-Analysis/)
- [Content Freshness vs. Refresh Cost (arXiv)](https://arxiv.org/abs/1008.0441)

### App-Specific UX Examples
- [Zwift XP & Levels](https://zwiftinsider.com/points-levels-unlocks/)
- [Khan Academy Mastery Levels](https://support.khanacademy.org/hc/en-us/articles/5548760867853)
- [WHOOP Recovery](https://www.whoop.com/us/en/thelocker/how-does-whoop-recovery-work-101/)
- [TrainerRoad Adaptive Training](https://www.trainerroad.com/adaptive-training)
- [Duolingo UX Case Study](https://usabilitygeek.com/ux-case-study-duolingo/)
- [Notion Progressive Disclosure](https://medium.com/design-bootcamp/how-notion-uses-progressive-disclosure-on-the-notion-ai-page-ae29645dae8d)
- [Intent-aware Personalized Feedback (Springer)](https://link.springer.com/article/10.1007/s44443-025-00165-5)

### Coaching Communication
- [Coaching Through Mood Words (Sportsmith)](https://www.sportsmith.co/articles/speak-the-language-of-movement-coaching-through-mood-words/)
- [WHOOP AI Coach](https://support.whoop.com/s/article/How-to-Use-the-AI-Powered-WHOOP-Coach)
- [Dr Paul McCarthy - Mental Prep for Racing](https://www.drpaulmccarthy.com/post/inside-the-mind-how-pro-drivers-master-mental-preparation-for-racing)
- [Analysis Coach - Professional Telemetry](https://analysiscoach.com/)
