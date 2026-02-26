'use client';

import { useState } from 'react';
import dynamic from 'next/dynamic';
import { TrackMapInteractive } from './TrackMapInteractive';
import { cn } from '@/lib/utils';

const TrackMap3D = dynamic(
  () => import('./TrackMap3D').then((mod) => mod.TrackMap3D),
  { ssr: false },
);

interface TrackMapContainerProps {
  sessionId: string;
}

export function TrackMapContainer({ sessionId }: TrackMapContainerProps) {
  const [is3D, setIs3D] = useState(false);

  return (
    <div className="relative h-full">
      {/* 2D / 3D toggle */}
      <div className="absolute right-2 top-2 z-20 flex overflow-hidden rounded-md border border-[var(--cata-border)] bg-[var(--bg-elevated)]">
        <button
          onClick={() => setIs3D(false)}
          className={cn(
            'px-2 py-1 text-[10px] font-semibold uppercase tracking-wider transition-colors',
            !is3D
              ? 'bg-[var(--bg-overlay)] text-[var(--text-primary)]'
              : 'text-[var(--text-muted)] hover:text-[var(--text-secondary)]',
          )}
        >
          2D
        </button>
        <button
          onClick={() => setIs3D(true)}
          className={cn(
            'px-2 py-1 text-[10px] font-semibold uppercase tracking-wider transition-colors',
            is3D
              ? 'bg-[var(--bg-overlay)] text-[var(--text-primary)]'
              : 'text-[var(--text-muted)] hover:text-[var(--text-secondary)]',
          )}
        >
          3D
        </button>
      </div>

      {is3D ? (
        <TrackMap3D sessionId={sessionId} />
      ) : (
        <TrackMapInteractive sessionId={sessionId} />
      )}
    </div>
  );
}
