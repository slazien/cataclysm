'use client';

import { HeroTrackMap } from '@/components/dashboard/HeroTrackMap';

interface HeroTrackMapSectionProps {
  sessionId: string;
  bestLapNumber: number;
}

export function HeroTrackMapSection({ sessionId, bestLapNumber }: HeroTrackMapSectionProps) {
  return (
    <div>
      <h3 className="mb-3 text-sm font-medium text-[var(--text-secondary)]">Track Map</h3>
      <div className="min-h-[400px] overflow-hidden rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)]">
        <HeroTrackMap sessionId={sessionId} bestLapNumber={bestLapNumber} />
      </div>
    </div>
  );
}
