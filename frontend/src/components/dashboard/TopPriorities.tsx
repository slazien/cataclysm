'use client';

import { useEffect, useRef } from 'react';
import { AiInsight } from '@/components/shared/AiInsight';
import { useCoachingReport, useGenerateReport } from '@/hooks/useCoaching';
import { useUiStore, useAnalysisStore } from '@/stores';
import { cn } from '@/lib/utils';
import type { PriorityCorner } from '@/lib/types';

interface TopPrioritiesProps {
  sessionId: string;
}

const priorityColors = [
  'border-l-[var(--color-brake)]',    // 1st — red
  'border-l-[var(--color-neutral)]',   // 2nd — amber
  'border-l-[var(--color-throttle)]',  // 3rd — green
];

const priorityLabels = ['Biggest Gain', 'Second Priority', 'Quick Win'];

function PriorityCard({
  priority,
  index,
  sessionId,
}: {
  priority: PriorityCorner;
  index: number;
  sessionId: string;
}) {
  const setActiveView = useUiStore((s) => s.setActiveView);
  const selectCorner = useAnalysisStore((s) => s.selectCorner);

  const handleDeepDive = () => {
    selectCorner(`T${priority.corner}`);
    setActiveView('deep-dive');
  };

  return (
    <AiInsight mode="card">
      <div className={cn('border-l-2 pl-3', priorityColors[index] ?? priorityColors[2])}>
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium uppercase tracking-wider text-[var(--text-muted)]">
            {priorityLabels[index] ?? `Priority ${index + 1}`}
          </span>
          <span className="text-xs font-semibold tabular-nums text-[var(--color-brake)]">
            {priority.time_cost_s > 0 ? '-' : ''}{Math.abs(priority.time_cost_s).toFixed(1)}s
          </span>
        </div>
        <p className="mt-1 text-sm font-medium text-[var(--text-primary)]">
          Turn {priority.corner} — {priority.issue}
        </p>
        <p className="mt-1 text-xs text-[var(--text-secondary)]">{priority.tip}</p>
        <button
          type="button"
          onClick={handleDeepDive}
          className="mt-2 text-xs font-medium text-[var(--ai-icon)] hover:underline"
        >
          Show in Deep Dive &rarr;
        </button>
      </div>
    </AiInsight>
  );
}

export function TopPriorities({ sessionId }: TopPrioritiesProps) {
  const { data: report, isLoading, isError } = useCoachingReport(sessionId);
  const generateReport = useGenerateReport();
  const skillLevel = useUiStore((s) => s.skillLevel);
  const hasTriggered = useRef(false);

  // Auto-trigger report generation if no report exists
  useEffect(() => {
    if (
      !isLoading &&
      (isError || !report) &&
      !generateReport.isPending &&
      !hasTriggered.current
    ) {
      hasTriggered.current = true;
      generateReport.mutate({ sessionId, skillLevel });
    }
  }, [sessionId, isLoading, isError, report, generateReport, skillLevel]);

  // Reset trigger flag when session changes
  useEffect(() => {
    hasTriggered.current = false;
  }, [sessionId]);

  if (isLoading || generateReport.isPending) {
    return (
      <div className="flex flex-col gap-3">
        <h2 className="text-sm font-medium uppercase tracking-wider text-[var(--text-muted)]">
          Top Priorities
        </h2>
        <div className="flex flex-col items-center gap-3 rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-8">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-[var(--ai-icon)] border-t-transparent" />
          <p className="text-sm text-[var(--text-secondary)]">
            Generating AI coaching insights...
          </p>
        </div>
      </div>
    );
  }

  if (!report || report.priority_corners.length === 0) {
    return (
      <div className="flex flex-col gap-3">
        <h2 className="text-sm font-medium uppercase tracking-wider text-[var(--text-muted)]">
          Top Priorities
        </h2>
        <div className="rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-6 text-center">
          <p className="text-sm text-[var(--text-secondary)]">
            No coaching insights available yet.
          </p>
        </div>
      </div>
    );
  }

  const priorities = report.priority_corners.slice(0, 3);

  return (
    <div className="flex flex-col gap-3">
      <h2 className="text-sm font-medium uppercase tracking-wider text-[var(--text-muted)]">
        Top Priorities
      </h2>
      <div className="flex flex-col gap-3">
        {priorities.map((p, i) => (
          <PriorityCard key={p.corner} priority={p} index={i} sessionId={sessionId} />
        ))}
      </div>
    </div>
  );
}
