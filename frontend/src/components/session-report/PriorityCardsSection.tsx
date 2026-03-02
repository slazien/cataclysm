'use client';

import { useState } from 'react';
import { ArrowRight, ChevronDown, ChevronUp } from 'lucide-react';
import { useUiStore, useAnalysisStore } from '@/stores';
import type { PriorityCorner, CornerGrade } from '@/lib/types';
import { worstGrade } from '@/lib/gradeUtils';

/** Maps a grade letter to the CSS variable for left-border color */
const GRADE_BORDER_COLORS: Record<string, string> = {
  A: 'border-l-[var(--grade-a)]',
  B: 'border-l-[var(--grade-b)]',
  C: 'border-l-[var(--grade-c)]',
  D: 'border-l-[var(--grade-d)]',
  F: 'border-l-[var(--grade-f)]',
};

/** Extracts a short action phrase from the issue text.
 *  Takes the first clause (before a comma, period, or dash) and caps it. */
function extractActionTitle(issue: string): string {
  // Try to grab first short clause
  const match = issue.match(/^(.{10,60}?)[.,;:\u2014\u2013-]\s/);
  if (match) return match[1].trim();
  // Fallback: first N words up to ~50 chars
  const words = issue.split(/\s+/);
  let result = '';
  for (const w of words) {
    if ((result + ' ' + w).trim().length > 50) break;
    result = (result + ' ' + w).trim();
  }
  return result || issue.slice(0, 50);
}

interface PriorityCardsSectionProps {
  priorities: PriorityCorner[];
  isNovice: boolean;
  cornerGrades?: CornerGrade[];
}

function PriorityCard({
  p,
  isNovice,
  gradeForCorner,
  onExplore,
}: {
  p: PriorityCorner;
  isNovice: boolean;
  gradeForCorner: string | null;
  onExplore: (corner: number) => void;
}) {
  const [expanded, setExpanded] = useState(false);

  const borderColorClass = gradeForCorner
    ? (GRADE_BORDER_COLORS[gradeForCorner] ?? 'border-l-[var(--cata-accent)]')
    : 'border-l-[var(--cata-accent)]';

  const actionTitle = extractActionTitle(p.issue);

  return (
    <div
      className={`rounded-lg border border-[var(--cata-border)] border-l-[3px] ${borderColorClass} bg-[var(--bg-surface)] p-4`}
    >
      {/* Header: corner name + action title + time gain */}
      <div className="mb-2 flex items-start justify-between gap-2">
        <div className="min-w-0">
          <span className="font-[family-name:var(--font-display)] text-sm font-bold text-[var(--text-primary)]">
            Turn {p.corner}
          </span>
          <span className="mx-1.5 text-[var(--text-muted)]">&mdash;</span>
          <span className="text-sm font-medium text-[var(--text-primary)]">
            {actionTitle}
          </span>
        </div>
        <span className="shrink-0 rounded-full bg-[var(--color-throttle)]/10 px-2 py-0.5 text-xs font-semibold tabular-nums text-[var(--color-throttle)]">
          -{p.time_cost_s.toFixed(2)}s
        </span>
      </div>

      {/* Explore link - prominent */}
      <button
        type="button"
        onClick={() => onExplore(p.corner)}
        className="mb-2 flex items-center gap-1 text-xs font-medium text-[var(--cata-accent)] transition-colors hover:text-[var(--cata-accent)]/80"
      >
        Explore in Deep Dive <ArrowRight className="h-3 w-3" />
      </button>

      {/* Novice tip - always visible when available */}
      {isNovice && p.tip && (
        <p className="mb-2 text-xs leading-relaxed text-[var(--text-muted)]">{p.tip}</p>
      )}

      {/* Expandable detail section */}
      <div>
        <button
          type="button"
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-1 text-xs text-[var(--text-muted)] transition-colors hover:text-[var(--text-secondary)]"
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
          <p className="mt-2 text-xs leading-relaxed text-[var(--text-secondary)]">
            {p.issue}
          </p>
        )}
      </div>
    </div>
  );
}

export function PriorityCardsSection({ priorities, isNovice, cornerGrades }: PriorityCardsSectionProps) {
  const setActiveView = useUiStore((s) => s.setActiveView);
  const setMode = useAnalysisStore((s) => s.setMode);
  const selectCorner = useAnalysisStore((s) => s.selectCorner);

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
    const grades = [cg.braking, cg.trail_braking, cg.min_speed, cg.throttle].filter(Boolean);
    return grades.length > 0 ? worstGrade(grades) : null;
  }

  return (
    <div>
      <h3 className="mb-3 font-[family-name:var(--font-display)] text-sm font-medium text-[var(--text-secondary)]">Priority Improvements</h3>
      <div className="grid gap-3 lg:grid-cols-3">
        {priorities.slice(0, 3).map((p) => (
          <PriorityCard
            key={p.corner}
            p={p}
            isNovice={isNovice}
            gradeForCorner={getGradeForCorner(p.corner)}
            onExplore={handleExploreCorner}
          />
        ))}
      </div>
    </div>
  );
}
