'use client';

import { AiInsight } from '@/components/shared/AiInsight';
import { CircularProgress } from '@/components/shared/CircularProgress';
import { MarkdownText } from '@/components/shared/MarkdownText';
import { SkillLevelMismatchBanner } from '@/components/coach/SkillLevelMismatchBanner';
import { useAutoReport } from '@/hooks/useAutoReport';
import { useUiStore, useAnalysisStore } from '@/stores';
import { useUnits } from '@/hooks/useUnits';
import { cn } from '@/lib/utils';
import { InfoTooltip } from '@/components/shared/InfoTooltip';
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

function formatPriorityBadge(timeCostS: number): string {
  return timeCostS > 0 ? `Up to ${timeCostS.toFixed(1)}s` : 'Estimate unavailable';
}

function PriorityCard({
  priority,
  index,
}: {
  priority: PriorityCorner;
  index: number;
}) {
  const setActiveView = useUiStore((s) => s.setActiveView);
  const selectCorner = useAnalysisStore((s) => s.selectCorner);
  const { resolveSpeed } = useUnits();

  const handleDeepDive = () => {
    selectCorner(`T${priority.corner}`);
    setActiveView('deep-dive');
  };

  return (
    <AiInsight mode="card">
      <div className={cn('border-l-2 pl-3', priorityColors[index] ?? priorityColors[2])}>
        <div className="flex items-center justify-between">
          <span className="font-[family-name:var(--font-display)] text-xs font-medium uppercase tracking-wider text-[var(--text-muted)]">
            {priorityLabels[index] ?? `Priority ${index + 1}`}
          </span>
          <span className="text-xs font-semibold tabular-nums text-[var(--color-brake)]">
            {formatPriorityBadge(priority.time_cost_s)}
          </span>
        </div>
        <p className="mt-1 text-sm font-medium text-[var(--text-primary)]">
          Turn {priority.corner} — <MarkdownText>{resolveSpeed(priority.issue)}</MarkdownText>
        </p>
        <p className="mt-1 text-xs text-[var(--text-secondary)]"><MarkdownText>{resolveSpeed(priority.tip)}</MarkdownText></p>
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
  const { report, isLoading, isError, isSkillMismatch, retry, regenerate } = useAutoReport(sessionId);
  const skillLevel = useUiStore((s) => s.skillLevel);

  if (isLoading) {
    return (
      <div className="flex flex-col gap-3">
        <h2 className="font-[family-name:var(--font-display)] text-sm font-medium uppercase tracking-wider text-[var(--text-muted)]">
          Top Priorities
        </h2>
        <div className="flex flex-col items-center gap-3 rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-8">
          <CircularProgress size={24} color="var(--ai-icon)" />
          <p className="text-sm text-[var(--text-secondary)]">
            Generating AI coaching insights...
          </p>
        </div>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="flex flex-col gap-3">
        <h2 className="font-[family-name:var(--font-display)] text-sm font-medium uppercase tracking-wider text-[var(--text-muted)]">
          Top Priorities
        </h2>
        <div className="rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-6 text-center">
          <p className="text-sm text-[var(--text-secondary)]">
            Failed to generate coaching insights.
          </p>
          <button
            type="button"
            onClick={retry}
            className="mt-3 rounded-md bg-[var(--cata-accent)] px-3 py-1.5 text-xs font-medium text-white hover:opacity-90 transition-opacity"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (!report || report.priority_corners.length === 0) {
    return (
      <div className="flex flex-col gap-3">
        <h2 className="font-[family-name:var(--font-display)] text-sm font-medium uppercase tracking-wider text-[var(--text-muted)]">
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
      <h2 className="flex items-center gap-1.5 text-sm font-medium uppercase tracking-wider text-[var(--text-muted)]">
        Top Priorities
        <InfoTooltip helpKey="section.top-priorities" />
      </h2>
      {isSkillMismatch && report.skill_level && (
        <SkillLevelMismatchBanner
          reportLevel={report.skill_level}
          currentLevel={skillLevel}
          onRegenerate={regenerate}
        />
      )}
      <div className="flex flex-col gap-3">
        {priorities.map((p, i) => (
          <PriorityCard key={p.corner} priority={p} index={i} />
        ))}
      </div>
    </div>
  );
}
