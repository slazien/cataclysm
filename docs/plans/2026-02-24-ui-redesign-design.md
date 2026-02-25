# UI Redesign: Coaching-First Telemetry Analysis

**Date:** 2026-02-24
**Status:** Approved
**Branch:** `nextjs-rewrite`

---

## 1. Problem Statement

Cataclysm's current UI is organized by data type (5 tabs: Overview, Speed Trace, Corners, AI Coach, Trends). This is how engineering tools like AiM Race Studio organize things — and it's why those tools get criticized for steep learning curves.

HPDE drivers don't think in terms of "speed traces" and "corner tables." They think: **"How did I do? What should I work on? Am I improving?"** The UI should follow that mental model.

### What Competitors Prove

- **Garmin Catalyst** ($1,200) succeeds with "Top 3 opportunities" + a session score — no squiggly lines
- **Track Titan** raised $5M by making AI coaching the product, not charts
- **Every tool** that shows raw data without interpretation (AiM, Harry's, RaceChrono) gets criticized for being "clunky and unintuitive"
- **No web-based tool** combines real-world track data + AI coaching + accessible UX

Full competitive analysis: `tasks/competitive-ux-analysis.md`

---

## 2. Design Principles

1. **Insight over data** — Never show a chart without explaining what it means
2. **Progressive disclosure (2 levels)** — Glanceable summary → detailed analysis on drill-in
3. **Coach, don't report** — Frame all AI output as coaching (OIS: Observation → Impact → Suggestion)
4. **Celebrate improvement** — Personal bests, milestones, progress narratives
5. **Zero friction** — Upload to insight in under 30 seconds
6. **Adaptive defaults, full access** — Skill level sets starting point, never hides features

---

## 3. Information Architecture

### Navigation Model

Replace the 5-tab + sidebar layout with:

- **Top bar**: 3 view tabs + upload button + coach toggle + settings
- **Contextual bar**: Session selector (opens left drawer) + lap pill bar (Deep Dive only)
- **Session drawer**: Opens from LEFT — session library, upload, multi-session management
- **Coach panel**: Opens from RIGHT — persistent AI chat + report summary
- **Mobile**: Bottom tab bar (not hamburger), session selector as full-screen modal, coach as bottom sheet

```
Desktop:
┌──────────────────────────────────────────────────────────────────┐
│ [Logo]  [Dashboard] [Deep Dive] [Progress]    [+Upload] [AI] [⚙] │
├──────────────────────────────────────────────────────────────────┤
│ [Barber Motorsports ▾ > Feb 15 Morning ▾]  [L3] [L5] [L7*] [L9] │
├──────────────────────────────────────────────────────────────────┤
│ ← Session Drawer │      Main Content Area      │ Coach Panel → │
│   (left, on      │      (active view)           │ (right, on   │
│    demand)        │                              │  demand)     │
└──────────────────────────────────────────────────────────────────┘

Mobile:
┌────────────────────────┐
│ [Barber ▾] [Feb 15 ▾]  │
├────────────────────────┤
│                        │
│    Main Content        │
│    (single column)     │
│                        │
├────────────────────────┤
│ [Dashboard] [Dive] [Progress] [AI] │
└────────────────────────┘
```

### Why No Sidebar

The current sidebar uses 280px for session management that's needed occasionally. Reclaiming that space for Deep Dive's synchronized panels is a bigger win. Sessions become a left drawer opened when switching context. The lap pill bar in the contextual bar handles the most frequent interaction (lap switching) without opening any drawer.

### Upload Discoverability (3 entry points)

Without a sidebar, upload must be discoverable elsewhere:
1. **Empty state CTA** — primary path for new users
2. **"+" button in top bar** — always visible
3. **Drag-and-drop** — entire viewport accepts CSV files with full-screen overlay indicator

---

## 4. Views

### 4.1 Session Dashboard ("How did I do?")

The landing page after uploading. Answers the question in under 10 seconds.

**Layout:**

```
┌──────────────────────────────────────────────────────────────────┐
│  Hero Metrics Row                                                 │
│  [Session Score /100] [Best Lap] [vs Last Session] [Skill Level] │
├──────────────────────────────────────────────────────────────────┤
│  Two-column middle                                                │
│  ┌─── Top 3 Priorities ─────┐  ┌─── Hero Track Map ────────────┐│
│  │ 1. T5 braking (0.4s)    │  │ Color-coded by corner grade   ││
│  │ 2. T1-2 consistency     │  │ (green=A, amber=B, red=C/D)   ││
│  │ 3. Esses — great! ✓     │  │ Click corner for details      ││
│  │ [Show in Deep Dive →]   │  │                                ││
│  └──────────────────────────┘  └────────────────────────────────┘│
├──────────────────────────────────────────────────────────────────┤
│  Lap Times Bar Chart (PB = purple, AI annotation above)          │
│  [Consistency Score] [Clean Laps] [Top Speed] [Optimal Lap]      │
└──────────────────────────────────────────────────────────────────┘
```

**Key decisions:**
- **Session Score (0-100)** is the single most prominent element — combines lap time vs optimal, consistency, and corner execution
- **Top 3 Priorities** use OIS format (Observation, Impact, Suggestion). Third item always positive. Each links to Deep Dive at the relevant corner
- **Track map colored by corner grade**, not speed — answers "where should I improve?" at a glance
- **"vs Last Session"** metric only appears with prior session at same track. Celebration treatment for PBs
- **Skill level** auto-detected from data (consistency, brake variance), overridable with one click
- **Optimal Lap** metric shows composite best achievable from the driver's own segments

**Mobile:** Same content, single column stacked: Score → Priorities → Mini track map → Lap times → Metrics.

### 4.2 Deep Dive ("Show me the data")

Synchronized panel analysis with three sub-modes via segmented control.

#### Sub-mode: Speed Analysis (default)

```
┌──────────────────────────────────────────────────────────────────┐
│ [● Speed Analysis]  [ Corner Analysis ]  [ Custom ]              │
├───────────────────────────────────────┬──────────────────────────┤
│  Speed Trace (~50% height)            │  Track Map (35% width)   │
│  Two laps overlaid, distance X-axis   │  Color = delta (rainbow) │
│  Corner zones as transparent rects    │  Cursor dot on track     │
│  AI annotations at key points         │  Corner labels + grades  │
│  ┈┈┈┈┈ synchronized cursor ┈┈┈┈┈    │  (clickable)             │
├───────────────────────────────────────┤                          │
│  Delta-T (~25% height)               │  Corner Quick Card       │
│  Green above = gaining time           │  (appears on corner      │
│  Red below = losing time              │  click: grade, KPIs,     │
│  Same X-axis, shared cursor           │  AI tip, "vs best" delta │
├───────────────────────────────────────┤  indicators)             │
│  Brake/Throttle (~25% height)        │                          │
│  Red = brake g, Green = throttle      │                          │
│  Same X-axis, shared cursor           │                          │
└───────────────────────────────────────┴──────────────────────────┘
```

**Synchronized cursor model:**
- Single `cursorDistance` (meters from S/F) shared across all panels via Zustand store
- Mouse move on any chart → vertical cursor line on all charts, dot moves on track map, tooltips update
- Click corner on map → charts scroll/zoom to that section, Corner Quick Card appears
- Updates throttled to `requestAnimationFrame` for 60fps across 3+ canvas charts

**Left column hierarchy:** Speed (largest — "the ultimate judge"), Delta-T (the "why"), Brake/Throttle (the "how"). Standard telemetry hierarchy from competitive analysis.

**Lap comparison:** Single lap selected → charts show that lap, delta vs optimal/best. Two laps selected (shift-click pills) → overlay both, delta shows gap between them, track map shows rainbow delta.

#### Sub-mode: Corner Analysis

```
┌──────────────────────────────────┬───────────────────────────────┐
│  Track Map (50% width)           │  Corner Detail Panel          │
│  All corners labeled + graded    │  Name, grade, KPIs            │
│  Selected corner highlighted     │  (entry/apex/exit speed,      │
│  ← → arrows to cycle corners    │  brake point, throttle commit,│
│                                  │  apex type, vs best lap)      │
│                                  │  🤖 AI coaching tip            │
├──────────────────────────────────┴───────────────────────────────┤
│  Corner Speed Overlay              │  Brake Consistency Chart     │
│  All clean laps for this corner    │  Brake point scatter by lap  │
└────────────────────────────────────┴─────────────────────────────┘
```

Corner-by-corner navigation via map click or arrow keys. Maps to how drivers think about the track.

#### Sub-mode: Custom Layout

Power users drag panels from a palette into a configurable grid. Save/load named layouts. The "Race Studio for the web" escape hatch — available but not default.

**Mobile Deep Dive:** Single chart at a time with swipe navigation. Track map first with tappable corner hotspots. Cursor position persists across swipes. No multi-panel layout on mobile — accept the constraint.

### 4.3 Progress ("Am I improving?")

Meaningful with 2+ sessions at the same track.

```
┌──────────────────────────────────────────────────────────────────┐
│  Hero Metrics: [Sessions] [All-Time Best] [Latest Best] [Trend] │
├──────────────────────────────────────────────────────────────────┤
│  🤖 AI Progress Summary (2-3 sentences synthesizing the story)   │
├──────────────────────────────────────────────────────────────────┤
│  Milestone Timeline (horizontal)                                  │
│  ──●─────────●──────────●─────────●── (first session → PB → ..) │
├────────────────────────────┬─────────────────────────────────────┤
│  Lap Time Trend            │  Consistency Trend                   │
│  (best / top-3 avg /       │  (consistency score per session)     │
│   optimal lines)           │  with AI annotation                  │
│  with plateau detection    │                                      │
├────────────────────────────┴─────────────────────────────────────┤
│  Corner Progression Heatmap                                       │
│  Metric selector: [Min Speed ▾] / Brake Consistency / Grade      │
│  Sessions × Corners grid, color-coded                             │
│  Click any cell → Deep Dive for that corner+session               │
├──────────────────────────────────────────────────────────────────┤
│  Session Box Plots (lap time distribution per session)            │
└──────────────────────────────────────────────────────────────────┘
```

**Key decisions:**
- **Milestone timeline** is the emotional anchor (Strava pattern) — auto-detected: PBs, per-corner improvements, consistency thresholds
- **AI Progress Summary** synthesizes the multi-session narrative — no competitor does this for real-world data
- **Corner Progression Heatmap** shows which corners are improving vs stagnant at a glance. Clickable cells deep-link to Deep Dive
- **Plateau detection** — AI identifies when best lap trend flattens and which corners hold the key to breaking through
- **Sparse state (<3 sessions):** Structure shown with ghost data points, message: "2 more sessions to unlock full trend analysis"

### 4.4 Ask the Coach Panel

Persistent right-side panel, 400px wide on desktop. Available from any view.

```
┌──────────────────────────┐
│  Ask the Coach     [✕]   │
│  ────────────────────────│
│  Context:                │
│  [Session: Feb 15]       │
│  [Viewing: L5 vs L7]    │
│  [Corner: T5]            │
│  ────────────────────────│
│  Report Summary          │
│  Overall: B+ | Focus: T5 │
│  [Full report ↓]        │
│  ────────────────────────│
│  Suggested questions:    │
│  • Why am I slow in T5?  │
│  • Compare L5 vs L7      │
│  ────────────────────────│
│  [Chat conversation...]  │
│  ────────────────────────│
│  [Ask a question... Send]│
└──────────────────────────┘
```

**Key decisions:**
- **Context chips** auto-update as user navigates — AI knows what you're looking at
- **Report auto-generates** on session load (no manual "Generate" button)
- **Suggested questions** are contextual — change based on current view and selected corner/lap
- **Panel pushes content left** (not overlay) — user sees charts while chatting
- **Mobile:** Bottom sheet with peek state (last message + input)

---

## 5. Visual Design System

### Color Tokens

```
Backgrounds:
  --bg-base:      #0a0c10    (app background)
  --bg-surface:   #13161c    (cards, panels)
  --bg-elevated:  #1c1f27    (popovers, hover states)
  --bg-overlay:   #252830    (modals, drawers)

Text:
  --text-primary:   #e2e4e9
  --text-secondary: #8b919e
  --text-muted:     #555b67

Motorsport semantic:
  --color-brake:    #ef4444  (red — braking, losing time)
  --color-throttle: #22c55e  (green — throttle, gaining time)
  --color-pb:       #a855f7  (purple — personal best)
  --color-optimal:  #3b82f6  (blue — optimal/theoretical)
  --color-neutral:  #f59e0b  (amber — caution, medium)

Grades: A=#22c55e  B=#84cc16  C=#f59e0b  D=#f97316  F=#ef4444

Lap palette (8 colorblind-safe):
  #58a6ff, #f97316, #22c55e, #e879f9, #facc15, #06b6d4, #f87171, #a3e635

AI content:
  --ai-border:  gradient(135deg, #6366f1, #a855f7)
  --ai-bg:      #6366f110
  --ai-icon:    #818cf8

Interactive:
  --accent:       #3b82f6
  --accent-hover: #2563eb
  --border:       #2a2d35
  --cursor-line:  #ffffff40
```

### Typography

```
Sans:  "Inter", system-ui, sans-serif
Mono:  "JetBrains Mono", "SF Mono", monospace  (lap times, KPIs)

Scale: xs=11px, sm=13px, base=15px, lg=18px, xl=24px, hero=36px
Weights: 400 (body), 500 (labels), 600 (headings), 700 (hero numbers)
```

### AI Content Treatment

AI-generated content is visually distinct from calculated data:
- **Calculated facts**: Solid border, `--bg-surface`, no icon
- **AI interpretations**: Gradient border (indigo→purple), `--ai-bg` tint, 🤖 icon prefix

### Component Library

**Base:** shadcn/ui customized with motorsport tokens.

**Custom components:**
- MetricCard — hero number + label + delta indicator
- GradeChip — A-F pill with grade color
- LapPill — lap number + time, toggleable, PB star marker
- CornerCard — expandable: grade + KPIs + AI tip
- AiInsight — gradient border, 🤖 prefix, tinted background
- TrackMap — interactive SVG with corner hotspots
- MilestoneTimeline — horizontal timeline with event markers
- ContextChip — coach panel context indicators

---

## 6. Technical Architecture

### Charting: Canvas-backed D3

Move from pure SVG D3 to Canvas for synchronized charts:
- SVG has poor performance with 3+ charts × 3000+ points × 60fps cursor
- Canvas renders the data layer; thin SVG overlay handles cursor line + tooltips
- Keep SVG-only for track map (needs DOM events on corners) and small static charts

### State Architecture (4 Zustand slices)

```typescript
// 1. SessionStore
{
  activeSessionId: string | null;
  sessions: SessionSummary[];
  uploadState: "idle" | "uploading" | "processing" | "done";
}

// 2. AnalysisStore (NEW — synchronized cursor system)
{
  cursorDistance: number | null;     // meters from S/F line
  selectedLaps: number[];           // from pill bar
  selectedCorner: string | null;    // corner ID
  deepDiveMode: "speed" | "corner" | "custom";
  zoomRange: [number, number] | null;
}

// 3. CoachStore
{
  panelOpen: boolean;
  report: CoachingReport | null;
  chatHistory: Message[];
  contextChips: ContextChip[];      // auto-updated from AnalysisStore
}

// 4. UiStore
{
  skillLevel: "novice" | "intermediate" | "advanced";
  sessionDrawerOpen: boolean;
  unitPreference: "imperial" | "metric";
}
```

**TanStack Query** layer mostly reused from current codebase. New hooks:
- `useCoachAnnotations(sessionId)` — returns positioned AI insights for chart overlays
- `useAutoReport(sessionId)` — auto-triggers report generation on session load

### Cursor Synchronization

Each canvas chart subscribes to `cursorDistance` via Zustand selector. Updates throttled to `requestAnimationFrame`:

```typescript
const cursorDistance = useAnalysisStore(s => s.cursorDistance);

useAnimationFrame(() => {
  if (cursorDistance !== null) {
    drawCursorLine(ctx, xScale(cursorDistance));
    drawTooltip(overlayRef, cursorDistance, data);
  }
});
```

Track map converts `cursorDistance` → lat/lon via interpolation on the track path.

### File Structure

```
frontend/
├── app/
│   ├── layout.tsx, page.tsx, globals.css
├── components/
│   ├── ui/                     (shadcn/ui base)
│   ├── navigation/             (TopBar, LapPillBar, SessionDrawer, MobileBottomTabs)
│   ├── dashboard/              (SessionDashboard, SessionScore, TopPriorities, HeroTrackMap, LapTimesBar)
│   ├── deep-dive/
│   │   ├── DeepDive.tsx, SpeedAnalysis.tsx, CornerAnalysis.tsx, CustomLayout.tsx
│   │   ├── charts/             (SpeedTrace, DeltaT, BrakeThrottle, TrackMapInteractive,
│   │   │                        TractionCircle, CornerSpeedOverlay, BrakeConsistency)
│   │   └── CornerQuickCard.tsx
│   ├── progress/               (ProgressView, MilestoneTimeline, LapTimeTrend,
│   │                            ConsistencyTrend, CornerHeatmap, SessionBoxPlot)
│   ├── coach/                  (CoachPanel, ChatInterface, ReportSummary,
│   │                            ContextChips, SuggestedQuestions)
│   ├── shared/                 (MetricCard, GradeChip, LapPill, AiInsight, CornerCard, EmptyState)
│   └── onboarding/             (WelcomeScreen, SampleDataCTA)
├── stores/                     (sessionStore, analysisStore, coachStore, uiStore)
├── hooks/                      (existing query hooks + useAnimationFrame, useCanvasChart)
├── lib/                        (api, theme, scales, types)
└── public/sample-session/      (sample Barber data for onboarding)
```

---

## 7. Onboarding

### Empty State (no data uploaded)

```
┌──────────────────────────────────────────┐
│  [Illustration: stylized track outline]  │
│                                          │
│  Analyze your track sessions             │
│  with AI coaching                        │
│                                          │
│  ┌────────────────────────────────────┐  │
│  │  Drag RaceChrono CSV files here   │  │
│  │  or [Browse Files]                │  │
│  │  [How to export from RaceChrono →]│  │
│  └────────────────────────────────────┘  │
│                                          │
│  [Try with sample data]                  │
│                                          │
│  "Upload a session and get your first    │
│   AI coaching report in under 30 seconds"│
└──────────────────────────────────────────┘
```

- **"Try with sample data"** ships a Barber Motorsports Park session — users explore the full app without uploading
- **"How to export from RaceChrono"** link — 3-4 step tutorial
- **No sign-up required** — value before commitment

### Post-Upload Transition

Processing animation with progress steps:
```
Parsing CSV...        ✓
Detecting laps...     ✓
Analyzing corners...  ✓
AI coaching report... ⏳
```
Then transition to Session Dashboard with score revealed via brief animation.

---

## 8. Accessibility & Additional Concerns

### Keyboard Shortcuts (desktop power users)

- Arrow keys: step through corners
- Number keys: jump to corner N
- Space: toggle lap overlay
- Escape: close panels/drawers
- `/`: focus coach chat input
- `?`: show shortcut reference

### Units

Configurable in settings: imperial (mph, ft) / metric (km/h, m). Respected everywhere. Default: imperial (US HPDE audience).

### Data Export

- PDF coaching report
- Shareable session link (future)
- Image export of individual charts
- CSV re-export with computed channels

### Session Notes

Session-level text notes and tags (tire pressure, brake bias, weather). Correlate setup changes with performance in Progress view.

### Offline Capability

Service worker caches last session for offline chart viewing. AI coaching requires connectivity. Progressive enhancement.

---

## 9. What Changes vs Current

| Dimension | Current | Redesign |
|-----------|---------|----------|
| Navigation | 5 tabs + sidebar | 3 views + top bar + drawers |
| Organization | By data type | By user intent |
| AI coaching | Separate tab, manual trigger | Woven throughout, auto-generated |
| Track map | Small cards in Overview | Interactive navigator (Deep Dive) + hero (Dashboard) |
| Charts | Independent SVG D3 | Canvas-backed, synchronized cursor |
| Lap switching | Part of sidebar | Lap pill bar in contextual bar |
| Session switching | Always-visible sidebar list | Left drawer on demand |
| Skill level | Dropdown, affects AI prompt only | Auto-detected, adapts default view depth |
| Component library | Custom Tailwind | shadcn/ui + custom motorsport components |
| Onboarding | Upload or nothing | Sample data + guided empty states |
| Mobile | Responsive shrink | Purpose-built (bottom tabs, swipe, bottom sheet) |

---

## 10. References

- `tasks/competitive-ux-analysis.md` — Full competitive landscape and UX research
- Garmin Catalyst UX philosophy — "Top 3 opportunities", zero-friction, no squiggly lines
- MoTeC i2 "rainbow track map" — delta colored on circuit outline
- Circuit Tools 3 — modern drag-and-drop panel analysis
- Track Titan — AI coaching flows, "Strava for Motorsport"
- VRS — "designed for drivers, not engineers"
- Coach Dave Delta — 4-phase corner model (Braking/Entry/Apex/Exit)
