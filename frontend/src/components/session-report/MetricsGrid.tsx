'use client';

import { motion as m } from 'motion/react';
import { cn } from '@/lib/utils';
import { MetricCard } from '@/components/shared/MetricCard';
import { motion as motionTokens } from '@/lib/design-tokens';
import { useSkillLevel } from '@/hooks/useSkillLevel';
import type { SessionSummary, LapSummary, SessionConsistency } from '@/lib/types';

interface MetricsGridProps {
  session: SessionSummary | null;
  laps: LapSummary[] | null;
  consistency: SessionConsistency | null;
  isNovice: boolean;
  isAdvanced: boolean;
  /** Physics-optimal lap time (equipment-aware). Preferred over session ideal lap when present. */
  physicsOptimalLapTime?: number;
  /** True while the optimal target is being recomputed for new equipment. */
  isOptimalRefreshing?: boolean;
  /** True while the initial optimal comparison query is in flight. */
  isOptimalPending?: boolean;
}

function formatTime(seconds: number): string {
  const min = Math.floor(seconds / 60);
  const sec = (seconds % 60).toFixed(3);
  return `${min}:${sec.padStart(6, '0')}`;
}

const CONSISTENCY_RANGES: Record<string, [number, number]> = {
  novice: [40, 55],
  intermediate: [60, 75],
  advanced: [78, 90],
};

function consistencySubtitle(score: number | undefined, level: string, hasSufficientData: boolean | undefined, sampleCount: number | undefined): string | undefined {
  if (hasSufficientData === false) return `Low sample (${sampleCount ?? 0} laps)`;
  if (score == null) return undefined;
  const range = CONSISTENCY_RANGES[level] ?? CONSISTENCY_RANGES.intermediate;
  if (score >= range[0] && score <= range[1]) return `On target for ${level} (${range[0]}–${range[1]})`;
  if (score > range[1]) return `Above ${level} range (${range[0]}–${range[1]})`;
  const gap = Math.ceil(range[0] - score);
  return `+${gap} pts to ${level} range (${range[0]}–${range[1]})`;
}

export function MetricsGrid({ session, laps, consistency, isNovice, isAdvanced, physicsOptimalLapTime, isOptimalRefreshing, isOptimalPending }: MetricsGridProps) {
  const { skillLevel } = useSkillLevel();
  const bestLap = session?.best_lap_time_s;
  const top3Avg = session?.top3_avg_time_s;
  const optimalLap = physicsOptimalLapTime;
  const nLaps = session?.n_laps ?? laps?.length;
  const consistencyScore = consistency?.lap_consistency?.consistency_score;

  const optimalDelta = bestLap != null && optimalLap != null ? bestLap - optimalLap : null;

  return (
    <div id="metrics-grid">
      <h3 className="mb-3 font-[family-name:var(--font-display)] text-sm font-medium text-[var(--text-secondary)]">Session Metrics</h3>
      <m.div
        className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-4"
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
        {(optimalLap != null || isOptimalPending) && (
          <MetricCard
            label="Optimal Target"
            value={optimalLap != null ? formatTime(optimalLap) : '\u2014'}
            subtitle={optimalDelta != null ? `${optimalDelta.toFixed(3)}s potential` : undefined}
            helpKey="metric.optimal-lap"
            className={cn((isOptimalRefreshing || isOptimalPending) && 'animate-pulse')}
          />
        )}
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
          subtitle={consistencySubtitle(
            consistencyScore != null ? Number(consistencyScore.toFixed(0)) : undefined,
            skillLevel,
            consistency?.lap_consistency?.has_sufficient_data,
            consistency?.lap_consistency?.sample_count,
          )}
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
            value={`${(top3Avg - bestLap).toFixed(1)}s`}
            subtitle="Top 3 avg - best lap"
            helpKey="metric.pace-spread"
          />
        )}
      </m.div>
    </div>
  );
}
