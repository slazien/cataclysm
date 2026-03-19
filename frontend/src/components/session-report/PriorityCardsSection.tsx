'use client';

import { useState } from 'react';
import { ArrowRight, ChevronDown, ChevronUp, TrendingUp, TrendingDown } from 'lucide-react';
import { useUiStore, useAnalysisStore, useSessionStore } from '@/stores';
import type { PriorityCorner, CornerGrade, OptimalComparisonData } from '@/lib/types';
import type { CornerDelta } from '@/hooks/usePreviousSessionDelta';
import { useUnits } from '@/hooks/useUnits';
import { useSkillLevel } from '@/hooks/useSkillLevel';
import { useCoachingNav } from '@/hooks/useCoachingNav';
import { useCoachingFeedback } from '@/hooks/useCoachingFeedback';
import { worstGrade } from '@/lib/gradeUtils';
import { formatCoachingText } from '@/lib/textUtils';
import { MarkdownText } from '@/components/shared/MarkdownText';
import { ThumbsRating } from '@/components/shared/ThumbsRating';

/** Maps a grade letter to the CSS variable for left-border color */
const GRADE_BORDER_COLORS: Record<string, string> = {
  A: 'border-l-[var(--grade-a)]',
  B: 'border-l-[var(--grade-b)]',
  C: 'border-l-[var(--grade-c)]',
  D: 'border-l-[var(--grade-d)]',
  F: 'border-l-[var(--grade-f)]',
};

interface PriorityCardsSectionProps {
  priorities: PriorityCorner[];
  isNovice: boolean;
  cornerGrades?: CornerGrade[];
  optimalComparison?: OptimalComparisonData | null;
  isOptimalRefreshing?: boolean;
  cornerDeltas?: Map<number, CornerDelta> | null;
}

function formatPriorityBadge(timeCostS: number): string {
  return timeCostS > 0 ? `Up to ${timeCostS.toFixed(1)}s` : 'Estimate unavailable';
}

function PriorityCard({
  p,
  isNovice,
  gradeForCorner,
  liveTimeCost,
  isRefreshing,
  delta,
  onExplore,
  feedbackRating,
  onRate,
  feedbackPending,
}: {
  p: PriorityCorner;
  isNovice: boolean;
  gradeForCorner: string | null;
  liveTimeCost?: number;
  isRefreshing?: boolean;
  delta?: CornerDelta | null;
  onExplore: (corner: number) => void;
  feedbackRating: number;
  onRate: (rating: number) => void;
  feedbackPending: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const { resolveSpeed } = useUnits();
  const coachingNav = useCoachingNav();

  const borderColorClass = gradeForCorner
    ? (GRADE_BORDER_COLORS[gradeForCorner] ?? 'border-l-[var(--cata-accent)]')
    : 'border-l-[var(--cata-accent)]';

  const resolvedIssue = formatCoachingText(resolveSpeed(p.issue));

  return (
    <div
      className={`rounded-lg border border-[var(--cata-border)] border-l-[3px] ${borderColorClass} bg-[var(--bg-surface)] p-4`}
    >
      {/* Header: corner name + time badges */}
      <div className="mb-1 flex items-center justify-between gap-2">
        <span className="font-[family-name:var(--font-display)] text-sm font-bold text-[var(--text-primary)]">
          Turn {p.corner}
        </span>
        <div className="flex shrink-0 items-center gap-1.5">
          <span className={`rounded-full bg-[var(--color-brake)]/10 px-2 py-0.5 text-xs font-semibold tabular-nums text-[var(--color-brake)] ${isRefreshing ? 'animate-pulse' : ''}`}>
            {formatPriorityBadge(liveTimeCost ?? p.time_cost_s)}
          </span>
          {delta && Math.abs(delta.delta_s) >= 0.05 && (
            <span
              className={`inline-flex items-center gap-0.5 rounded-full px-1.5 py-0.5 text-[10px] font-semibold tabular-nums ${
                delta.delta_s > 0
                  ? 'bg-[var(--color-throttle)]/10 text-[var(--color-throttle)]'
                  : 'bg-[var(--color-brake)]/10 text-[var(--color-brake)]'
              }`}
              title={`${delta.delta_s > 0 ? 'Improved' : 'Regressed'} vs previous session`}
            >
              {delta.delta_s > 0 ? (
                <TrendingUp className="h-2.5 w-2.5" />
              ) : (
                <TrendingDown className="h-2.5 w-2.5" />
              )}
              {Math.abs(delta.delta_s).toFixed(1)}s
            </span>
          )}
        </div>
      </div>
      {/* Coaching summary — first 2 lines of resolved issue */}
      <p className="mb-2 line-clamp-2 text-sm leading-snug text-[var(--text-secondary)]">
        {resolvedIssue}
      </p>

      {/* Explore link - prominent */}
      <button
        type="button"
        onClick={() => onExplore(p.corner)}
        className="mb-2 inline-flex min-h-[44px] items-center gap-1 text-xs font-medium text-[var(--cata-accent)] transition-colors hover:text-[var(--cata-accent)]/80"
      >
        Explore in Deep Dive <ArrowRight className="h-3 w-3" />
      </button>

      {/* Novice tip - always visible when available */}
      {isNovice && p.tip && (
        <p className="mb-2 text-xs leading-relaxed text-[var(--text-secondary)]">{formatCoachingText(resolveSpeed(p.tip))}</p>
      )}

      {/* Expandable detail section — hidden for novice (tip above is sufficient) */}
      {!isNovice && (
        <div>
          <button
            type="button"
            onClick={() => setExpanded(!expanded)}
            className="inline-flex min-h-[44px] items-center gap-1 text-xs text-[var(--text-secondary)] transition-colors hover:text-[var(--text-secondary)]"
          >
            {expanded ? (
              <>
                Hide details <ChevronUp className="h-3 w-3" />
              </>
            ) : (
              <>
                Show details <ChevronDown className="h-3 w-3" />
              </>
            )}
          </button>
          {expanded && (
            <div className="mt-2 text-xs leading-relaxed text-[var(--text-secondary)]">
              <MarkdownText block linkHandlers={coachingNav}>{resolvedIssue}</MarkdownText>
            </div>
          )}
        </div>
      )}
      <div className="mt-3 flex justify-end">
        <ThumbsRating
          rating={feedbackRating}
          onRate={onRate}
          disabled={feedbackPending}
        />
      </div>
    </div>
  );
}

export function PriorityCardsSection({ priorities, isNovice, cornerGrades, optimalComparison, isOptimalRefreshing, cornerDeltas }: PriorityCardsSectionProps) {
  const setActiveView = useUiStore((s) => s.setActiveView);
  const setMode = useAnalysisStore((s) => s.setMode);
  const selectCorner = useAnalysisStore((s) => s.selectCorner);
  const { showFeature } = useSkillLevel();
  const showTrailBraking = showFeature('trail_braking_grade');
  const activeSessionId = useSessionStore((s) => s.activeSessionId);
  const { getRating, submitFeedback } = useCoachingFeedback(activeSessionId);

  function handleExploreCorner(cornerNum: number) {
    selectCorner(`T${cornerNum}`);
    setMode('corner');
    setActiveView('deep-dive');
  }

  /** Find the worst overall grade for a corner number */
  function getGradeForCorner(cornerNum: number): string | null {
    if (!cornerGrades) return null;
    const cg = cornerGrades.find((g) => g.corner === cornerNum);
    if (!cg) return null;
    const grades = [cg.braking, showTrailBraking ? cg.trail_braking : null, cg.min_speed, cg.throttle].filter((g): g is string => Boolean(g));
    return grades.length > 0 ? worstGrade(grades) : null;
  }

  return (
    <div id="priority-improvements">
      <h3 className="mb-3 font-[family-name:var(--font-display)] text-sm font-medium text-[var(--text-secondary)]">Priority Improvements</h3>
      <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
        {priorities.slice(0, 3).map((p) => {
          // Use corner_opportunities regardless of is_valid — consistent
          // with OptimalGapChart and CornerSpeedGapPanel which show
          // per-corner data even when aggregate comparison is invalid.
          // Use live time cost from physics when positive; fall back to
          // coaching report value when the model returns 0 (driver faster
          // than model — capped from negative).  `||` intentionally treats
          // 0 as falsy so the fallback fires.
          const liveTimeCost = optimalComparison?.corner_opportunities?.find(
            (o) => o.corner_number === p.corner,
          )?.time_cost_s || undefined;
          const section = `priority_corner_${p.corner}`;
          return (
            <PriorityCard
              key={p.corner}
              p={p}
              isNovice={isNovice}
              gradeForCorner={getGradeForCorner(p.corner)}
              liveTimeCost={liveTimeCost}
              isRefreshing={isOptimalRefreshing}
              delta={cornerDeltas?.get(p.corner)}
              onExplore={handleExploreCorner}
              feedbackRating={getRating(section)}
              onRate={(r) => submitFeedback.mutate({ section, rating: r })}
              feedbackPending={submitFeedback.isPending}
            />
          );
        })}
      </div>
    </div>
  );
}
