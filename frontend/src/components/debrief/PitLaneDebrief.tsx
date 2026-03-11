'use client';

import { useState } from 'react';
import { useSession } from '@/hooks/useSession';
import { useConsistency, useOptimalComparison } from '@/hooks/useAnalysis';
import { useCoachingReport } from '@/hooks/useCoaching';
import { ArrowRight } from 'lucide-react';
import { useSessionStore, useUiStore, useAnalysisStore } from '@/stores';
import { MarkdownText } from '@/components/shared/MarkdownText';
import { useUnits } from '@/hooks/useUnits';
import { useCoachingNav } from '@/hooks/useCoachingNav';
import { formatCoachingText } from '@/lib/textUtils';
import { normalizeScore, formatLapTime } from '@/lib/formatters';
import { DebriefHeroCard } from './DebriefHeroCard';
import { TimeLossCorners } from './TimeLossCorners';
import { QuickTip } from './QuickTip';
import { NextSessionFocus } from './NextSessionFocus';
import { ReviewModeSelector, getStoredReviewMode, setStoredReviewMode } from './ReviewModeSelector';
import type { ReviewMode } from './ReviewModeSelector';
import { SkeletonCard } from '@/components/shared/SkeletonCard';
import { EmptyState } from '@/components/shared/EmptyState';
import { SectionDivider } from '@/components/shared/SectionDivider';

export function PitLaneDebrief() {
  const sessionId = useSessionStore((s) => s.activeSessionId);
  const { data: session, isLoading: sessionLoading } = useSession(sessionId);
  const { data: consistency } = useConsistency(sessionId);
  const { data: report } = useCoachingReport(sessionId);
  const { data: optimalComparison } = useOptimalComparison(sessionId);
  const { resolveSpeed } = useUnits();
  const coachingNav = useCoachingNav();
  const setActiveView = useUiStore((s) => s.setActiveView);
  const setMode = useAnalysisStore((s) => s.setMode);
  const selectCorner = useAnalysisStore((s) => s.selectCorner);

  const [reviewMode, setReviewMode] = useState<ReviewMode>(getStoredReviewMode);

  function handleModeChange(mode: ReviewMode) {
    setReviewMode(mode);
    setStoredReviewMode(mode);
  }

  function handleExploreCorner(cornerNum: number) {
    selectCorner(`T${cornerNum}`);
    setMode('corner');
    setActiveView('deep-dive');
  }

  if (!sessionId) {
    return <EmptyState message="Select a session to see your debrief." />;
  }

  if (sessionLoading) {
    return (
      <div className="mx-auto flex w-full min-w-0 max-w-5xl flex-col gap-6 p-4 lg:p-6">
        <SkeletonCard height="h-48" />
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

  const topPriority = report?.priority_corners?.[0] ?? null;
  const is15m = reviewMode === '15m' || reviewMode === '1hr';
  const is1hr = reviewMode === '1hr';

  // Optimal gap to show in 5m mode as a compact stat
  const gapToOptimal = optimalComparison?.is_valid
    ? optimalComparison.total_gap_s
    : null;

  return (
    <div className="mx-auto flex w-full min-w-0 max-w-5xl flex-col gap-6 p-4 pb-24 lg:p-6 lg:pb-24">
      {/* Header row — title + review mode selector */}
      <div className="flex items-center justify-between">
        <h2 className="font-[family-name:var(--font-display)] text-sm font-bold uppercase tracking-widest text-[var(--text-secondary)]">
          Pit Board
        </h2>
        <ReviewModeSelector mode={reviewMode} onChange={handleModeChange} />
      </div>

      {/* ── 5m: Always visible ── */}

      {/* Next Session Focus — #1 priority, huge text */}
      {topPriority && <NextSessionFocus priority={topPriority} />}

      {/* Hero — pit board style */}
      <DebriefHeroCard
        bestLapTime={session.best_lap_time_s ?? 0}
        consistencyScore={consistencyScore}
        trackName={session.track_name ?? 'Unknown Track'}
        sessionDate={session.session_date ?? ''}
        nLaps={session.n_laps ?? 0}
      />

      {/* Gap to optimal — compact stat in 5m mode */}
      {gapToOptimal != null && gapToOptimal > 0 && (
        <div className="flex items-center gap-2 rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] px-4 py-3">
          <span className="text-sm text-[var(--text-secondary)]">Gap to optimal:</span>
          <span className="font-[family-name:var(--font-display)] text-lg font-bold text-[var(--color-brake)]">
            {gapToOptimal.toFixed(1)}s
          </span>
          {optimalComparison && (
            <span className="text-xs text-[var(--text-secondary)]">
              ({formatLapTime(optimalComparison.actual_lap_time_s)} vs {formatLapTime(optimalComparison.optimal_lap_time_s)})
            </span>
          )}
        </div>
      )}

      <SectionDivider />

      {/* Top 3 time-loss corners */}
      {report?.priority_corners && report.priority_corners.length > 0 && (
        <TimeLossCorners corners={report.priority_corners.slice(0, 3)} />
      )}

      {/* Quick tip — always in 5m */}
      {report?.drills && report.drills.length > 0 && (
        <QuickTip drill={report.drills[0]} />
      )}

      {/* ── 15m: Optimal gap per corner + more drills ── */}
      {is15m && (
        <>
          {/* Link to Report tab's Speed vs Optimal chart */}
          <button
            type="button"
            onClick={() => setActiveView('session-report')}
            className="flex min-h-[44px] w-full items-center justify-between rounded-xl border border-[var(--cata-border)] bg-[var(--bg-surface)] px-5 py-4 text-left transition-colors hover:bg-[var(--bg-elevated)]"
          >
            <div>
              <h3 className="font-[family-name:var(--font-display)] text-sm font-bold text-[var(--text-primary)]">
                Speed vs Optimal
              </h3>
              <p className="text-xs text-[var(--text-secondary)]">
                Corner-by-corner gap breakdown on the Report tab
              </p>
            </div>
            <ArrowRight className="h-4 w-4 shrink-0 text-[var(--text-secondary)]" />
          </button>

          {/* All drills (not just the first) */}
          {report?.drills && report.drills.length > 1 && (
            <div className="rounded-xl border border-[var(--cata-border)] bg-[var(--bg-surface)] p-5">
              <h3 className="mb-3 border-l-[3px] border-[var(--text-secondary)] pl-3 font-[family-name:var(--font-display)] text-sm font-bold uppercase tracking-widest text-[var(--text-secondary)]">
                Practice Drills
              </h3>
              <div className="space-y-3">
                {report.drills.slice(1).map((drill, i) => (
                  <div key={i} className="text-sm leading-relaxed text-[var(--text-secondary)]">
                    <MarkdownText block linkHandlers={coachingNav}>
                      {formatCoachingText(resolveSpeed(drill))}
                    </MarkdownText>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {/* ── 1hr: Full summary + patterns + deep dive links ── */}
      {is1hr && (
        <>
          {/* Session patterns */}
          {report?.patterns && report.patterns.length > 0 && (
            <div className="rounded-xl border border-[var(--cata-border)] bg-[var(--bg-surface)] p-5">
              <h3 className="mb-3 border-l-[3px] border-[var(--text-secondary)] pl-3 font-[family-name:var(--font-display)] text-sm font-bold uppercase tracking-widest text-[var(--text-secondary)]">
                Session Patterns
              </h3>
              <ul className="space-y-2">
                {report.patterns.map((pattern, i) => (
                  <li key={i} className="text-sm leading-relaxed text-[var(--text-secondary)]">
                    <MarkdownText block linkHandlers={coachingNav}>
                      {formatCoachingText(resolveSpeed(pattern))}
                    </MarkdownText>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Full session summary */}
          {report?.summary && (
            <div className="rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-4">
              <h3 className="mb-2 font-[family-name:var(--font-display)] text-sm font-medium text-[var(--text-secondary)]">
                Session Summary
              </h3>
              <div className="text-sm leading-relaxed text-[var(--text-secondary)]">
                <MarkdownText block linkHandlers={coachingNav}>
                  {formatCoachingText(resolveSpeed(report.summary))}
                </MarkdownText>
              </div>
            </div>
          )}

          {/* Deep dive links for each priority corner */}
          {report?.priority_corners && report.priority_corners.length > 0 && (
            <div className="rounded-xl border border-[var(--cata-border)] bg-[var(--bg-surface)] p-5">
              <h3 className="mb-3 border-l-[3px] border-[var(--text-secondary)] pl-3 font-[family-name:var(--font-display)] text-sm font-bold uppercase tracking-widest text-[var(--text-secondary)]">
                Deep Dive Into Each Corner
              </h3>
              <div className="flex flex-wrap gap-2">
                {report.priority_corners.slice(0, 3).map((pc) => (
                  <button
                    key={pc.corner}
                    type="button"
                    onClick={() => handleExploreCorner(pc.corner)}
                    className="inline-flex min-h-[44px] items-center gap-2 rounded-lg border border-[var(--cata-border)] bg-[var(--bg-base)] px-4 py-2 text-sm font-medium text-[var(--text-primary)] transition-colors hover:bg-[var(--bg-elevated)]"
                  >
                    T{pc.corner}
                    <span className="text-xs text-[var(--color-brake)]">
                      −{pc.time_cost_s.toFixed(1)}s
                    </span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
