'use client';

import { useState } from 'react';
import dynamic from 'next/dynamic';
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

  return (
    <div className="relative h-full">
      {/* Mode toggle */}
      <div className="absolute right-2 top-2 z-20 flex overflow-hidden rounded-md border border-[var(--cata-border)] bg-[var(--bg-elevated)]">
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

      {mode === '3d' && <TrackMap3D sessionId={sessionId} />}
      {mode === 'sat' && <TrackMapSatellite sessionId={sessionId} />}
      {mode === '2d' && <TrackMapInteractive sessionId={sessionId} />}
    </div>
  );
}
