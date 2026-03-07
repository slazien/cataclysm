# Design Review: Deep Dive Tab — Speed vs Corner Sub-Tab Overlap

**Review ID:** deep_dive_tabs_20260307
**Reviewed:** 2026-03-07 (revised)
**Target:** `frontend/src/components/deep-dive/` (SpeedAnalysis.tsx, CornerAnalysis.tsx, and children)
**Focus:** Usability, Information Architecture, Content Overlap, Drill-Down Interaction
**Severity Summary:** 2 Critical, 4 Major, 2 Minor, 3 Suggestions

---

## Executive Summary

The Speed and Corner sub-tabs suffer from **significant content duplication and unclear conceptual boundaries**. Both tabs show corner-specific analysis (KPIs, grades, AI tips, racing line maps, track maps), making it unclear what each tab's focus is. The Speed tab isn't purely about speed — it's a full-lap view with corner analysis bolted on. The Corner tab adds unique per-corner charts but repeats most of the corner detail content from the Speed tab.

Recent code changes have **worsened** the duplication: `CornerLineMap` has grown to a 937-line feature-rich component (rotation, cursor sync, replay animation, fullscreen, PNG export, lateral exaggeration) that renders identically in both tabs. Both `CornerQuickCard` and `CornerDetailPanel` now have their own prev/next arrow navigation buttons, duplicating corner cycling logic. Meanwhile, `CornerSpeedGapPanel` — a polished, ranked bar chart of corner time costs — sits orphaned and unused in the codebase.

The core problem: **the tabs are organized by UI component availability rather than by analytical question**. Users should think "what question am I trying to answer?" — not "which tab has the widget I need?"

The proposed redesign introduces a **Monitor-Analyze-Detail (MAD) drill-down pattern**: the Lap Trace tab shows WHERE time is lost (monitor/analyze), and a natural CTA in the CornerSpeedGapPanel funnels users to the Corner Focus tab for WHY (detail).

---

## Current State Map

### Speed Tab (`SpeedAnalysis.tsx`) renders:

| Component | What It Shows | Scope | Lines |
|---|---|---|---|
| SpeedTrace | Speed vs distance for full lap | Full-lap | |
| AI Insight | Priority corner tip | Per-corner | |
| Delta-T | Time delta between two laps | Full-lap | |
| Brake/Throttle | Pedal inputs vs distance | Full-lap | |
| Driving Line | Lateral offset from reference | Full-lap | |
| G-G Diagram | Combined G-force scatter | Full-lap | |
| **TrackMapContainer** | Interactive track map | Full-lap | |
| **CornerQuickCard** | Corner KPIs, grades, AI tip, racing line map, prev/next arrows | **Per-corner** | ~401 |

### Corner Tab (`CornerAnalysis.tsx`) renders:

| Component | What It Shows | Scope | Lines |
|---|---|---|---|
| CornerReportCardGrid | All corners as grade cards | All corners | |
| **TrackMapContainer** | Interactive track map | Full-lap | |
| **CornerDetailPanel** | Corner KPIs, grades, AI tip, racing line map, leaderboard, prev/next arrows | **Per-corner** | ~405 |
| CornerSpeedOverlay | Speed through one corner, all laps overlaid | Per-corner x all-laps | |
| BrakeConsistency | Brake point scatter for one corner, all laps | Per-corner x all-laps | |

### Overlap Matrix

| Content | Speed Tab | Corner Tab | Verdict |
|---|---|---|---|
| Track Map | TrackMapContainer | TrackMapContainer | **IDENTICAL** |
| Corner Header (Turn N + grade + time cost) | CornerQuickCard | CornerDetailPanel | **Near-identical** |
| Min Speed KPI | CornerQuickCard | CornerDetailPanel | **Identical** |
| Brake Point KPI | CornerQuickCard | CornerDetailPanel | **Identical** |
| Peak Brake G KPI | CornerQuickCard | CornerDetailPanel | **Identical** |
| Throttle Commit KPI | CornerQuickCard | CornerDetailPanel | **Identical** |
| Optimal Min Speed KPI | CornerQuickCard | CornerDetailPanel | **Identical** |
| Grade chips (braking, trail, min spd, throttle) | CornerQuickCard (compact) | CornerDetailPanel (expanded + explanations) | **Superset** |
| AI coaching tip | CornerQuickCard | CornerDetailPanel | **Near-identical** |
| Racing Line Map (**CornerLineMap — 937 lines**) | CornerQuickCard | CornerDetailPanel | **IDENTICAL** |
| Prev/Next arrow navigation | CornerQuickCard | CornerDetailPanel | **IDENTICAL** |
| Keyboard shortcut hint badge | CornerQuickCard | CornerDetailPanel | **IDENTICAL** |
| "Open in Corner Analysis" link | CornerQuickCard | N/A | **Admits duplication** |
| Corner leaderboard | No | CornerDetailPanel | Unique to Corner |
| Grade explanations | No | CornerDetailPanel | Unique to Corner |
| Corner Speed Overlay | No | CornerSpeedOverlay | Unique to Corner |
| Brake Consistency chart | No | BrakeConsistency | Unique to Corner |
| Report Card Grid | No | CornerReportCardGrid | Unique to Corner |
| Speed Trace | SpeedTrace | No | Unique to Speed |
| Delta-T | DeltaT | No | Unique to Speed |
| Brake/Throttle inputs | BrakeThrottle | No | Unique to Speed |
| Driving Line (full-lap) | LateralOffsetChart | No | Unique to Speed |
| G-G Diagram | GGDiagramChart | No | Unique to Speed |

**Code duplication summary:**
- `CornerQuickCard` (401 lines) and `CornerDetailPanel` (405 lines) share ~70% of logic
- Both define `findBestCorner()` with identical implementation
- Both define `KpiRow` (slightly different signatures)
- Both fetch identical data: `useCorners`, `useAllLapCorners`, `useCoachingReport`, `useOptimalComparison`, `useLineAnalysis`
- Both compute the same grades, deltas, and optimal comparisons
- Both render `CornerLineMap` (937 lines) — a heavyweight canvas component with rotation, replay, fullscreen, export, cursor sync, tooltips, time-interval dots, track boundaries, and lateral exaggeration slider
- Both now have prev/next arrow buttons with identical cycling logic
- Both show a keyboard shortcut hint badge
- The Detail Panel is strictly a superset of the Quick Card

**Orphaned component:** `CornerSpeedGapPanel` (363 lines) is fully built, tested, and polished but **never imported in any UI file** — only referenced in its test. It shows a ranked bar chart of per-corner time costs with animated bars and a focused speed-comparison view. This is the ideal replacement for CornerQuickCard in the redesigned Lap Trace sidebar.

---

## Critical Issues

### Issue 1: Corner Analysis Is Essentially Repeated Across Both Tabs

**Severity:** Critical
**Location:** `SpeedAnalysis.tsx:170-174` (CornerQuickCard), `CornerAnalysis.tsx:120-136` (CornerDetailPanel)
**Category:** Usability / Information Architecture

**Problem:**
When a user clicks a corner on the track map in the Speed tab, they see a detailed Corner Quick Card with KPIs, grades, AI tips, a 937-line racing line visualization, and prev/next navigation arrows. Switching to the Corner tab shows... almost the same information in the Corner Detail Panel, plus two additional charts. The Quick Card even has an "Open in Corner Analysis" button (`CornerQuickCard.tsx:383-395`), which explicitly acknowledges that users are seeing a preview of content that lives elsewhere.

This creates three user experience problems:
1. **Confusion:** "I already see corner data here — what extra does the Corner tab give me?"
2. **Decision fatigue:** Users don't know which tab to use for corner analysis
3. **Wasted cognitive load:** Users must mentally diff the two views to understand what's unique about each

**Impact:**
From competitive research (`tasks/competitive-ux-analysis.md`): the #1 criticism of traditional telemetry tools (AiM, MoTeC) is "clunky and unintuitive" organization. Track Titan and Garmin Catalyst succeed specifically by having clear, focused views. Cataclysm's overlapping tabs risk the same criticism that plagues AiM Race Studio.

### Issue 2: Tabs Are Organized by Component, Not by Question

**Severity:** Critical
**Category:** Information Architecture

**Problem:**
The Speed tab answers two fundamentally different questions:
- "How did I drive the entire lap?" (Speed Trace, Delta-T, Brake/Throttle, Driving Line, G-G Diagram)
- "What happened at this specific corner?" (CornerQuickCard)

The Corner tab also conflates two levels:
- "How do all my corners compare?" (Report Card Grid)
- "What happened at this specific corner across all laps?" (Speed Overlay, Brake Consistency)

Professional tools separate these cleanly:
- **MoTeC i2:** "Time/Distance Graph" (full-lap traces) vs "XY Scatter" (per-section statistical analysis)
- **Track Titan:** Full-lap overlay view vs "Coaching Flows" that focus on one corner at a time
- **Full Grip Motorsport:** 19 detectors organized by PHASE (braking, entry, apex, exit) not by chart type

**Impact:**
From the vision doc (`docs/plans/2026-03-05-vision-design.md`): Cataclysm's design principle #1 is "Insight over data — Never show a chart without explaining what it means." Overlapping tabs obscure the insight because the user can't tell which view answers which question.

---

## Major Issues

### Issue 3: Track Map Rendered Twice

**Severity:** Major
**Location:** `SpeedAnalysis.tsx:164-167`, `CornerAnalysis.tsx:125-129`
**Category:** Usability

**Problem:**
The same `TrackMapContainer` component renders in both tabs. This is the primary navigation element for corner selection, yet it appears identically in two places. The only difference: in the Speed tab, it's in a right sidebar (35% width); in the Corner tab, it's the left panel (60% width).

### Issue 4: CornerQuickCard vs CornerDetailPanel Code Duplication (Worsened)

**Severity:** Major
**Location:** `CornerQuickCard.tsx`, `CornerDetailPanel.tsx`
**Category:** Code Quality / Maintainability

**Problem:**
These two components share ~70% of their logic. Since the initial review, the duplication has **worsened**:

| Duplicated Element | CornerQuickCard | CornerDetailPanel | Status |
|---|---|---|---|
| `findBestCorner()` | Identical | Identical | Was duplicated |
| `KpiRow` component | Compact signature | Extended with `invertDelta`, `deltaUnit` | Was duplicated |
| Data hooks (5 hooks) | All 5 | All 5 | Was duplicated |
| Grade computation | Identical | Identical | Was duplicated |
| `CornerLineMap` (937 lines) | Rendered | Rendered | Was duplicated |
| **Prev/Next arrows** | **Added recently** | **Added recently** | **NEW duplication** |
| **Kbd hint badge** | **Added recently** | **Added recently** | **NEW duplication** |
| Corner cycling callback | `cycleCorner()` | `cycleCorner()` | **NEW duplication** |

The Detail Panel is strictly a superset — it has everything the Quick Card has plus grade explanations, corner leaderboard, and more detailed delta displays.

### Issue 5: Speed Tab Name Is Misleading

**Severity:** Major
**Category:** Usability

**Problem:**
The "Speed" tab contains Brake/Throttle inputs, Driving Line analysis, G-G Diagram, and corner-specific AI insights — none of which are "speed analysis." It's really a "Full Lap Analysis" or "Lap Trace" view. The name "Speed" makes users think the Speed tab and Corner tab differ on WHAT metric they analyze, when they actually differ (or should differ) on the SCOPE: full-lap vs per-corner.

### Issue 6: CornerLineMap (937 Lines) Duplicated in Both Tabs

**Severity:** Major
**Location:** `CornerQuickCard.tsx` → `CornerLineMap`, `CornerDetailPanel.tsx` → `CornerLineMap`
**Category:** Performance / Code Quality

**Problem:**
`CornerLineMap` has grown from a simple racing line visualization into a 937-line heavyweight component with:
- Canvas rendering with d3 scales
- Rotation and bird's-eye view
- Cursor sync with other charts
- Tooltip overlays
- Time-interval dots (0.25s spacing)
- Replay animation with play/pause controls
- Fullscreen mode
- PNG export
- Track boundary drawing
- Lateral exaggeration slider (1-8x)

This component renders identically in both `CornerQuickCard` (Speed tab) and `CornerDetailPanel` (Corner tab). Two instances of this heavyweight canvas component run simultaneously across tabs (though only one is visible at a time due to conditional rendering). The duplication means any feature added to CornerLineMap must be rendered in two different container contexts.

---

## Minor Issues

### Issue 7: Corner Quick Card Has Its Own Navigation Arrows

**Severity:** Minor
**Location:** `CornerQuickCard.tsx:76-89`

**Problem:**
Both CornerQuickCard and CornerDetailPanel now have prev/next arrow buttons that duplicate corner cycling logic also handled by global keyboard shortcuts (`useKeyboardShortcuts.ts`). Three parallel implementations of the same behavior.

### Issue 8: No Visual Continuity When Switching Tabs

**Severity:** Minor
**Category:** Usability

**Problem:**
When a user selects Turn 5 in the Speed tab's track map and then switches to the Corner tab, the corner selection persists (good — it's in `analysisStore`), but the visual layout shifts dramatically. The track map moves from a right sidebar to a left panel with different sizing. There's no visual continuity to anchor the user.

---

## Suggestions

### Suggestion 1: Rename Tabs to Reflect Scope, Not Metric

Rename "Speed" to **"Lap Trace"** and "Corner" to **"Corner Focus"** (or "Corner Drill-Down").

This signals the actual conceptual difference:
- **Lap Trace** = "see the full lap from start to finish"
- **Corner Focus** = "zoom into one corner and understand it deeply"

Alternative names considered: "Full Lap" / "Per Corner", "Overview" / "Corner Drill", "Trace" / "Corner"

### Suggestion 2: Remove Corner Quick Card from Speed Tab

The Speed tab should be purely about full-lap analysis. Remove `CornerQuickCard` entirely. Instead, when a user clicks a corner on the track map in the Speed tab, highlight that section on the speed trace/delta-T/brake-throttle charts (as is already done via cursor sync). If they want corner-specific detail, the Corner tab is one click away via the drill-down CTA (see Suggestion 3).

This creates a clean split:
- **Lap Trace tab:** SpeedTrace + DeltaT + BrakeThrottle + DrivingLine + GGDiagram + TrackMap + CornerSpeedGapPanel (no corner card)
- **Corner Focus tab:** TrackMap + CornerDetailPanel + CornerSpeedOverlay + BrakeConsistency + ReportCardGrid

### Suggestion 3: Add CornerSpeedGapPanel with Drill-Down CTA to Lap Trace Sidebar

To replace the corner context lost by removing CornerQuickCard, activate the **orphaned** `CornerSpeedGapPanel` (363 lines, fully built) in the right sidebar of the Lap Trace tab. This shows the ranked list of corner time costs — a glanceable "where am I losing time?" that naturally complements the full-lap traces without duplicating the Corner tab's detail.

Enhance the panel's existing `CornerFocusView` with a drill-down CTA button that navigates to the Corner Focus tab. This creates the natural progressive disclosure funnel described in the Drill-Down Interaction Design section below.

---

## Drill-Down Interaction Design

### The Problem

The current "Open in Corner Analysis" button in CornerQuickCard (`CornerQuickCard.tsx:383-395`) is a band-aid acknowledgment that the Speed tab duplicates Corner tab content. It's a flat text button that says "Open in Corner Analysis" — low visibility, no context about what additional insight the user will gain by switching.

The redesign needs a drill-down interaction where users naturally flow from "where am I losing time?" (Lap Trace) to "why am I losing time at this corner?" (Corner Focus) without confusion or surprise.

### Research: Best Practices for Drill-Down Navigation

From UX research on analytics drill-down patterns:

1. **Monitor-Analyze-Detail (MAD) Framework** ([Pencil & Paper](https://www.pencilandpaper.io/articles/ux-pattern-analysis-data-dashboards), [GoodData](https://medium.com/gooddata-developers/six-principles-of-dashboards-information-architecture-5487d84c20c4)): Effective analytics UIs use a layered information delivery system where each level expands on the previous one — Monitor (overview metrics) → Analyze (comparative views) → Detail (granular drill-down).

2. **Explicit affordance over auto-navigation** ([FusionCharts](https://www.fusioncharts.com/resources/charting-best-practices/drill-down-interface)): Clearly indicate clickable visual elements with consistent design aesthetics and visual cues. Users should always feel in control of navigation depth — auto-navigating on click is jarring when users may just want to select/highlight.

3. **Progressive disclosure** ([NN/g](https://www.nngroup.com/articles/progressive-disclosure/), [IxDF](https://ixdf.org/literature/topics/progressive-disclosure)): Defer less important information to secondary screens. Show only the most important information initially, reducing cognitive overload. However, avoid hiding important information too deeply — keep the drill-down to 1-2 clicks.

4. **Visual continuity** ([Improvado](https://improvado.io/blog/drill-down-reports-guide), [Bold BI](https://www.boldbi.com/blog/what-is-drill-down-and-drill-up-in-dashboards/)): Use the same chart style and color scheme across levels to build familiarity. Ensure navigational responsiveness — slow or clunky navigation frustrates users and reduces adoption.

5. **Back-navigation affordance** ([FusionCharts](https://www.fusioncharts.com/blog/4-things-to-know-to-create-an-intuitive-drill-down-interface/)): Always provide a clear way back. Breadcrumb-style context shows the user where they drilled from.

6. **Motorsport tools pattern** ([Track Titan](https://www.tracktitan.io/post/how-to-analyse-telemetry-for-sim-racing)): Track Titan segments telemetry data into manageable parts rather than showing everything at once. Every improvement opportunity is displayed on the track map — click any marker to see detailed recommendations and estimated time gains. This is exactly the overview-then-drill pattern.

### Evaluated Interaction Approaches

| Approach | Description | Pros | Cons | Verdict |
|---|---|---|---|---|
| **A: Auto-navigate on click** | Clicking a corner bar in CornerSpeedGapPanel switches to Corner Focus tab | Fewest clicks | Jarring; user may want to see trace highlights, not leave the tab; violates user control principle | Rejected |
| **B: Double-click to drill** | Single-click selects corner, double-click navigates | Keeps single-click simple | Not discoverable; not mobile-friendly; no convention for this in analytics UIs | Rejected |
| **C: Inline CTA button** | Clicking selects corner and shows a focused view with a "Drill into Turn N" button | Two-step gives control; user sees preview before committing; explicit affordance | Extra click vs auto-navigate | Rejected (extra UI element when gap panel is compact) |
| **D: Progressive preview + CTA** | Click selects corner → CornerSpeedGapPanel's focus view shows speed bars + "Explore Turn N in detail →" CTA → clicking CTA switches tab | Natural 3-step funnel; matches MAD framework; user always in control; CTA provides context about what they'll see | Two clicks to drill (acceptable per research) | **Selected** |

### Selected Design: Progressive Preview + CTA (Approach D)

The CornerSpeedGapPanel **already has** a `CornerFocusView` component (`CornerSpeedGapPanel.tsx:116-232`) that appears when a corner is selected. It shows a speed comparison between the user's min speed and the optimal, with insight text. This is the perfect "preview" step before drilling into the full Corner Focus tab.

**The 3-step progressive disclosure funnel:**

```
Step 1: MONITOR — Ranked Bar Chart (all corners)
  User sees: "T5 is my biggest time loss (+0.45s)"
  Action: Click T5 bar
        ↓
Step 2: ANALYZE — Speed Comparison Preview (one corner)
  User sees: "Your speed: 58.3 mph vs Optimal: 61.6 mph — closing the 3.3 mph gap saves ~0.45s"
  Action: Click "Explore Turn 5 →" CTA
        ↓
Step 3: DETAIL — Corner Focus Tab (full analysis)
  User sees: Full CornerDetailPanel + CornerSpeedOverlay + BrakeConsistency + CornerLineMap
  User can: Cycle corners, view grades, see AI coaching, analyze racing line, view leaderboard
```

**Implementation details:**

1. **CTA button in CornerFocusView:** Add a styled button at the bottom of the existing `CornerFocusView` component:
   ```tsx
   <button
     onClick={() => {
       selectCorner(`T${opp.corner_number}`);
       setMode('corner');
     }}
     className="mt-2 flex w-full items-center justify-center gap-1.5 rounded-lg
                bg-[var(--cata-accent)]/10 py-2 text-xs font-medium
                text-[var(--cata-accent)] transition-colors
                hover:bg-[var(--cata-accent)]/20"
   >
     Explore Turn {opp.corner_number} in detail
     <ArrowRight className="h-3.5 w-3.5" />
   </button>
   ```

2. **State flow:**
   - `selectedCorner` is already in `analysisStore` and persists across tab switches
   - `setMode('corner')` switches the DeepDive tab to Corner Focus
   - Corner Focus tab reads `selectedCorner` from store → CornerDetailPanel renders for that corner
   - No new state management needed — the existing architecture supports this perfectly

3. **Visual continuity:**
   - The corner selection (e.g., "T5") persists across the tab switch via `analysisStore.selectedCorner`
   - The CornerSpeedGapPanel's focus view header ("Turn 5 Breakdown") matches the CornerDetailPanel's header ("Turn 5")
   - The speed gap numbers carry over as KPIs in the detail view
   - The CTA button uses accent color to signal it's an action, not just info

4. **Back-navigation:**
   - The tab bar (Lap Trace | Corner Focus) is always visible at the top — clicking "Lap Trace" returns the user
   - The corner selection persists, so if the user goes back to Lap Trace, the CornerSpeedGapPanel still shows the T5 focus view
   - No breadcrumb needed — the tab bar itself serves as the navigation context

5. **Track map corner click:**
   - In the Lap Trace tab, clicking a corner on the track map sets `selectedCorner` → CornerSpeedGapPanel shows the focus view with CTA
   - In the Corner Focus tab, clicking a corner on the track map updates `selectedCorner` → CornerDetailPanel updates (existing behavior)
   - Same click action, different consequence per tab — but always coherent with the tab's purpose

6. **Mobile behavior:**
   - On mobile, the CornerSpeedGapPanel stacks below the track map in the Lap Trace tab
   - The CTA button is full-width, large enough for touch (44px min height)
   - Tab switching works identically on mobile

### Why This Approach Works

This design follows every principle from the research:

| Principle | How This Design Satisfies It |
|---|---|
| **MAD Framework** | Step 1 = Monitor (ranked bars), Step 2 = Analyze (speed comparison), Step 3 = Detail (full corner analysis) |
| **Explicit affordance** | CTA button with "Explore Turn N in detail →" text — user knows exactly what clicking does |
| **User control** | Single-click never auto-navigates; user explicitly chooses to drill down via CTA |
| **Progressive disclosure** | Each step reveals more information; user is never overwhelmed |
| **Visual continuity** | Corner selection persists; header text matches; accent color on CTA signals action |
| **Back-navigation** | Tab bar always visible; clicking "Lap Trace" returns to overview |
| **Motorsport tools pattern** | Mirrors Track Titan's "click marker to see recommendation, click to drill" flow |

---

## Proposed Redesign

### New Tab Architecture

```
Deep Dive
  |-- Lap Trace (was: Speed)
  |     |-- [Left 65%] Speed Trace + AI Insight + Delta-T + Brake/Throttle + Driving Line + G-G
  |     |-- [Right 35%] Track Map + CornerSpeedGapPanel (ranked bar chart + drill-down CTA)
  |     |-- Interaction: clicking corner on map/chart highlights traces AND shows gap panel focus
  |     |-- Drill-down: CTA in gap panel focus view → switches to Corner Focus tab
  |
  |-- Corner Focus (was: Corner)
  |     |-- [Toggle] Grid View / Detail View
  |     |-- Grid: CornerReportCardGrid (all corners, sorted by grade)
  |     |-- Detail:
  |     |     |-- [Left 50%] Track Map (zoomed to corner) + Corner Speed Overlay
  |     |     |-- [Right 50%] Corner Detail Panel + Brake Consistency
  |     |     |-- Corner navigation via arrows + keyboard
  |     |
  |-- Sectors (skill-gated, unchanged)
  |-- Replay (skill-gated, unchanged)
```

### What Changes

| Change | Rationale | Effort |
|---|---|---|
| Rename "Speed" → "Lap Trace" | Reflects actual scope (full-lap traces) | Trivial |
| Rename "Corner" → "Corner Focus" | Clearer purpose | Trivial |
| Remove CornerQuickCard from Lap Trace | Eliminates primary duplication (~401 lines) | Medium |
| Activate CornerSpeedGapPanel in Lap Trace sidebar | Provides corner context without duplicating detail; already built (363 lines) | Low |
| Add drill-down CTA to CornerSpeedGapPanel's CornerFocusView | Natural progressive disclosure funnel from Lap Trace → Corner Focus | Low |
| Remove "Open in Corner Analysis" button | No longer needed — drill-down CTA replaces it | Trivial |
| Delete CornerQuickCard.tsx | ~401 lines removed; all functionality preserved in CornerDetailPanel | Low |
| Consolidate shared code (KpiRow, findBestCorner) into shared util | Code quality; prevents future duplication | Medium |
| Corner Focus detail: auto-zoom track map to selected corner | Differentiates from Lap Trace's full-map view; enhances per-corner focus | Optional |

### What Stays the Same

- All existing charts/visualizations (no data loss)
- Corner selection via track map click and keyboard arrows
- Cursor sync across charts
- Skill-level gating for advanced features
- Report Card Grid toggle
- CornerDetailPanel content (it becomes THE corner view, not a duplicate)
- CornerLineMap (937 lines) only renders in Corner Focus tab now — no performance duplication
- analysisStore state management (selectedCorner, deepDiveMode)

### Data Flow After Redesign

```
[Lap Trace Tab]
  TrackMap click T5
       ↓
  analysisStore.selectCorner('T5')
       ↓
  CornerSpeedGapPanel reacts → shows CornerFocusView for T5
  Speed Trace/Delta-T/BrakeThrottle highlight T5 zone via cursorDistance
       ↓
  User clicks "Explore Turn 5 in detail →" CTA
       ↓
  analysisStore.setMode('corner')
       ↓
[Corner Focus Tab]
  CornerDetailPanel reads selectedCorner='T5' → renders full T5 analysis
  CornerSpeedOverlay shows T5 speed overlay
  BrakeConsistency shows T5 brake scatter
  CornerLineMap renders T5 racing line (only instance now)
```

---

## Competitive Validation

This split mirrors how the best tools organize analysis:

| Tool | Full-Lap View | Per-Corner View | Drill-Down Method |
|---|---|---|---|
| MoTeC i2 | Time/Distance Graph | XY Scatter + Section Analysis | Click section on graph |
| AiM Race Studio | Distance Graph | Scatter + Histogram | Select section range |
| Track Titan | Lap overlay with all channels | Coaching Flows (one corner) | Click marker on track map |
| Full Grip | Full telemetry view | Per-detector breakdown | Click detector on map |
| Garmin Catalyst | Speed trace | "Top 3 corner opportunities" | Tap opportunity card |
| **Cataclysm (proposed)** | **Lap Trace** | **Corner Focus** | **Gap panel CTA** |

The "Lap Trace = full-lap sequential" vs "Corner Focus = one-corner cross-lap" split is the standard in professional tools because it maps to how drivers actually analyze:

1. **Step 1:** "Where on the lap am I losing time?" → Lap Trace (see Delta-T dip at T5, see gap panel ranking)
2. **Step 2:** "How much am I losing at T5?" → CornerSpeedGapPanel focus view (speed comparison bars)
3. **Step 3:** "What's wrong with my T5 technique?" → Corner Focus (grades, AI coaching, racing line, brake consistency)

From coaching research (`tasks/coaching_science_deep_research.md`): effective coaching uses **progressive disclosure** — identify the problem area first, then drill in. Two tabs that both show corner details break this progression. The MAD funnel restores it.

---

## Implementation Priority

1. **Rename tabs** (trivial — string changes in `DeepDive.tsx:81-82`)
   - `'speed'` label → `'Lap Trace'`, `'corner'` label → `'Corner Focus'`
   - Keep internal mode values as `'speed'` / `'corner'` to avoid breaking store/shortcuts

2. **Remove CornerQuickCard from SpeedAnalysis** (medium)
   - Remove import and JSX from `SpeedAnalysis.tsx:16,170-174`
   - Right sidebar changes: track map takes full height, CornerSpeedGapPanel below it

3. **Activate CornerSpeedGapPanel in Lap Trace sidebar** (low)
   - Import and render in `SpeedAnalysis.tsx` right column
   - Pass `sessionId` and `parseCornerNumber(selectedCorner)` as props
   - Already fully built and tested

4. **Add drill-down CTA to CornerSpeedGapPanel** (low)
   - Add `onDrillDown?: (corner: number) => void` prop
   - Add CTA button to `CornerFocusView` component
   - In `SpeedAnalysis.tsx`: `onDrillDown={(c) => { selectCorner(`T${c}`); setMode('corner'); }}`

5. **Delete CornerQuickCard.tsx** (low)
   - Remove file entirely after step 2
   - ~401 lines of duplicated code eliminated

6. **Consolidate shared code** (medium)
   - Extract `findBestCorner()` to `lib/cornerUtils.ts` (or extend existing)
   - Extract shared `KpiRow` to `components/shared/KpiRow.tsx`
   - CornerDetailPanel imports from shared utils instead of defining locally

7. **Track map corner-zoom in Corner Focus** (optional, low-medium)
   - When `deepDiveMode === 'corner'`, TrackMapContainer auto-zooms to selected corner
   - Differentiates from Lap Trace's full-map view

---

## Positive Observations

- The cursor sync system across charts is excellent — professional-grade UX
- Corner selection persisting across tab switches via `analysisStore` is the right architecture — it makes the drill-down flow possible with zero new state management
- The CornerReportCardGrid with grade-sorted cards is unique and valuable — no competitor has this
- BrakeConsistency and CornerSpeedOverlay charts are genuinely unique analysis — the Corner tab's actual unique value
- The skill-level gating system (progressive disclosure) follows best practices from the coaching research
- The CornerSpeedGapPanel (bar chart ranking time costs) is an excellent Arccos-style "Corners Gained" visualization — it just needs to be activated
- The CornerLineMap's feature set (replay, fullscreen, export, exaggeration slider) is impressive — consolidating it to one instance in Corner Focus makes it a premium drill-down reward

---

## Next Steps

1. Align on the tab rename (Lap Trace / Corner Focus vs alternatives)
2. Confirm the drill-down interaction design (Progressive Preview + CTA approach)
3. Implement steps 1-5 as a single PR (coherent change)
4. Extract shared corner utilities (step 6) as a follow-up cleanup PR
5. Visual QA on mobile — the layout changes affect the single-column stack
6. Consider track map zoom (step 7) as a polish follow-up

---

_Generated by UI Design Review. Run `/ui-design:design-review` again after fixes._
