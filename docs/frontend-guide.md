# Frontend Guide

The frontend is a Next.js 16 application using React 19, TypeScript, Tailwind CSS 4, and D3.js for data visualization.

## Tech Stack

| Technology | Version | Purpose |
|-----------|---------|---------|
| Next.js | 16.1.6 | React meta-framework (App Router) |
| React | 19.2.3 | UI library |
| TypeScript | 5 | Type safety |
| Tailwind CSS | 4 | Utility-first styling |
| D3.js | 7.9 | Data visualization |
| Zustand | 5.0 | Client-side UI state |
| TanStack Query | 5.90 | API data fetching & caching |
| NextAuth.js | 5.0 beta | Authentication (Google OAuth) |
| Radix UI | 1.4 | Accessible UI primitives |
| Three.js | 0.183 | 3D visualization |
| Lucide React | 0.575 | Icon library |

## Page Structure

The app uses Next.js App Router. After authentication, it functions as an SPA with a `ViewRouter` component switching between 4 main views.

| Route | Purpose |
|-------|---------|
| `/` | Main dashboard — session drawer, top bar, and view routing |
| `/analysis/[id]` | Redirect: sets active session, navigates to `/` |
| `/compare/[id]` | Lap comparison page |
| `/share/[token]` | Public shared session view |
| `/org/[slug]` | Organization (HPDE club) dashboard |
| `/instructor` | Instructor student management |
| `/api/auth/[...nextauth]` | NextAuth.js auth routes |

## Views

All analysis happens on `/` via `ViewRouter`:

### Dashboard
Overview of the current session with metrics cards, track map, and charts.

**Components**: `SessionDashboard`, `SessionScore`, `HeroTrackMap`, `LapTimesBar`, `TimeGainedChart`, `SkillRadar`, `TopPriorities`, `GPSQualityPanel`, `WeatherPanel`, `DegradationAlerts`, `ShareButton`

**Session Score formula**: 40% consistency + 30% optimal line + 30% corner grades

### Deep Dive
Detailed telemetry analysis with 5 sub-tabs:

| Tab | Description | Key Components |
|-----|-------------|----------------|
| Speed | Speed trace with multi-lap overlay | `SpeedTrace` (D3), `DeltaT`, `BrakeThrottle` |
| Corners | Per-corner data and track map | `CornerAnalysis`, `CornerDetailPanel`, `CornerSpeedOverlay` |
| Sectors | Mini-sector breakdown | `MiniSectorMap` |
| Custom | User-configurable charts | — |
| Replay | Animated lap playback | `LapReplay`, speed gauge, track map |

### Progress
Multi-session trends and historical analysis.

**Components**: `LapTimeTrend`, `ConsistencyTrend`, `CornerHeatmap`, `SessionBoxPlot`, `MilestoneTimeline`

### Debrief
Pit lane coaching summary with AI-generated insights.

## State Management

### Zustand Stores

Four stores manage client-side UI state:

**`sessionStore`** — Active session and upload state
```typescript
{
  activeSessionId: string | null
  sessions: SessionSummary[]
  uploadState: 'idle' | 'uploading' | 'processing' | 'done' | 'error'
  uploadProgress: number  // 0-60 = upload bytes, 60-100 = server processing
}
```

**`analysisStore`** — Deep dive interaction state
```typescript
{
  cursorDistance: number | null    // Crosshair position synced across charts
  selectedLaps: number[]          // Laps selected for overlay
  selectedCorner: string | null   // Active corner in detail panel
  deepDiveMode: 'speed' | 'corner' | 'sectors' | 'custom' | 'replay'
  zoomRange: [number, number] | null
}
```

**`coachStore`** — AI coach panel
```typescript
{
  panelOpen: boolean
  report: CoachingReport | null
  chatHistory: ChatMessage[]
  isWaiting: boolean
  pendingQuestion: string | null
}
```

**`uiStore`** — Global UI preferences
```typescript
{
  activeView: 'dashboard' | 'deep-dive' | 'progress' | 'debrief'
  skillLevel: 'novice' | 'intermediate' | 'advanced'
  sessionDrawerOpen: boolean
  settingsPanelOpen: boolean
  unitPreference: 'imperial' | 'metric'
  toasts: Toast[]
}
```

### TanStack Query

API data fetching with automatic caching:
- **Stale time**: 60 seconds (default)
- **Polling**: Reports poll every 2s while `status === "generating"`
- **Cache invalidation**: Mutations call `queryClient.invalidateQueries()` to refetch
- **Query keys**: Namespaced by endpoint and session ID

## API Client (`lib/api.ts`)

All API calls use a generic `fetchApi<T>()` helper:

```typescript
async function fetchApi<T>(path: string, options?: RequestInit): Promise<T>
```

**Key patterns**:
- API base is empty string (requests go to same origin, proxied to backend)
- File uploads use XHR (not fetch) for progress tracking
- Some endpoints return `{ data: {...} }` envelope — client unwraps automatically
- Query parameters encoded with `URLSearchParams`

**Organized by domain**:
- `listSessions()`, `getSession()`, `uploadSessions()`, `deleteSession()`
- `getCorners()`, `getAllLapCorners()`, `getDelta()`, `getConsistency()`
- `generateCoachingReport()`, `getCoachingReport()`, `downloadPdfReport()`
- `getTrends()`, `getMilestones()`
- `getCornerLeaderboard()`, `getCornerKings()`
- `createShareLink()`, `getShareMetadata()`

## Custom Hooks (`hooks/`)

React hooks wrapping TanStack Query:

| Hook | API Call | Notes |
|------|----------|-------|
| `useSessions()` | `GET /api/sessions` | Session list for drawer |
| `useSession(id)` | `GET /api/sessions/{id}` | Single session details |
| `useSessionLaps(id)` | `GET /api/sessions/{id}/laps` | Lap summaries |
| `useLapData(id, lap)` | `GET /api/sessions/{id}/laps/{lap}/data` | Single lap telemetry |
| `useMultiLapData(id, laps)` | Batch fetch | Multiple laps for overlay |
| `useCorners(id)` | `GET /api/sessions/{id}/corners` | Best lap corners |
| `useAllLapCorners(id)` | `GET /api/sessions/{id}/corners/all-laps` | All lap corners |
| `useConsistency(id)` | `GET /api/sessions/{id}/consistency` | Consistency metrics |
| `useDelta(id, ref, comp)` | `GET /api/sessions/{id}/delta` | Delta between two laps |
| `useGains(id)` | `GET /api/sessions/{id}/gains` | Time gain estimates |
| `useMiniSectors(id, n, lap)` | `GET /api/sessions/{id}/mini-sectors` | Sector breakdown |
| `useCoachingReport(id)` | `GET /api/coaching/{id}/report` | Polls while generating |
| `useTrends(track)` | `GET /api/trends/{track}` | Multi-session trends |
| `useLeaderboard(track, corner)` | `GET /api/leaderboards/...` | Corner rankings |
| `useAchievements()` | `GET /api/achievements` | Achievement list |
| `useEquipment(id)` | `GET /api/equipment/{id}/equipment` | Equipment profile |

## Chart Architecture

Charts use D3.js with custom implementations:

**Canvas-rendered** (performance-critical):
- `SpeedTrace` — Multi-lap speed overlay with crosshair
- `ReplayTrackMap` — Animated playback visualization

**SVG-rendered** (interactive):
- `TrackMapInteractive` — 2D GPS track with corner markers
- `CornerSpeedOverlay` — Speed scatter per corner
- `DeltaT` — Time delta chart
- `BrakeThrottle` — Brake/throttle traces
- `MiniSectorMap` — Sector heatmap

**Progress charts** (D3):
- `LapTimeTrend` — Best lap trend line
- `ConsistencyTrend` — Consistency score over time
- `CornerHeatmap` — Color-coded corner speeds
- `SessionBoxPlot` — Lap time distribution

### Cursor Synchronization

The `cursorDistance` value in `analysisStore` syncs crosshairs across all charts in the deep dive view. When the user hovers on any chart, all others update to show the same distance point on track.

## Component Organization

```
frontend/src/components/
├── dashboard/          # Dashboard view components
│   ├── SessionDashboard.tsx
│   ├── SessionScore.tsx
│   ├── HeroTrackMap.tsx
│   ├── LapTimesBar.tsx
│   ├── TimeGainedChart.tsx
│   ├── SkillRadar.tsx
│   └── ...
├── deep-dive/          # Deep dive analysis
│   ├── SpeedAnalysis.tsx
│   ├── CornerAnalysis.tsx
│   ├── CornerDetailPanel.tsx
│   └── charts/
│       ├── SpeedTrace.tsx
│       ├── TrackMapInteractive.tsx
│       ├── DeltaT.tsx
│       ├── BrakeThrottle.tsx
│       └── MiniSectorMap.tsx
├── progress/           # Progress/trends view
│   ├── ProgressView.tsx
│   ├── LapTimeTrend.tsx
│   ├── ConsistencyTrend.tsx
│   ├── CornerHeatmap.tsx
│   └── SessionBoxPlot.tsx
├── coach/              # AI coaching panel
│   ├── CoachPanel.tsx
│   ├── ReportSummary.tsx
│   ├── ChatInterface.tsx
│   └── SuggestedQuestions.tsx
├── comparison/         # Lap comparison
├── equipment/          # Equipment profiles
├── leaderboard/        # Rankings
├── instructor/         # Instructor features
├── org/                # Organization management
├── replay/             # Lap replay
├── wrapped/            # Year-in-review
├── shared/             # Shared UI components
│   ├── MetricCard.tsx
│   ├── EmptyState.tsx
│   ├── WelcomeScreen.tsx
│   ├── CircularProgress.tsx
│   ├── RadarChart.tsx
│   ├── GradeChip.tsx
│   └── SettingsPanel.tsx
└── ui/                 # Radix UI + shadcn/ui primitives
    ├── button.tsx
    ├── card.tsx
    ├── dialog.tsx
    ├── dropdown-menu.tsx
    ├── sheet.tsx
    ├── tabs.tsx
    └── ...
```

## Authentication

NextAuth.js v5 with Google OAuth:

- **Provider**: Google OAuth (optional dev bypass with `DEV_AUTH_BYPASS=true`)
- **Session strategy**: JWT (stateless, no DB sessions)
- **Middleware**: Protects all routes except `/api/auth/*` and Next.js internals
- **Dev mode**: When no OAuth credentials are set, all requests pass through

## Error Handling

- `ViewErrorBoundary` — Wraps each view, keyed by `sessionId` to reset on session switch
- `ChartErrorBoundary` — Individual chart crash recovery
- `EmptyState` — Displayed when no data is available
- `WelcomeScreen` — Shown before any session is uploaded
- Toast notifications for upload errors, API failures, etc.

## Mobile Support

- `SessionDrawer` collapses on mobile viewports
- `MobileBottomTabs` provides tab navigation on small screens
- Tailwind responsive breakpoints used throughout
- Charts adapt to available width
