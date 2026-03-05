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

  const mapContent = (() => {
    if (satEnabled) {
      return (
        <TrackMapSatellite
          sessionId={sessionId}
          terrain={viewMode === '3d'}
          exaggeration={exaggeration}
        />
      );
    }
    if (viewMode === '3d') return <TrackMap3D sessionId={sessionId} />;
    return <TrackMapInteractive sessionId={sessionId} />;
  })();

  const showExaggerationSlider = viewMode === '3d' && satEnabled;

  const controls = (
    <div className="absolute right-2 top-2 z-20 flex items-center gap-1">
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

      <button
        onClick={toggleSat}
        className={cn(
          'flex items-center gap-1 rounded-md border px-2 py-1 text-[10px] font-semibold uppercase tracking-wider transition-colors',
          satEnabled
            ? 'border-[var(--color-optimal)] bg-[var(--bg-overlay)] text-[var(--text-primary)]'
            : 'border-[var(--cata-border)] bg-[var(--bg-elevated)] text-[var(--text-muted)] hover:text-[var(--text-secondary)]',
        )}
        title="Toggle satellite overlay"
      >
        <Satellite size={12} />
        SAT
      </button>

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
            className="h-1 w-16 cursor-pointer accent-[var(--color-optimal)]"
            title={`Terrain exaggeration: ${exaggeration.toFixed(1)}×`}
          />
        </div>
      )}

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
