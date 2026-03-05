'use client';

import { useState, useEffect, useCallback } from 'react';
import dynamic from 'next/dynamic';
import { Maximize2, Minimize2 } from 'lucide-react';
import { TrackMapInteractive } from './TrackMapInteractive';
import { cn } from '@/lib/utils';

type MapMode = '2d' | 'sat' | '3d';

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

const MODE_LABELS: { mode: MapMode; label: string }[] = [
  { mode: '2d', label: '2D' },
  { mode: 'sat', label: 'SAT' },
  { mode: '3d', label: '3D' },
];

export function TrackMapContainer({ sessionId }: TrackMapContainerProps) {
  const [mode, setMode] = useState<MapMode>('2d');
  const [fullscreen, setFullscreen] = useState(false);

  const toggleFullscreen = useCallback(() => setFullscreen((f) => !f), []);

  useEffect(() => {
    if (!fullscreen) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setFullscreen(false);
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [fullscreen]);

  const mapContent = (
    <>
      {mode === '3d' && <TrackMap3D sessionId={sessionId} />}
      {mode === 'sat' && <TrackMapSatellite sessionId={sessionId} />}
      {mode === '2d' && <TrackMapInteractive sessionId={sessionId} />}
    </>
  );

  const controls = (
    <div className="absolute right-2 top-2 z-20 flex items-center gap-1">
      <div className="flex overflow-hidden rounded-md border border-[var(--cata-border)] bg-[var(--bg-elevated)]">
        {MODE_LABELS.map(({ mode: m, label }) => (
          <button
            key={m}
            onClick={() => setMode(m)}
            className={cn(
              'px-2 py-1 text-[10px] font-semibold uppercase tracking-wider transition-colors',
              mode === m
                ? 'bg-[var(--bg-overlay)] text-[var(--text-primary)]'
                : 'text-[var(--text-muted)] hover:text-[var(--text-secondary)]',
            )}
          >
            {label}
          </button>
        ))}
      </div>
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
        {/* Placeholder to keep layout stable */}
        <div className="h-full" />
        {/* Fullscreen overlay */}
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
