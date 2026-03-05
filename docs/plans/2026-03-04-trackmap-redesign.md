# Track Map Redesign Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the 3-way mode toggle (2D/SAT/3D) with a 2D/3D view toggle + independent SAT overlay toggle, adding 3D satellite terrain support via Mapbox GL.

**Architecture:** `TrackMapContainer` gets new state (`viewMode` + `satEnabled`) and renders one of 4 combinations. `TrackMapSatellite` gains `terrain` and `exaggeration` props to handle both flat satellite (2D+SAT) and 3D terrain (3D+SAT). No new components needed.

**Tech Stack:** React, Mapbox GL v3 (terrain API), react-map-gl v8, Three.js/R3F (unchanged)

**Design doc:** `docs/plans/2026-03-04-trackmap-redesign-design.md`

---

### Task 1: Update TrackMapContainer — New Toggle UI and State

**Files:**
- Modify: `frontend/src/components/deep-dive/charts/TrackMapContainer.tsx`

**Step 1: Replace state and types**

Replace the `MapMode` type and `MODE_LABELS` array with new state model. The container now manages two independent toggles: `viewMode` ('2d' | '3d') and `satEnabled` (boolean), plus an `exaggeration` number for the 3D terrain slider.

```tsx
'use client';

import { useState, useEffect, useCallback } from 'react';
import dynamic from 'next/dynamic';
import { Maximize2, Minimize2, Satellite } from 'lucide-react';
import { TrackMapInteractive } from './TrackMapInteractive';
import { cn } from '@/lib/utils';

type ViewMode = '2d' | '3d';

const TrackMap3D = dynamic(
  () => import('./TrackMap3D').then((mod) => mod.TrackMap3D),
  { ssr: false },
);

const TrackMapSatellite = dynamic(
  () => import('./TrackMapSatellite').then((mod) => mod.TrackMapSatellite),
  { ssr: false },
);

interface TrackMapContainerProps {
  sessionId: string;
}

const VIEW_MODES: { mode: ViewMode; label: string }[] = [
  { mode: '2d', label: '2D' },
  { mode: '3d', label: '3D' },
];

const EXAGGERATION_MIN = 1.0;
const EXAGGERATION_MAX = 4.0;
const EXAGGERATION_STEP = 0.5;
const EXAGGERATION_DEFAULT = 2.0;

export function TrackMapContainer({ sessionId }: TrackMapContainerProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('2d');
  const [satEnabled, setSatEnabled] = useState(false);
  const [exaggeration, setExaggeration] = useState(EXAGGERATION_DEFAULT);
  const [fullscreen, setFullscreen] = useState(false);

  const toggleFullscreen = useCallback(() => setFullscreen((f) => !f), []);
  const toggleSat = useCallback(() => setSatEnabled((s) => !s), []);

  useEffect(() => {
    if (!fullscreen) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setFullscreen(false);
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [fullscreen]);

  // Render the appropriate map view based on viewMode + satEnabled
  const mapContent = (() => {
    if (satEnabled) {
      // Both 2D+SAT and 3D+SAT use TrackMapSatellite with different terrain prop
      return (
        <TrackMapSatellite
          sessionId={sessionId}
          terrain={viewMode === '3d'}
          exaggeration={exaggeration}
        />
      );
    }
    // Non-satellite views
    if (viewMode === '3d') return <TrackMap3D sessionId={sessionId} />;
    return <TrackMapInteractive sessionId={sessionId} />;
  })();

  const showExaggerationSlider = viewMode === '3d' && satEnabled;

  const controls = (
    <div className="absolute right-2 top-2 z-20 flex items-center gap-1">
      {/* 2D / 3D toggle */}
      <div className="flex overflow-hidden rounded-md border border-[var(--cata-border)] bg-[var(--bg-elevated)]">
        {VIEW_MODES.map(({ mode, label }) => (
          <button
            key={mode}
            onClick={() => setViewMode(mode)}
            className={cn(
              'px-2 py-1 text-[10px] font-semibold uppercase tracking-wider transition-colors',
              viewMode === mode
                ? 'bg-[var(--bg-overlay)] text-[var(--text-primary)]'
                : 'text-[var(--text-muted)] hover:text-[var(--text-secondary)]',
            )}
          >
            {label}
          </button>
        ))}
      </div>

      {/* SAT toggle */}
      <button
        onClick={toggleSat}
        className={cn(
          'flex items-center gap-1 rounded-md border px-2 py-1 text-[10px] font-semibold uppercase tracking-wider transition-colors',
          satEnabled
            ? 'border-[var(--motorsport-optimal)] bg-[var(--bg-overlay)] text-[var(--text-primary)]'
            : 'border-[var(--cata-border)] bg-[var(--bg-elevated)] text-[var(--text-muted)] hover:text-[var(--text-secondary)]',
        )}
        title="Toggle satellite overlay"
      >
        <Satellite size={12} />
        SAT
      </button>

      {/* Exaggeration slider — only in 3D+SAT */}
      {showExaggerationSlider && (
        <div className="flex items-center gap-1 rounded-md border border-[var(--cata-border)] bg-[var(--bg-elevated)] px-2 py-1">
          <span className="text-[9px] text-[var(--text-muted)]">{exaggeration.toFixed(1)}×</span>
          <input
            type="range"
            min={EXAGGERATION_MIN}
            max={EXAGGERATION_MAX}
            step={EXAGGERATION_STEP}
            value={exaggeration}
            onChange={(e) => setExaggeration(Number(e.target.value))}
            className="h-1 w-16 cursor-pointer accent-[var(--motorsport-optimal)]"
            title={`Terrain exaggeration: ${exaggeration.toFixed(1)}×`}
          />
        </div>
      )}

      {/* Fullscreen */}
      <button
        onClick={toggleFullscreen}
        className="flex items-center justify-center rounded-md border border-[var(--cata-border)] bg-[var(--bg-elevated)] p-1 text-[var(--text-muted)] transition-colors hover:text-[var(--text-primary)]"
        title={fullscreen ? 'Exit fullscreen (Esc)' : 'Fullscreen'}
      >
        {fullscreen ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
      </button>
    </div>
  );

  if (fullscreen) {
    return (
      <>
        <div className="h-full" />
        <div className="fixed inset-0 z-50 bg-[var(--bg-base)]">
          <div className="relative h-full w-full">
            {controls}
            {mapContent}
          </div>
        </div>
      </>
    );
  }

  return (
    <div className="relative h-full">
      {controls}
      {mapContent}
    </div>
  );
}
```

**Step 2: Verify the dev server compiles**

Run: `cd frontend && npx next dev` (check for TypeScript errors — `TrackMapSatellite` doesn't accept `terrain`/`exaggeration` props yet, so there will be type errors. That's expected; we fix it in Task 2.)

**Step 3: Commit**

```bash
git add frontend/src/components/deep-dive/charts/TrackMapContainer.tsx
git commit -m "refactor: replace 3-way map mode with 2D/3D toggle + SAT overlay"
```

---

### Task 2: Update TrackMapSatellite — Accept terrain and exaggeration props

**Files:**
- Modify: `frontend/src/components/deep-dive/charts/TrackMapSatellite.tsx`

**Step 1: Update interface and add terrain logic**

The component needs three changes:
1. Accept `terrain` (boolean) and `exaggeration` (number) props
2. When `terrain=false`: use `pitch: 0` (flat top-down for 2D+SAT)
3. When `terrain=true`: use `pitch: 45`, auto-bearing from GPS data, enable Mapbox terrain DEM

Update the interface:

```tsx
interface TrackMapSatelliteProps {
  sessionId: string;
  terrain?: boolean;
  exaggeration?: number;
}
```

Update the component signature:

```tsx
export function TrackMapSatellite({
  sessionId,
  terrain = false,
  exaggeration = 2.0,
}: TrackMapSatelliteProps) {
```

**Step 2: Add auto-bearing computation**

Add this helper function above the component (after `buildCornerLabels`):

```tsx
/** Compute initial bearing from S/F straight direction */
function computeAutoBearing(lapData: LapData): number {
  const n = Math.min(20, lapData.lat.length - 1);
  if (n < 1) return 0;
  const dx = lapData.lon[n] - lapData.lon[0];
  const dy = lapData.lat[n] - lapData.lat[0];
  return (Math.atan2(dx, dy) * 180) / Math.PI;
}
```

**Step 3: Add terrain setup on map load**

Replace the `onLoad` handler and update the `initialViewState`. Inside the component body, add a `useEffect` to enable terrain when the map loads:

```tsx
  // Auto-bearing for 3D terrain view
  const autoBearing = useMemo(() => {
    if (!terrain || !lapData) return 0;
    return computeAutoBearing(lapData);
  }, [terrain, lapData]);

  // Enable/disable Mapbox terrain
  useEffect(() => {
    const map = mapRef.current?.getMap();
    if (!map || !mapLoaded) return;

    if (terrain) {
      if (!map.getSource('mapbox-dem')) {
        map.addSource('mapbox-dem', {
          type: 'raster-dem',
          url: 'mapbox://mapbox.mapbox-terrain-dem-v1',
          tileSize: 512,
          maxzoom: 14,
        });
      }
      map.setTerrain({ source: 'mapbox-dem', exaggeration });
    } else {
      if (map.getTerrain()) {
        map.setTerrain(null);
      }
    }
  }, [terrain, exaggeration, mapLoaded]);
```

**Step 4: Update the MapGL initialViewState**

Change the `initialViewState` in the JSX to use terrain-aware pitch and bearing:

```tsx
  initialViewState={{
    longitude: centerLon,
    latitude: centerLat,
    zoom: 15,
    pitch: terrain ? 45 : 0,
    bearing: terrain ? autoBearing : 0,
  }}
```

**Important**: `initialViewState` only applies on first mount. Since `TrackMapSatellite` gets remounted when toggling SAT (it's dynamically imported and conditionally rendered), this works correctly — each mount gets the right initial pitch/bearing.

**Step 5: Verify dev server compiles and runs**

Run: `cd frontend && npx next dev`
- Navigate to deep dive tab
- Toggle SAT on in 2D mode — should show flat satellite (pitch=0)
- Toggle to 3D mode with SAT on — should show pitched satellite with terrain

**Step 6: Commit**

```bash
git add frontend/src/components/deep-dive/charts/TrackMapSatellite.tsx
git commit -m "feat: add 3D terrain support to satellite map with exaggeration control"
```

---

### Task 3: QA Testing via Playwright

**Step 1: Test all 4 view combinations**

Use Playwright MCP to navigate to the deep dive page and verify each combination:

1. **2D (no SAT)**: SVG track map renders with colored segments and corner labels
2. **2D + SAT**: Flat satellite map (pitch=0) with track overlay, corner markers, cursor
3. **3D (no SAT)**: Three.js 3D view with elevation, orbit controls
4. **3D + SAT**: Satellite terrain with visible elevation, track overlay, exaggeration slider visible

**Step 2: Test exaggeration slider**

- Verify slider appears only in 3D+SAT mode
- Verify slider disappears when switching to 2D or toggling SAT off
- Verify slider range shows label (e.g., "2.0×")

**Step 3: Test fullscreen in each mode**

- Toggle fullscreen in each of the 4 combinations
- Verify Escape key exits fullscreen
- Verify controls remain visible in fullscreen

**Step 4: Test mobile viewport**

- Resize to Pixel 7 / iPhone 14 device emulation
- Verify controls don't overflow
- Verify touch interaction works on satellite maps

**Step 5: Commit any fixes**

```bash
git add -A && git commit -m "fix: QA fixes for track map redesign"
```

---

### Task 4: Code Review

Run the code reviewer agent on the changed files:
- `frontend/src/components/deep-dive/charts/TrackMapContainer.tsx`
- `frontend/src/components/deep-dive/charts/TrackMapSatellite.tsx`

Fix any issues found, commit, and push.
