'use client';

import { HeroTrackMap } from '@/components/dashboard/HeroTrackMap';

interface HeroTrackMapSectionProps {
  sessionId: string;
  bestLapNumber: number;
}

export function HeroTrackMapSection({ sessionId, bestLapNumber }: HeroTrackMapSectionProps) {
  return (
    <div id="hero-track-map">
      <h3 className="mb-3 font-[family-name:var(--font-display)] text-sm font-medium text-[var(--text-secondary)]">Track Map</h3>
      <div className="min-h-[250px] overflow-hidden rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] lg:min-h-[400px]">
        <HeroTrackMap sessionId={sessionId} bestLapNumber={bestLapNumber} />
      </div>
    </div>
  );
}
