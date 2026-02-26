'use client';

import { useMemo } from 'react';
import { useSession, useSessionLaps } from '@/hooks/useSession';
import { useConsistency } from '@/hooks/useAnalysis';
import { useIdealLap, useCoachingReport } from '@/hooks/useCoaching';
import { useSessionStore } from '@/stores';
import { MetricCard } from '@/components/shared/MetricCard';
import { EmptyState } from '@/components/shared/EmptyState';
import { CircularProgress } from '@/components/shared/CircularProgress';
import { SessionScore } from './SessionScore';
import { TopPriorities } from './TopPriorities';
import { HeroTrackMap } from './HeroTrackMap';
import { LapTimesBar } from './LapTimesBar';
import { formatLapTime, formatSpeed, normalizeScore } from '@/lib/formatters';
import { MPS_TO_MPH } from '@/lib/constants';

export function SessionDashboard() {
  const sessionId = useSessionStore((s) => s.activeSessionId);
  const { data: session, isLoading: sessionLoading } = useSession(sessionId);
  const { data: laps, isLoading: lapsLoading } = useSessionLaps(sessionId);
  const { data: consistency, isLoading: consistencyLoading } = useConsistency(sessionId);
  const { data: idealLap } = useIdealLap(sessionId);
  const { data: coachingReport } = useCoachingReport(sessionId);

  // Derive best lap number
  const bestLapNumber = useMemo(() => {
    if (!laps || laps.length === 0) return null;
    const best = laps.reduce((min, lap) =>
      lap.lap_time_s < min.lap_time_s ? lap : min,
    );
    return best.lap_number;
  }, [laps]);

  // Derive top speed across all laps
  const topSpeedMph = useMemo(() => {
    if (!laps || laps.length === 0) return null;
    const maxMps = Math.max(...laps.map((l) => l.max_speed_mps));
    return maxMps * MPS_TO_MPH;
  }, [laps]);

  // Compute ideal lap time and delta
  const idealLapInfo = useMemo(() => {
    if (!idealLap || !session) return null;
    const { distance_m, speed_mph } = idealLap;
    if (!distance_m || !speed_mph || distance_m.length < 2) return null;

    let totalTime = 0;
    for (let i = 1; i < distance_m.length; i++) {
      const ds = distance_m[i] - distance_m[i - 1];
      const avgSpeedMph = (speed_mph[i] + speed_mph[i - 1]) / 2;
      const avgSpeedMps = avgSpeedMph / MPS_TO_MPH;
      if (avgSpeedMps > 0) {
        totalTime += ds / avgSpeedMps;
      }
    }

    const delta = session.best_lap_time_s - totalTime;
    return { time: totalTime, delta };
  }, [idealLap, session]);

  // Compute composite session score: consistency (40%) + best/optimal (30%) + corner grades (30%)
  const sessionScore = useMemo(() => {
    const components: { value: number; weight: number }[] = [];

    // Consistency component (0-100)
    if (consistency?.lap_consistency) {
      const consistencyScore = normalizeScore(consistency.lap_consistency.consistency_score);
      components.push({ value: consistencyScore, weight: 0.4 });
    }

    // Best lap vs optimal component (0-100)
    // More penalizing curve: 100 at perfect, 75 at 5% off, 50 at 10% off, 0 at 20%+ off
    if (idealLapInfo && session) {
      const gapPct = 1 - (idealLapInfo.time / session.best_lap_time_s);
      const optimalScore = Math.min(100, Math.max(0, 100 - gapPct * 500));
      components.push({ value: optimalScore, weight: 0.3 });
    }

    // Corner grades component (0-100)
    if (coachingReport?.corner_grades && coachingReport.corner_grades.length > 0) {
      const gradeMap: Record<string, number> = { A: 100, B: 80, C: 60, D: 40, F: 20 };
      const gradeFields = ['braking', 'trail_braking', 'min_speed', 'throttle'] as const;
      let total = 0;
      let count = 0;
      for (const cg of coachingReport.corner_grades) {
        for (const field of gradeFields) {
          const letter = cg[field]?.charAt(0)?.toUpperCase();
          if (letter && gradeMap[letter] !== undefined) {
            total += gradeMap[letter];
            count++;
          }
        }
      }
      if (count > 0) {
        components.push({ value: total / count, weight: 0.3 });
      }
    }

    if (components.length === 0) return null;

    // Normalize weights to sum to 1 if some components are missing
    const totalWeight = components.reduce((s, c) => s + c.weight, 0);
    const weighted = components.reduce((s, c) => s + c.value * (c.weight / totalWeight), 0);
    return weighted;
  }, [consistency, idealLapInfo, session, coachingReport]);

  // No session selected
  if (!sessionId) {
    return <EmptyState />;
  }

  // Loading state
  if (sessionLoading || lapsLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <CircularProgress size={32} />
          <p className="text-sm text-[var(--text-secondary)]">Loading session...</p>
        </div>
      </div>
    );
  }

  if (!session) {
    return (
      <EmptyState
        title="Session not found"
        message="The selected session could not be loaded."
      />
    );
  }

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6 p-4 lg:p-6">
      {/* Hero Metrics Row */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4 lg:gap-4">
        <SessionScore score={sessionScore} isLoading={consistencyLoading} />

        <MetricCard
          label="Best Lap"
          value={formatLapTime(session.best_lap_time_s)}
          subtitle={`Lap ${bestLapNumber ?? '--'}`}
          highlight="pb"
        />

        <MetricCard
          label="Top 3 Average"
          value={formatLapTime(session.top3_avg_time_s)}
          delta={session.top3_avg_time_s - session.best_lap_time_s}
          deltaLabel="vs best"
        />

        <MetricCard
          label="Session Average"
          value={formatLapTime(session.avg_lap_time_s)}
          delta={session.avg_lap_time_s - session.best_lap_time_s}
          deltaLabel="vs best"
        />
      </div>

      {/* Two-column middle section */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 lg:gap-6">
        <TopPriorities sessionId={sessionId} />
        {bestLapNumber !== null && (
          <HeroTrackMap sessionId={sessionId} bestLapNumber={bestLapNumber} />
        )}
      </div>

      {/* Lap Times Bar Chart */}
      <LapTimesBar sessionId={sessionId} />

      {/* Summary Metrics Row */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4 lg:gap-4">
        <MetricCard
          label="Consistency"
          value={
            consistency?.lap_consistency
              ? `${Math.round(normalizeScore(consistency.lap_consistency.consistency_score))}%`
              : '--'
          }
          subtitle={
            consistency?.lap_consistency
              ? `${consistency.lap_consistency.std_dev_s.toFixed(2)}s std dev`
              : undefined
          }
          highlight={
            consistency?.lap_consistency
              ? normalizeScore(consistency.lap_consistency.consistency_score) >= 80
                ? 'good'
                : 'none'
              : 'none'
          }
        />

        <MetricCard
          label="Clean Laps"
          value={`${session.n_clean_laps} / ${session.n_laps}`}
          subtitle={
            session.n_laps > 0
              ? `${Math.round((session.n_clean_laps / session.n_laps) * 100)}% clean`
              : undefined
          }
          highlight={
            session.n_laps > 0 && session.n_clean_laps / session.n_laps >= 0.8
              ? 'good'
              : 'none'
          }
        />

        <MetricCard
          label="Top Speed"
          value={topSpeedMph !== null ? formatSpeed(topSpeedMph) : '--'}
        />

        <MetricCard
          label="Optimal Lap"
          value={idealLapInfo ? formatLapTime(idealLapInfo.time) : '--'}
          delta={idealLapInfo ? idealLapInfo.delta : undefined}
          deltaLabel={idealLapInfo ? 'potential gain' : undefined}
          highlight={idealLapInfo ? 'good' : 'none'}
        />
      </div>
    </div>
  );
}
