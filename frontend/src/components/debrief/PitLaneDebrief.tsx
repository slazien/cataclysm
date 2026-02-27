'use client';

import { useSession } from '@/hooks/useSession';
import { useConsistency } from '@/hooks/useAnalysis';
import { useCoachingReport } from '@/hooks/useCoaching';
import { useSessionStore } from '@/stores';
import { formatLapTime, normalizeScore } from '@/lib/formatters';
import { DebriefHeroCard } from './DebriefHeroCard';
import { TimeLossCorners } from './TimeLossCorners';
import { QuickTip } from './QuickTip';
import { SkeletonCard } from '@/components/shared/SkeletonCard';
import { EmptyState } from '@/components/shared/EmptyState';

export function PitLaneDebrief() {
  const sessionId = useSessionStore((s) => s.activeSessionId);
  const { data: session, isLoading: sessionLoading } = useSession(sessionId);
  const { data: consistency } = useConsistency(sessionId);
  const { data: report } = useCoachingReport(sessionId);

  if (!sessionId) {
    return <EmptyState message="Select a session to see your debrief." />;
  }

  if (sessionLoading) {
    return (
      <div className="mx-auto flex max-w-lg flex-col gap-4 p-4">
        <SkeletonCard height="h-32" />
        <SkeletonCard height="h-40" />
        <SkeletonCard height="h-20" />
      </div>
    );
  }

  if (!session) {
    return <EmptyState title="Session not found" />;
  }

  const consistencyScore = consistency?.lap_consistency
    ? Math.round(normalizeScore(consistency.lap_consistency.consistency_score))
    : null;

  return (
    <div className="mx-auto flex max-w-lg flex-col gap-4 p-4 pb-24">
      {/* Hero */}
      <DebriefHeroCard
        bestLapTime={session.best_lap_time_s ?? 0}
        consistencyScore={consistencyScore}
        trackName={session.track_name ?? 'Unknown Track'}
        sessionDate={session.session_date ?? ''}
        nLaps={session.n_laps ?? 0}
      />

      {/* Top 3 time-loss corners */}
      {report?.priority_corners && report.priority_corners.length > 0 && (
        <TimeLossCorners corners={report.priority_corners.slice(0, 3)} />
      )}

      {/* Quick tip */}
      {report?.drills && report.drills.length > 0 && (
        <QuickTip drill={report.drills[0]} />
      )}

      {/* Summary */}
      {report?.summary && (
        <div className="rounded-xl border border-[var(--cata-border)] bg-[var(--bg-surface)] p-4">
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-[var(--text-tertiary)]">
            Session Summary
          </h3>
          <p className="text-sm leading-relaxed text-[var(--text-secondary)]">
            {report.summary}
          </p>
        </div>
      )}
    </div>
  );
}
