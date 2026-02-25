# UI Redesign Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Ground-up rebuild of the Next.js frontend from a 5-tab data-type layout to a 3-view coaching-first information architecture with synchronized chart panels, AI coaching woven throughout, and canvas-backed D3 charts.

**Architecture:** New layout shell (TopBar + SessionDrawer + CoachPanel + 3 views) with shadcn/ui component library. Canvas-backed D3 charts synchronized via a shared Zustand `AnalysisStore`. Reuse existing `lib/api.ts`, `lib/types.ts`, all TanStack Query hooks, and the entire FastAPI backend unchanged.

**Tech Stack:** Next.js 16 (App Router), React 19, TypeScript 5, Tailwind v4, shadcn/ui, D3.js 7 (canvas rendering), Zustand 5, TanStack Query 5, Vitest

**Design doc:** `docs/plans/2026-02-24-ui-redesign-design.md`

---

## Phase Overview

| Phase | Name | Tasks | Depends On | Shippable? |
|-------|------|-------|------------|------------|
| 1 | Foundation | 1-5 | — | No (scaffold only) |
| 2 | Navigation Shell | 6-10 | Phase 1 | Yes (empty views navigate) |
| 3 | Session Dashboard | 11-16 | Phase 2 | Yes (coaching-first landing) |
| 4 | Deep Dive: Speed Analysis | 17-23 | Phase 2 | Yes (core analysis) |
| 5 | Deep Dive: Corner Analysis | 24-27 | Phase 4 | Yes (corner drill-in) |
| 6 | Coach Panel | 28-32 | Phase 3 | Yes (AI coaching) |
| 7 | Progress View | 33-37 | Phase 2 | Yes (trends) |
| 8 | Onboarding & Polish | 38-42 | All above | Yes (complete app) |

**Total estimated tasks:** 42
**Reused from current codebase:** `lib/api.ts`, `lib/types.ts`, `lib/formatters.ts`, `lib/constants.ts`, all hooks (`useSession.ts`, `useAnalysis.ts`, `useCoaching.ts`, `useTracks.ts`, `useTrends.ts`)

---

## Phase 1: Foundation

### Task 1: Initialize shadcn/ui and Design Tokens

**Files:**
- Modify: `frontend/package.json` (add shadcn/ui deps)
- Modify: `frontend/app/globals.css` (new design tokens)
- Create: `frontend/lib/design-tokens.ts` (tokens as JS for D3 charts)
- Create: `frontend/components/ui/` (shadcn/ui components as added)

**Step 1: Install shadcn/ui**

```bash
cd frontend
npx shadcn@latest init
```

Select: TypeScript, New York style, CSS variables, `@/components/ui` path, `@/lib/utils` utils path.

**Step 2: Add required shadcn/ui components**

```bash
npx shadcn@latest add button card dialog sheet tabs separator badge tooltip dropdown-menu scroll-area
```

**Step 3: Replace globals.css with new design tokens**

```css
@import "tailwindcss";

:root {
  /* Background hierarchy */
  --bg-base: #0a0c10;
  --bg-surface: #13161c;
  --bg-elevated: #1c1f27;
  --bg-overlay: #252830;

  /* Text hierarchy */
  --text-primary: #e2e4e9;
  --text-secondary: #8b919e;
  --text-muted: #555b67;

  /* Motorsport semantic */
  --color-brake: #ef4444;
  --color-throttle: #22c55e;
  --color-pb: #a855f7;
  --color-optimal: #3b82f6;
  --color-neutral: #f59e0b;

  /* Grades */
  --grade-a: #22c55e;
  --grade-b: #84cc16;
  --grade-c: #f59e0b;
  --grade-d: #f97316;
  --grade-f: #ef4444;

  /* AI content */
  --ai-bg: rgba(99, 102, 241, 0.06);
  --ai-icon: #818cf8;

  /* Interactive */
  --accent: #3b82f6;
  --accent-hover: #2563eb;
  --border: #2a2d35;
  --border-focus: #3b82f6;
  --cursor-line: rgba(255, 255, 255, 0.25);

  /* shadcn/ui integration — map our tokens to shadcn CSS vars */
  --background: var(--bg-base);
  --foreground: var(--text-primary);
  --card: var(--bg-surface);
  --card-foreground: var(--text-primary);
  --popover: var(--bg-elevated);
  --popover-foreground: var(--text-primary);
  --primary: var(--accent);
  --primary-foreground: #ffffff;
  --secondary: var(--bg-surface);
  --secondary-foreground: var(--text-primary);
  --muted: var(--bg-overlay);
  --muted-foreground: var(--text-muted);
  --accent: var(--bg-elevated);
  --accent-foreground: var(--text-primary);
  --destructive: var(--color-brake);
  --destructive-foreground: #ffffff;
  --border: var(--border);
  --input: var(--border);
  --ring: var(--border-focus);
  --radius: 0.5rem;
}

body {
  background-color: var(--bg-base);
  color: var(--text-primary);
  font-family: 'Inter', system-ui, -apple-system, sans-serif;
}
```

**Step 4: Create JS design tokens for D3 charts**

```typescript
// frontend/lib/design-tokens.ts
export const colors = {
  bg: { base: '#0a0c10', surface: '#13161c', elevated: '#1c1f27', overlay: '#252830' },
  text: { primary: '#e2e4e9', secondary: '#8b919e', muted: '#555b67' },
  motorsport: { brake: '#ef4444', throttle: '#22c55e', pb: '#a855f7', optimal: '#3b82f6', neutral: '#f59e0b' },
  grade: { a: '#22c55e', b: '#84cc16', c: '#f59e0b', d: '#f97316', f: '#ef4444' },
  ai: { bg: 'rgba(99, 102, 241, 0.06)', icon: '#818cf8', borderFrom: '#6366f1', borderTo: '#a855f7' },
  lap: ['#58a6ff', '#f97316', '#22c55e', '#e879f9', '#facc15', '#06b6d4', '#f87171', '#a3e635'],
  cursor: 'rgba(255, 255, 255, 0.25)',
  grid: '#1c1f27',
  axis: '#555b67',
} as const;

export const fonts = {
  sans: "'Inter', system-ui, -apple-system, sans-serif",
  mono: "'JetBrains Mono', 'SF Mono', monospace",
} as const;
```

**Step 5: Commit**

```bash
git add frontend/package.json frontend/app/globals.css frontend/lib/design-tokens.ts frontend/components/ui/
git commit -m "feat: initialize shadcn/ui and motorsport design tokens"
```

---

### Task 2: Create New Zustand Stores

**Files:**
- Create: `frontend/src/stores/sessionStore.ts`
- Create: `frontend/src/stores/analysisStore.ts`
- Create: `frontend/src/stores/coachStore.ts`
- Create: `frontend/src/stores/uiStore.ts`
- Create: `frontend/src/stores/index.ts`
- Delete: `frontend/src/store/sessionSlice.ts` (old)
- Delete: `frontend/src/store/uiSlice.ts` (old)
- Test: `frontend/src/stores/__tests__/analysisStore.test.ts`

**Step 1: Write tests for AnalysisStore (the new critical store)**

```typescript
// frontend/src/stores/__tests__/analysisStore.test.ts
import { describe, it, expect, beforeEach } from 'vitest';
import { useAnalysisStore } from '../analysisStore';

describe('AnalysisStore', () => {
  beforeEach(() => {
    useAnalysisStore.setState(useAnalysisStore.getInitialState());
  });

  it('should set cursor distance', () => {
    useAnalysisStore.getState().setCursorDistance(150.5);
    expect(useAnalysisStore.getState().cursorDistance).toBe(150.5);
  });

  it('should clear cursor distance', () => {
    useAnalysisStore.getState().setCursorDistance(150.5);
    useAnalysisStore.getState().setCursorDistance(null);
    expect(useAnalysisStore.getState().cursorDistance).toBeNull();
  });

  it('should select laps', () => {
    useAnalysisStore.getState().selectLaps([3, 7]);
    expect(useAnalysisStore.getState().selectedLaps).toEqual([3, 7]);
  });

  it('should select corner', () => {
    useAnalysisStore.getState().selectCorner('T5');
    expect(useAnalysisStore.getState().selectedCorner).toBe('T5');
  });

  it('should set deep dive mode', () => {
    useAnalysisStore.getState().setMode('corner');
    expect(useAnalysisStore.getState().deepDiveMode).toBe('corner');
  });

  it('should set zoom range', () => {
    useAnalysisStore.getState().setZoom([100, 500]);
    expect(useAnalysisStore.getState().zoomRange).toEqual([100, 500]);
  });

  it('should clear zoom', () => {
    useAnalysisStore.getState().setZoom([100, 500]);
    useAnalysisStore.getState().setZoom(null);
    expect(useAnalysisStore.getState().zoomRange).toBeNull();
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/stores/__tests__/analysisStore.test.ts`
Expected: FAIL — module not found

**Step 3: Implement all four stores**

```typescript
// frontend/src/stores/analysisStore.ts
import { create } from 'zustand';

type DeepDiveMode = 'speed' | 'corner' | 'custom';

interface AnalysisState {
  cursorDistance: number | null;
  selectedLaps: number[];
  selectedCorner: string | null;
  deepDiveMode: DeepDiveMode;
  zoomRange: [number, number] | null;

  setCursorDistance: (d: number | null) => void;
  selectLaps: (laps: number[]) => void;
  selectCorner: (id: string | null) => void;
  setMode: (mode: DeepDiveMode) => void;
  setZoom: (range: [number, number] | null) => void;
}

export const useAnalysisStore = create<AnalysisState>()((set) => ({
  cursorDistance: null,
  selectedLaps: [],
  selectedCorner: null,
  deepDiveMode: 'speed',
  zoomRange: null,

  setCursorDistance: (d) => set({ cursorDistance: d }),
  selectLaps: (laps) => set({ selectedLaps: laps }),
  selectCorner: (id) => set({ selectedCorner: id }),
  setMode: (mode) => set({ deepDiveMode: mode }),
  setZoom: (range) => set({ zoomRange: range }),
}));
```

```typescript
// frontend/src/stores/sessionStore.ts
import { create } from 'zustand';
import type { SessionSummary } from '@/lib/types';

type UploadState = 'idle' | 'uploading' | 'processing' | 'done' | 'error';

interface SessionState {
  activeSessionId: string | null;
  sessions: SessionSummary[];
  uploadState: UploadState;

  setActiveSession: (id: string | null) => void;
  setSessions: (sessions: SessionSummary[]) => void;
  setUploadState: (state: UploadState) => void;
}

export const useSessionStore = create<SessionState>()((set) => ({
  activeSessionId: null,
  sessions: [],
  uploadState: 'idle',

  setActiveSession: (id) => set({ activeSessionId: id }),
  setSessions: (sessions) => set({ sessions }),
  setUploadState: (state) => set({ uploadState: state }),
}));
```

```typescript
// frontend/src/stores/coachStore.ts
import { create } from 'zustand';
import type { CoachingReport, ChatMessage } from '@/lib/types';

interface ContextChip {
  label: string;
  value: string;
}

interface CoachState {
  panelOpen: boolean;
  report: CoachingReport | null;
  chatHistory: ChatMessage[];
  contextChips: ContextChip[];

  togglePanel: () => void;
  setReport: (report: CoachingReport | null) => void;
  addMessage: (msg: ChatMessage) => void;
  clearChat: () => void;
  setContextChips: (chips: ContextChip[]) => void;
}

export const useCoachStore = create<CoachState>()((set) => ({
  panelOpen: false,
  report: null,
  chatHistory: [],
  contextChips: [],

  togglePanel: () => set((s) => ({ panelOpen: !s.panelOpen })),
  setReport: (report) => set({ report }),
  addMessage: (msg) => set((s) => ({ chatHistory: [...s.chatHistory, msg] })),
  clearChat: () => set({ chatHistory: [] }),
  setContextChips: (chips) => set({ contextChips: chips }),
}));
```

```typescript
// frontend/src/stores/uiStore.ts
import { create } from 'zustand';

type SkillLevel = 'novice' | 'intermediate' | 'advanced';
type UnitPreference = 'imperial' | 'metric';
type ActiveView = 'dashboard' | 'deep-dive' | 'progress';

interface UiState {
  activeView: ActiveView;
  skillLevel: SkillLevel;
  sessionDrawerOpen: boolean;
  unitPreference: UnitPreference;

  setActiveView: (view: ActiveView) => void;
  setSkillLevel: (level: SkillLevel) => void;
  toggleSessionDrawer: () => void;
  setUnitPreference: (pref: UnitPreference) => void;
}

export const useUiStore = create<UiState>()((set) => ({
  activeView: 'dashboard',
  skillLevel: 'intermediate',
  sessionDrawerOpen: false,
  unitPreference: 'imperial',

  setActiveView: (view) => set({ activeView: view }),
  setSkillLevel: (level) => set({ skillLevel: level }),
  toggleSessionDrawer: () => set((s) => ({ sessionDrawerOpen: !s.sessionDrawerOpen })),
  setUnitPreference: (pref) => set({ unitPreference: pref }),
}));
```

```typescript
// frontend/src/stores/index.ts
export { useSessionStore } from './sessionStore';
export { useAnalysisStore } from './analysisStore';
export { useCoachStore } from './coachStore';
export { useUiStore } from './uiStore';
```

**Step 4: Run tests**

Run: `cd frontend && npx vitest run src/stores/__tests__/analysisStore.test.ts`
Expected: PASS (all 7 tests)

**Step 5: Commit**

```bash
git add frontend/src/stores/
git commit -m "feat: add new Zustand stores (session, analysis, coach, ui)"
```

---

### Task 3: Canvas Chart Infrastructure

**Files:**
- Create: `frontend/src/hooks/useCanvasChart.ts`
- Create: `frontend/src/hooks/useAnimationFrame.ts`
- Test: `frontend/src/hooks/__tests__/useAnimationFrame.test.ts`

**Step 1: Write useAnimationFrame hook**

```typescript
// frontend/src/hooks/useAnimationFrame.ts
import { useEffect, useRef } from 'react';

export function useAnimationFrame(callback: () => void, deps: unknown[] = []) {
  const rafRef = useRef<number>(0);
  const callbackRef = useRef(callback);
  callbackRef.current = callback;

  useEffect(() => {
    const animate = () => {
      callbackRef.current();
      rafRef.current = requestAnimationFrame(animate);
    };
    rafRef.current = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(rafRef.current);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
}
```

**Step 2: Write useCanvasChart hook**

This is the core infrastructure for canvas-backed D3 charts with synchronized cursor.

```typescript
// frontend/src/hooks/useCanvasChart.ts
import { useRef, useEffect, useCallback, useState } from 'react';
import { useAnalysisStore } from '@/stores';

interface CanvasChartConfig {
  /** Margin around the chart area */
  margin: { top: number; right: number; bottom: number; left: number };
  /** Whether this chart participates in cursor sync */
  syncCursor?: boolean;
}

interface CanvasChartResult {
  /** Ref to attach to the container div */
  containerRef: React.RefObject<HTMLDivElement | null>;
  /** Ref to the main canvas (data layer) */
  canvasRef: React.RefObject<HTMLCanvasElement | null>;
  /** Ref to the overlay canvas (cursor + tooltips) */
  overlayRef: React.RefObject<HTMLCanvasElement | null>;
  /** Current chart dimensions (inner area minus margins) */
  dimensions: { width: number; height: number };
  /** Get 2D context for main canvas */
  getCtx: () => CanvasRenderingContext2D | null;
  /** Get 2D context for overlay canvas */
  getOverlayCtx: () => CanvasRenderingContext2D | null;
}

export function useCanvasChart(config: CanvasChartConfig): CanvasChartResult {
  const { margin, syncCursor = true } = config;
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const overlayRef = useRef<HTMLCanvasElement>(null);
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 });

  // Resize observer
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry) return;
      const { width, height } = entry.contentRect;
      const innerW = Math.max(0, width - margin.left - margin.right);
      const innerH = Math.max(0, height - margin.top - margin.bottom);
      setDimensions({ width: innerW, height: innerH });

      // Size both canvases to container, accounting for device pixel ratio
      const dpr = window.devicePixelRatio || 1;
      [canvasRef.current, overlayRef.current].forEach((canvas) => {
        if (!canvas) return;
        canvas.width = width * dpr;
        canvas.height = height * dpr;
        canvas.style.width = `${width}px`;
        canvas.style.height = `${height}px`;
        const ctx = canvas.getContext('2d');
        ctx?.scale(dpr, dpr);
      });
    });

    observer.observe(container);
    return () => observer.disconnect();
  }, [margin.left, margin.right, margin.top, margin.bottom]);

  // Cursor sync: write cursorDistance on mouse move over overlay
  useEffect(() => {
    if (!syncCursor) return;
    const overlay = overlayRef.current;
    if (!overlay) return;

    const setCursorDistance = useAnalysisStore.getState().setCursorDistance;

    const handleMouseMove = (e: MouseEvent) => {
      const rect = overlay.getBoundingClientRect();
      const x = e.clientX - rect.left - margin.left;
      // Store raw pixel x — the chart component converts to distance via its xScale
      // We emit a custom event with the pixel position for the parent to handle
      overlay.dispatchEvent(new CustomEvent('chart-cursor', { detail: { x, width: dimensions.width } }));
    };

    const handleMouseLeave = () => {
      setCursorDistance(null);
    };

    overlay.addEventListener('mousemove', handleMouseMove);
    overlay.addEventListener('mouseleave', handleMouseLeave);
    return () => {
      overlay.removeEventListener('mousemove', handleMouseMove);
      overlay.removeEventListener('mouseleave', handleMouseLeave);
    };
  }, [syncCursor, margin.left, dimensions.width]);

  const getCtx = useCallback(() => canvasRef.current?.getContext('2d') ?? null, []);
  const getOverlayCtx = useCallback(() => overlayRef.current?.getContext('2d') ?? null, []);

  return { containerRef, canvasRef, overlayRef, dimensions, getCtx, getOverlayCtx };
}
```

**Step 3: Commit**

```bash
git add frontend/src/hooks/useCanvasChart.ts frontend/src/hooks/useAnimationFrame.ts
git commit -m "feat: add canvas chart infrastructure hooks"
```

---

### Task 4: Custom Shared Components

**Files:**
- Create: `frontend/src/components/shared/MetricCard.tsx`
- Create: `frontend/src/components/shared/GradeChip.tsx`
- Create: `frontend/src/components/shared/LapPill.tsx`
- Create: `frontend/src/components/shared/AiInsight.tsx`
- Create: `frontend/src/components/shared/EmptyState.tsx`

**Implementation notes:**

Each component uses shadcn/ui primitives + motorsport design tokens. Key examples:

```typescript
// MetricCard.tsx — the core KPI display component
interface MetricCardProps {
  label: string;
  value: string;
  subtitle?: string;
  delta?: { value: number; label?: string };  // +/- change indicator
  highlight?: 'pb' | 'good' | 'bad';
}
```

```typescript
// GradeChip.tsx — A-F grade pill
interface GradeChipProps {
  grade: string;  // "A" | "B" | "C" | "D" | "F"
  size?: 'sm' | 'md';
}
// Maps grade to --grade-a through --grade-f colors
```

```typescript
// AiInsight.tsx — visually distinct AI content
interface AiInsightProps {
  children: React.ReactNode;
  compact?: boolean;  // inline vs card
}
// Gradient border (indigo→purple), tinted bg, 🤖 prefix
```

```typescript
// LapPill.tsx — toggleable lap selector chip
interface LapPillProps {
  lapNumber: number;
  time: number;
  isPB?: boolean;
  isSelected: boolean;
  color: string;  // from lap palette
  onClick: () => void;
}
```

**Step: Build each component, commit**

```bash
git add frontend/src/components/shared/
git commit -m "feat: add shared components (MetricCard, GradeChip, LapPill, AiInsight, EmptyState)"
```

---

### Task 5: Reuse and Migrate Existing Code

**Files:**
- Keep unchanged: `frontend/src/lib/api.ts`
- Keep unchanged: `frontend/src/lib/types.ts`
- Keep unchanged: `frontend/src/lib/formatters.ts`
- Keep unchanged: `frontend/src/lib/constants.ts`
- Keep unchanged: `frontend/src/hooks/useSession.ts`
- Keep unchanged: `frontend/src/hooks/useAnalysis.ts`
- Keep unchanged: `frontend/src/hooks/useCoaching.ts`
- Keep unchanged: `frontend/src/hooks/useTracks.ts`
- Keep unchanged: `frontend/src/hooks/useTrends.ts`
- Modify: `frontend/src/app/layout.tsx` (update providers, metadata)
- Delete: `frontend/src/store/` (old store directory — replaced by `stores/`)
- Delete: `frontend/src/components/` (old components — rebuilt in new structure)

**Step 1: Update layout.tsx with new providers**

```typescript
// frontend/src/app/layout.tsx
import type { Metadata } from 'next';
import { Providers } from '@/components/Providers';
import './globals.css';

export const metadata: Metadata = {
  title: 'Cataclysm — AI Track Coaching',
  description: 'Post-session telemetry analysis and AI coaching for HPDE drivers',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
```

**Step 2: Update Providers**

```typescript
// frontend/src/components/Providers.tsx
'use client';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useState } from 'react';

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() =>
    new QueryClient({
      defaultOptions: {
        queries: { staleTime: 60_000, refetchOnWindowFocus: false },
      },
    }),
  );

  return (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  );
}
```

**Step 3: Remove old store and components, commit**

```bash
git rm -r frontend/src/store/
git rm -r frontend/src/components/charts/ frontend/src/components/coaching/ frontend/src/components/layout/ frontend/src/components/tabs/ frontend/src/components/ui/
git add frontend/src/app/layout.tsx frontend/src/components/Providers.tsx
git commit -m "refactor: remove old components and stores, update layout for redesign"
```

> **IMPORTANT:** After this commit, the app will not render until Phase 2 provides the new page.tsx and navigation shell. This is expected — we're rebuilding.

---

## Phase 2: Navigation Shell

### Task 6: Main Page with View Router

**Files:**
- Create: `frontend/src/app/page.tsx`
- Create: `frontend/src/components/navigation/ViewRouter.tsx`

**Implementation:**

```typescript
// frontend/src/app/page.tsx
'use client';

import { TopBar } from '@/components/navigation/TopBar';
import { ViewRouter } from '@/components/navigation/ViewRouter';
import { SessionDrawer } from '@/components/navigation/SessionDrawer';
import { CoachPanel } from '@/components/coach/CoachPanel';
import { useCoachStore } from '@/stores';

export default function Home() {
  const panelOpen = useCoachStore((s) => s.panelOpen);

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-[var(--bg-base)]">
      <TopBar />
      <div className="flex flex-1 overflow-hidden">
        <SessionDrawer />
        <main className="flex-1 overflow-y-auto">
          <ViewRouter />
        </main>
        {panelOpen && <CoachPanel />}
      </div>
    </div>
  );
}
```

```typescript
// frontend/src/components/navigation/ViewRouter.tsx
'use client';

import { useUiStore, useSessionStore } from '@/stores';
import { SessionDashboard } from '@/components/dashboard/SessionDashboard';
import { DeepDive } from '@/components/deep-dive/DeepDive';
import { ProgressView } from '@/components/progress/ProgressView';
import { EmptyState } from '@/components/shared/EmptyState';

export function ViewRouter() {
  const activeView = useUiStore((s) => s.activeView);
  const activeSessionId = useSessionStore((s) => s.activeSessionId);

  if (!activeSessionId) return <EmptyState />;

  switch (activeView) {
    case 'dashboard': return <SessionDashboard />;
    case 'deep-dive': return <DeepDive />;
    case 'progress': return <ProgressView />;
    default: return <SessionDashboard />;
  }
}
```

**Commit after building stub components for all views + TopBar.**

---

### Task 7: TopBar Component

**Files:**
- Create: `frontend/src/components/navigation/TopBar.tsx`
- Create: `frontend/src/components/navigation/ContextualBar.tsx`

**TopBar contains:**
- Logo
- 3 view tabs (Dashboard, Deep Dive, Progress) — uses shadcn Tabs
- Upload "+" button
- Coach toggle button (🤖)
- Settings gear icon

**ContextualBar contains:**
- Session selector (track name + date, click opens SessionDrawer)
- Lap pill bar (only in Deep Dive view) — horizontal scroll of LapPill components

```typescript
// TopBar.tsx — key structure
export function TopBar() {
  const { activeView, setActiveView } = useUiStore();
  const { togglePanel, panelOpen } = useCoachStore();
  const { toggleSessionDrawer } = useUiStore();
  const activeSessionId = useSessionStore((s) => s.activeSessionId);

  return (
    <header className="border-b border-[var(--border)]">
      <div className="flex items-center justify-between px-4 h-12 bg-[var(--bg-surface)]">
        {/* Left: Logo */}
        {/* Center: View tabs */}
        {/* Right: Upload, Coach toggle, Settings */}
      </div>
      {activeSessionId && <ContextualBar />}
    </header>
  );
}
```

```typescript
// ContextualBar.tsx — session selector + lap pills
export function ContextualBar() {
  const activeView = useUiStore((s) => s.activeView);
  // Session selector is always shown
  // Lap pills only shown in deep-dive view
  return (
    <div className="flex items-center gap-3 px-4 h-10 bg-[var(--bg-base)] border-b border-[var(--border)]">
      <SessionSelector />
      {activeView === 'deep-dive' && <LapPillBar />}
    </div>
  );
}
```

---

### Task 8: Session Drawer

**Files:**
- Create: `frontend/src/components/navigation/SessionDrawer.tsx`

**Uses shadcn Sheet component** (slide from left). Contains:
- Upload drop zone at top
- Recent sessions list grouped by recency
- Each session card: track name, date, lap count, best time, [Open] button
- "Remove All" action

```typescript
// SessionDrawer.tsx — key structure
export function SessionDrawer() {
  const { sessionDrawerOpen, toggleSessionDrawer } = useUiStore();
  const { data: sessions } = useSessions();

  return (
    <Sheet open={sessionDrawerOpen} onOpenChange={toggleSessionDrawer}>
      <SheetContent side="left" className="w-[380px] bg-[var(--bg-surface)]">
        <SheetHeader>
          <SheetTitle>Sessions</SheetTitle>
        </SheetHeader>
        <FileUploadZone />
        <ScrollArea>
          <SessionList sessions={sessions?.items ?? []} />
        </ScrollArea>
      </SheetContent>
    </Sheet>
  );
}
```

---

### Task 9: Lap Pill Bar

**Files:**
- Create: `frontend/src/components/navigation/LapPillBar.tsx`

**Horizontal scrollable strip of LapPill components.**

```typescript
// LapPillBar.tsx
export function LapPillBar() {
  const activeSessionId = useSessionStore((s) => s.activeSessionId);
  const { selectedLaps, selectLaps } = useAnalysisStore();
  const { data: laps } = useSessionLaps(activeSessionId);
  const { data: sessionData } = useSession(activeSessionId);

  const bestLapNum = /* find lap with min time */;

  const toggleLap = (lapNum: number) => {
    if (selectedLaps.includes(lapNum)) {
      selectLaps(selectedLaps.filter((l) => l !== lapNum));
    } else if (selectedLaps.length < 2) {
      selectLaps([...selectedLaps, lapNum]);
    } else {
      // Replace oldest selection
      selectLaps([selectedLaps[1], lapNum]);
    }
  };

  return (
    <div className="flex gap-1.5 overflow-x-auto scrollbar-thin">
      {laps?.filter(l => l.is_clean).map((lap, i) => (
        <LapPill
          key={lap.lap_number}
          lapNumber={lap.lap_number}
          time={lap.lap_time_s}
          isPB={lap.lap_number === bestLapNum}
          isSelected={selectedLaps.includes(lap.lap_number)}
          color={colors.lap[i % colors.lap.length]}
          onClick={() => toggleLap(lap.lap_number)}
        />
      ))}
    </div>
  );
}
```

---

### Task 10: Mobile Bottom Tabs

**Files:**
- Create: `frontend/src/components/navigation/MobileBottomTabs.tsx`

Only renders on mobile (`lg:hidden`). Four icons: Dashboard, Deep Dive, Progress, Coach.

```typescript
export function MobileBottomTabs() {
  const { activeView, setActiveView } = useUiStore();
  const { togglePanel } = useCoachStore();

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-50 flex h-14 items-center justify-around
                     border-t border-[var(--border)] bg-[var(--bg-surface)] lg:hidden">
      <TabButton icon={LayoutDashboard} label="Dashboard" active={activeView === 'dashboard'}
                 onClick={() => setActiveView('dashboard')} />
      <TabButton icon={Search} label="Dive" active={activeView === 'deep-dive'}
                 onClick={() => setActiveView('deep-dive')} />
      <TabButton icon={TrendingUp} label="Progress" active={activeView === 'progress'}
                 onClick={() => setActiveView('progress')} />
      <TabButton icon={Bot} label="Coach" onClick={togglePanel} />
    </nav>
  );
}
```

**Phase 2 commit:**

```bash
git add frontend/src/components/navigation/ frontend/src/app/page.tsx
git commit -m "feat: add navigation shell (TopBar, SessionDrawer, LapPillBar, MobileBottomTabs)"
```

---

## Phase 3: Session Dashboard

### Task 11: SessionDashboard Layout

**Files:**
- Create: `frontend/src/components/dashboard/SessionDashboard.tsx`

Orchestrates the dashboard layout: hero metrics row → two-column middle → lap times + summary metrics.

### Task 12: SessionScore Component

**Files:**
- Create: `frontend/src/components/dashboard/SessionScore.tsx`

Large circular/radial score display (0-100). Computed from: consistency score (40%), best lap vs optimal (30%), corner grades average (30%). Uses existing `useConsistency` and `useGains` hooks.

### Task 13: TopPriorities Component

**Files:**
- Create: `frontend/src/components/dashboard/TopPriorities.tsx`

Renders top 3 from `CoachingReport.priority_corners`. Each card: corner number, issue (observation), time_cost (impact), tip (suggestion). Color-coded severity. "Show in Deep Dive →" link sets `activeView='deep-dive'` + `selectedCorner` in AnalysisStore.

Uses `useCoachingReport` hook. Auto-triggers report generation via `useAutoReport` hook (new — wraps `useGenerateReport` with auto-fire on mount if no report exists).

### Task 14: HeroTrackMap Component

**Files:**
- Create: `frontend/src/components/dashboard/HeroTrackMap.tsx`

SVG track map (reuse lat/lon path logic from existing `TrackSpeedMap`). Color-coded by corner grade (not speed). Corner labels at apex positions. Non-interactive on Dashboard (just visual hero). Click corner → navigate to Deep Dive + select that corner.

Uses `useCorners` + `useLapData` (best lap) for the track path + corner positions.

### Task 15: LapTimesBar Component (Canvas)

**Files:**
- Create: `frontend/src/components/dashboard/LapTimesBar.tsx`

Canvas-backed bar chart of lap times. PB lap highlighted in purple. AI annotation text above chart (from report summary). Uses `useCanvasChart` hook + `useSessionLaps`.

### Task 16: Dashboard Summary Metrics

**Files:**
- Modify: `frontend/src/components/dashboard/SessionDashboard.tsx` (add bottom row)

Four MetricCards: Consistency Score, Clean Laps, Top Speed, Optimal Lap Time. All from existing hooks.

**Phase 3 commit:**

```bash
git add frontend/src/components/dashboard/
git commit -m "feat: add Session Dashboard (score, priorities, hero map, lap times)"
```

---

## Phase 4: Deep Dive — Speed Analysis

### Task 17: DeepDive Layout + Sub-mode Switcher

**Files:**
- Create: `frontend/src/components/deep-dive/DeepDive.tsx`
- Create: `frontend/src/components/deep-dive/SpeedAnalysis.tsx`

DeepDive renders a segmented control (shadcn Tabs with "segment" style) for Speed/Corner/Custom modes. SpeedAnalysis is the default sub-mode layout: left column (65%, three stacked charts) + right column (35%, track map + corner quick card).

### Task 18: Canvas SpeedTrace

**Files:**
- Create: `frontend/src/components/deep-dive/charts/SpeedTrace.tsx`

**The most critical chart.** Canvas-backed, distance X-axis, multi-lap overlay.

Key implementation details:
- Uses `useCanvasChart` hook for canvas lifecycle
- Uses `useMultiLapData` for selected laps' data
- Uses `useCorners` for corner zone rects (semi-transparent background spans)
- Subscribes to `analysisStore.cursorDistance` for cursor line rendering
- On `chart-cursor` custom event: converts pixel X → distance via D3 `xScale.invert()`, calls `setCursorDistance()`
- AI annotation overlays: positioned at specific distances from `useCoachAnnotations` (new hook)
- Zoom via D3 zoom behavior on overlay canvas (X-axis only)

```typescript
// SpeedTrace.tsx — core rendering pattern
export function SpeedTrace() {
  const { containerRef, canvasRef, overlayRef, dimensions, getCtx, getOverlayCtx } = useCanvasChart({
    margin: { top: 20, right: 16, bottom: 30, left: 50 },
    syncCursor: true,
  });
  const selectedLaps = useAnalysisStore((s) => s.selectedLaps);
  const cursorDistance = useAnalysisStore((s) => s.cursorDistance);
  const { data: lapDataList } = useMultiLapData(activeSessionId, selectedLaps);
  const { data: corners } = useCorners(activeSessionId);

  // Build D3 scales
  const xScale = useMemo(() => /* d3.scaleLinear distance domain */, [lapDataList, dimensions]);
  const yScale = useMemo(() => /* d3.scaleLinear speed domain */, [lapDataList, dimensions]);

  // Render data layer (on data/dimension change)
  useEffect(() => {
    const ctx = getCtx();
    if (!ctx || !lapDataList.length) return;
    // Clear, draw corner zones, draw speed lines, draw axes
  }, [lapDataList, dimensions, corners]);

  // Render cursor layer (on cursor change — RAF throttled)
  useAnimationFrame(() => {
    const ctx = getOverlayCtx();
    if (!ctx) return;
    ctx.clearRect(0, 0, /* full canvas */);
    if (cursorDistance !== null) {
      // Draw vertical cursor line + tooltip
    }
  }, [cursorDistance]);

  // Handle cursor pixel → distance conversion
  useEffect(() => {
    overlayRef.current?.addEventListener('chart-cursor', (e) => {
      const { x } = (e as CustomEvent).detail;
      const distance = xScale.invert(x);
      useAnalysisStore.getState().setCursorDistance(distance);
    });
  }, [xScale]);

  return (
    <div ref={containerRef} className="relative h-full w-full">
      <canvas ref={canvasRef} className="absolute inset-0" />
      <canvas ref={overlayRef} className="absolute inset-0" />
    </div>
  );
}
```

---

### Task 19: Canvas DeltaT Chart

**Files:**
- Create: `frontend/src/components/deep-dive/charts/DeltaT.tsx`

Same canvas pattern as SpeedTrace. Green above zero line (gaining), red below (losing). Shared distance X-axis, subscribes to same `cursorDistance`. Uses `useDelta` hook.

### Task 20: Canvas BrakeThrottle Chart

**Files:**
- Create: `frontend/src/components/deep-dive/charts/BrakeThrottle.tsx`

Longitudinal g-force by distance. Red fill for braking, green fill for throttle. Corner zones overlaid. Shared cursor.

### Task 21: Interactive Track Map (SVG)

**Files:**
- Create: `frontend/src/components/deep-dive/charts/TrackMapInteractive.tsx`

**SVG-based** (not canvas — needs DOM events on corner hotspots).

Key behaviors:
- Draw track path from lat/lon data
- Color path segments by delta-T (rainbow map: green→red gradient)
- Corner labels at apex positions with GradeChip badges
- Animated cursor dot at position derived from `cursorDistance` (interpolate on path)
- Click corner → `selectCorner(id)` in AnalysisStore → other panels react
- Highlight selected corner with pulsing ring

```typescript
// TrackMapInteractive.tsx
// On cursorDistance change: interpolate to find lat/lon at that distance
// Move a <circle> element to that position
// On corner click: set selectedCorner, dispatch navigation
```

### Task 22: Corner Quick Card

**Files:**
- Create: `frontend/src/components/deep-dive/CornerQuickCard.tsx`

Floating card in right column, appears when `selectedCorner` is set. Shows: corner name, grade, KPIs (entry/apex/exit speed, brake point, throttle commit), AI coaching tip, "vs best" delta indicators. "Open in Corner Analysis →" link switches sub-mode.

### Task 23: Cursor Sync Integration Test

**Files:**
- Test: `frontend/src/components/deep-dive/__tests__/cursorSync.test.ts`

Integration test verifying that setting `cursorDistance` in AnalysisStore is reflected across all chart components. Uses Vitest + Testing Library to render SpeedAnalysis and verify cursor state propagation.

**Phase 4 commit:**

```bash
git add frontend/src/components/deep-dive/
git commit -m "feat: add Deep Dive speed analysis with synchronized canvas charts"
```

---

## Phase 5: Deep Dive — Corner Analysis

### Task 24: CornerAnalysis Layout

**Files:**
- Create: `frontend/src/components/deep-dive/CornerAnalysis.tsx`

Two-column top (large track map + corner detail panel), two-column bottom (corner speed overlay + brake consistency). Corner cycling via arrow keys and map clicks.

### Task 25: Corner Detail Panel

**Files:**
- Create: `frontend/src/components/deep-dive/CornerDetailPanel.tsx`

Full corner information: name, direction, grade, all KPIs, "vs best lap" deltas (green/red inline indicators), AI coaching tip (AiInsight component). Subscribes to `selectedCorner` from AnalysisStore.

### Task 26: Corner Speed Overlay (Canvas)

**Files:**
- Create: `frontend/src/components/deep-dive/charts/CornerSpeedOverlay.tsx`

Canvas chart showing speed traces for all clean laps, zoomed to selected corner's entry→exit distance range. Best lap highlighted, comparison lap dashed. Brake/throttle traces underneath.

### Task 27: Brake Consistency Chart (Canvas)

**Files:**
- Create: `frontend/src/components/deep-dive/charts/BrakeConsistency.tsx`

Scatter plot of brake point distance for each lap at the selected corner. Shows variance visually — tight cluster = consistent, spread = inconsistent. Canvas-backed.

**Phase 5 commit:**

```bash
git add frontend/src/components/deep-dive/CornerAnalysis.tsx frontend/src/components/deep-dive/CornerDetailPanel.tsx
git add frontend/src/components/deep-dive/charts/CornerSpeedOverlay.tsx frontend/src/components/deep-dive/charts/BrakeConsistency.tsx
git commit -m "feat: add Deep Dive corner analysis sub-mode"
```

---

## Phase 6: Coach Panel

### Task 28: CoachPanel Layout

**Files:**
- Create: `frontend/src/components/coach/CoachPanel.tsx`

Right-side panel, 400px wide. Pushes main content left. Contains: ContextChips, ReportSummary, SuggestedQuestions, ChatInterface. Uses shadcn Sheet (side="right") on mobile.

### Task 29: Context Chips

**Files:**
- Create: `frontend/src/components/coach/ContextChips.tsx`

Auto-updates from AnalysisStore state. Shows current session, selected laps, selected corner. Informs the AI about what the user is looking at.

```typescript
// Subscribes to multiple stores to build context
export function ContextChips() {
  const activeSessionId = useSessionStore((s) => s.activeSessionId);
  const selectedLaps = useAnalysisStore((s) => s.selectedLaps);
  const selectedCorner = useAnalysisStore((s) => s.selectedCorner);
  // Build chips array, update CoachStore
}
```

### Task 30: Report Summary

**Files:**
- Create: `frontend/src/components/coach/ReportSummary.tsx`

Collapsed view of coaching report: overall grade, strongest area, focus areas. Expandable to full corner-by-corner grades. Uses `useCoachingReport`.

### Task 31: Suggested Questions

**Files:**
- Create: `frontend/src/components/coach/SuggestedQuestions.tsx`

Context-sensitive question chips. Changes based on: current view, selected corner, selected laps. Clicking a question sends it to the chat.

### Task 32: Chat Interface

**Files:**
- Create: `frontend/src/components/coach/ChatInterface.tsx`

Reuse existing chat logic (sends to `/api/coaching/{id}/chat` endpoint). Message history from `CoachStore.chatHistory`. Input field with send button. Messages styled differently for user vs AI (AI messages use AiInsight treatment).

**Phase 6 commit:**

```bash
git add frontend/src/components/coach/
git commit -m "feat: add persistent Coach panel with context-aware chat"
```

---

## Phase 7: Progress View

### Task 33: ProgressView Layout

**Files:**
- Create: `frontend/src/components/progress/ProgressView.tsx`

Hero metrics → AI progress summary → milestone timeline → two-column trends → corner heatmap → box plots. Uses `useTrends` and `useMilestones` hooks.

### Task 34: Milestone Timeline

**Files:**
- Create: `frontend/src/components/progress/MilestoneTimeline.tsx`

Horizontal SVG timeline with session markers and milestone events. Auto-detected milestones from `useMilestones` hook.

### Task 35: Trend Charts (Canvas)

**Files:**
- Create: `frontend/src/components/progress/LapTimeTrend.tsx`
- Create: `frontend/src/components/progress/ConsistencyTrend.tsx`

Canvas charts: Lap time trend (3 lines: best, top-3 avg, optimal) and consistency score progression. AI annotation overlay for plateau detection.

### Task 36: Corner Heatmap (Canvas)

**Files:**
- Create: `frontend/src/components/progress/CornerHeatmap.tsx`

Sessions × corners 2D heatmap. Metric selector (min speed / brake consistency / grade). Color scale from dark → bright green. Clickable cells link to Deep Dive.

### Task 37: Session Box Plot (Canvas)

**Files:**
- Create: `frontend/src/components/progress/SessionBoxPlot.tsx`

Lap time distribution box-and-whisker plots per session. Shows tightening distribution as consistency improves.

**Phase 7 commit:**

```bash
git add frontend/src/components/progress/
git commit -m "feat: add Progress view with trends, milestones, and corner heatmap"
```

---

## Phase 8: Onboarding & Polish

### Task 38: Empty State / Welcome Screen

**Files:**
- Modify: `frontend/src/components/shared/EmptyState.tsx` (full implementation)

Large centered upload zone with illustration placeholder, "Try with sample data" button, "How to export from RaceChrono" link, value proposition copy.

### Task 39: Sample Session Data

**Files:**
- Create: `frontend/public/sample-session/barber_sample.csv`

Include a real Barber Motorsports Park session (or synthetic one from test fixtures). The "Try with sample data" button loads this via the upload endpoint.

### Task 40: Post-Upload Processing Animation

**Files:**
- Create: `frontend/src/components/shared/ProcessingOverlay.tsx`

Step-by-step progress indicator: "Parsing CSV ✓", "Detecting laps ✓", "Analyzing corners ✓", "AI coaching ⏳". Subscribes to `sessionStore.uploadState`.

### Task 41: Keyboard Shortcuts

**Files:**
- Create: `frontend/src/hooks/useKeyboardShortcuts.ts`

Global keyboard event handler:
- `1/2/3`: Switch views (Dashboard/Deep Dive/Progress)
- `←/→`: Cycle corners (in Deep Dive)
- `Space`: Toggle lap overlay
- `Escape`: Close drawers/panels
- `/`: Focus coach chat input
- `?`: Show shortcut reference (tooltip)

### Task 42: Responsive Polish & Final QA

**Files:**
- All component files (responsive class adjustments)

**Checklist:**
- [ ] Mobile bottom tabs work on all views
- [ ] Session drawer renders correctly on mobile (full-screen)
- [ ] Coach panel renders as bottom sheet on mobile
- [ ] Dashboard stacks to single column on mobile
- [ ] Deep Dive shows single chart with swipe on mobile
- [ ] All charts handle resize correctly (ResizeObserver)
- [ ] Drag-and-drop CSV upload works on full viewport
- [ ] No console errors in any view
- [ ] Color contrast meets WCAG 4.5:1 minimum
- [ ] Lap times display in monospace font
- [ ] AI content has gradient border treatment everywhere
- [ ] Empty states render for all views when no data

**Phase 8 commit:**

```bash
git add .
git commit -m "feat: add onboarding, keyboard shortcuts, and responsive polish"
```

---

## Backend Changes Required

### New Endpoints Needed

These are required for the redesign but are **backend tasks, not frontend**:

1. **`GET /api/coaching/{id}/annotations`** — Returns AI insights positioned at specific track distances. Derived from the coaching report but formatted for chart overlay.

2. **`POST /api/coaching/{id}/chat`** — Chat endpoint for follow-up questions. Accepts message + context (current corner, laps being viewed). Returns AI response. *(May already exist — check backend routes.)*

3. **`GET /api/sessions/{id}/score`** — Returns session score (0-100) computed from consistency, best vs optimal, corner grades. *(Could also be computed frontend-side from existing data.)*

4. **`GET /api/sessions/{id}/skill-detection`** — Returns detected skill level based on telemetry patterns. *(Could also be computed frontend-side.)*

---

## Testing Strategy

Per CLAUDE.md: every new module gets a companion test file.

| Category | What to Test | Framework |
|----------|-------------|-----------|
| Stores | State transitions, actions, selectors | Vitest + Zustand |
| Hooks | Data fetching, cursor sync, animation frame | Vitest + Testing Library |
| Components | Render without crash, props, interactions | Vitest + Testing Library |
| Charts | Canvas rendering calls, cursor events | Vitest + mock canvas |
| Integration | Cursor sync across panels, view navigation | Vitest + Testing Library |

**Mocking strategy:**
- Mock `canvas.getContext('2d')` for canvas chart tests
- Mock TanStack Query with `@tanstack/react-query` test utils
- Mock Zustand stores with `useStore.setState()` in tests

---

## Definition of Done

Per CLAUDE.md quality gates:

1. All components render without errors
2. Cursor synchronization works across all Deep Dive panels at 60fps
3. Coach panel context chips update on navigation
4. All views responsive (mobile + desktop)
5. Keyboard shortcuts functional
6. Sample data onboarding works end-to-end
7. `npm run build` succeeds (no TypeScript errors)
8. All Vitest tests pass
9. QA via Playwright MCP on all views
