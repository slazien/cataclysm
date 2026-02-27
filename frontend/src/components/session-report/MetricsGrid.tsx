'use client';

import { MetricCard } from '@/components/shared/MetricCard';
import type { SessionSummary, LapSummary, SessionConsistency } from '@/lib/types';

interface MetricsGridProps {
  session: SessionSummary | null;
  laps: LapSummary[] | null;
  consistency: SessionConsistency | null;
  isNovice: boolean;
  isAdvanced: boolean;
}

function formatTime(seconds: number): string {
  const min = Math.floor(seconds / 60);
  const sec = (seconds % 60).toFixed(3);
  return `${min}:${sec.padStart(6, '0')}`;
}

export function MetricsGrid({ session, laps, consistency, isNovice, isAdvanced }: MetricsGridProps) {
  const bestLap = session?.best_lap_time_s;
  const top3Avg = session?.top3_avg_time_s;
  const nLaps = session?.n_laps ?? laps?.length;
  const consistencyScore = consistency?.lap_consistency?.consistency_score;

  return (
    <div>
      <h3 className="mb-3 text-sm font-medium text-[var(--text-secondary)]">Session Metrics</h3>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <MetricCard
          label="Best Lap"
          value={bestLap != null ? formatTime(bestLap) : '\u2014'}
          highlight="pb"
        />
        {!isNovice && (
          <MetricCard
            label="Top 3 Average"
            value={top3Avg != null ? formatTime(top3Avg) : '\u2014'}
            subtitle="Pace benchmark"
          />
        )}
        <MetricCard
          label="Clean Laps"
          value={`${session?.n_clean_laps ?? '\u2014'} / ${nLaps ?? '\u2014'}`}
          subtitle="Total laps driven"
        />
        <MetricCard
          label="Consistency"
          value={consistencyScore != null ? `${consistencyScore.toFixed(0)}%` : '\u2014'}
          highlight={consistencyScore != null ? (consistencyScore >= 80 ? 'good' : consistencyScore >= 60 ? 'none' : 'bad') : 'none'}
        />
        {isAdvanced && bestLap != null && top3Avg != null && (
          <MetricCard
            label="Pace Spread"
            value={`${((top3Avg - bestLap) * 1000).toFixed(0)}ms`}
            subtitle="Top 3 avg - best lap"
          />
        )}
      </div>
    </div>
  );
}
