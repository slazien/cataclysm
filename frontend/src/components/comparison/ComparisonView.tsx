'use client';

import { useState } from 'react';
import { Loader2 } from 'lucide-react';
import { useShareComparison } from '@/hooks/useComparison';
import { TaleOfTheTape } from './TaleOfTheTape';
import { CornerScorecard } from './CornerScorecard';
import { ComparisonDeltaChart } from './ComparisonDeltaChart';

interface ComparisonViewProps {
  token: string;
}

export function ComparisonView({ token }: ComparisonViewProps) {
  const { data, isLoading, error } = useShareComparison(token);
  const [selectedCorner, setSelectedCorner] = useState<number | null>(null);

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 py-12">
        <Loader2 className="h-6 w-6 animate-spin text-[var(--text-muted)]" />
        <p className="text-sm text-[var(--text-secondary)]">Loading comparison...</p>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="rounded-lg border border-[var(--color-brake)]/30 bg-[var(--color-brake)]/5 p-6 text-center">
        <p className="text-sm text-[var(--text-primary)]">
          Failed to load comparison data.
        </p>
        <p className="mt-1 text-xs text-[var(--text-muted)]">
          {error instanceof Error ? error.message : 'The share link may be expired or invalid.'}
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-5">
      {/* Layer 1: Tale of the Tape */}
      <TaleOfTheTape
        sessionA={{
          trackName: data.session_a_track,
          bestLap: data.session_a_best_lap,
        }}
        sessionB={{
          trackName: data.session_b_track,
          bestLap: data.session_b_best_lap,
        }}
      />

      {/* Layer 2: Corner Scorecard */}
      {data.corner_deltas.length > 0 && (
        <CornerScorecard
          cornerDeltas={data.corner_deltas}
          onSelectCorner={setSelectedCorner}
          selectedCorner={selectedCorner}
        />
      )}

      {/* Layer 3: Delta Chart for selected corner */}
      {selectedCorner !== null && data.distance_m.length > 0 && (
        <div className="rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-4">
          <h2 className="mb-3 text-sm font-medium text-[var(--text-primary)] font-[family-name:var(--font-display)]">
            Delta-T: Turn {selectedCorner}
          </h2>
          <p className="mb-4 text-xs text-[var(--text-secondary)]">
            Green = Driver A gaining time, Red = Driver A losing time
          </p>
          <div className="h-56 lg:h-64">
            <ComparisonDeltaChart
              cornerNumber={selectedCorner}
              distanceM={data.distance_m}
              deltaTimeS={data.delta_time_s}
            />
          </div>
        </div>
      )}
    </div>
  );
}
