'use client';

import { motion as m } from 'motion/react';
import { MetricCard } from '@/components/shared/MetricCard';
import { motion as motionTokens } from '@/lib/design-tokens';
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
      <h3 className="mb-3 font-[family-name:var(--font-display)] text-sm font-medium text-[var(--text-secondary)]">Session Metrics</h3>
      <m.div
        className="grid grid-cols-2 gap-3 lg:grid-cols-4"
        initial="initial"
        animate="animate"
        variants={{ animate: { transition: motionTokens.stagger } }}
      >
        <MetricCard
          label="Best Lap"
          value={bestLap != null ? formatTime(bestLap) : '\u2014'}
          highlight="pb"
          helpKey="metric.best-lap"
        />
        {!isNovice && (
          <MetricCard
            label="Top 3 Average"
            value={top3Avg != null ? formatTime(top3Avg) : '\u2014'}
            subtitle="Pace benchmark"
            helpKey="metric.top3-avg"
          />
        )}
        <MetricCard
          label="Clean Laps"
          value={`${session?.n_clean_laps ?? '\u2014'} / ${nLaps ?? '\u2014'}`}
          subtitle="Total laps driven"
          helpKey="metric.clean-laps"
        />
        <MetricCard
          label="Consistency"
          helpKey="metric.consistency"
          value={consistencyScore != null ? `${consistencyScore.toFixed(0)}%` : '\u2014'}
          subtitle={
            consistency?.lap_consistency?.has_sufficient_data === false
              ? `Low sample (${consistency.lap_consistency.sample_count ?? 0} laps)`
              : undefined
          }
          highlight={
            consistencyScore != null
              ? consistency?.lap_consistency?.has_sufficient_data === false
                ? 'none'
                : consistencyScore >= 80
                  ? 'good'
                  : consistencyScore >= 60
                    ? 'none'
                    : 'bad'
              : 'none'
          }
        />
        {isAdvanced && bestLap != null && top3Avg != null && (
          <MetricCard
            label="Top 3 Gap"
            value={`${((top3Avg - bestLap) * 1000).toFixed(0)}ms`}
            subtitle="Top 3 avg - best lap"
            helpKey="metric.pace-spread"
          />
        )}
      </m.div>
    </div>
  );
}
