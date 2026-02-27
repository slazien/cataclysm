'use client';

import { ArrowRight } from 'lucide-react';
import { useUiStore, useAnalysisStore } from '@/stores';
import type { PriorityCorner } from '@/lib/types';

interface PriorityCardsSectionProps {
  priorities: PriorityCorner[];
  isNovice: boolean;
}

export function PriorityCardsSection({ priorities, isNovice }: PriorityCardsSectionProps) {
  const setActiveView = useUiStore((s) => s.setActiveView);
  const setMode = useAnalysisStore((s) => s.setMode);
  const selectCorner = useAnalysisStore((s) => s.selectCorner);

  function handleExploreCorner(cornerNum: number) {
    selectCorner(`T${cornerNum}`);
    setMode('corner');
    setActiveView('deep-dive');
  }

  return (
    <div>
      <h3 className="mb-3 text-sm font-medium text-[var(--text-secondary)]">Priority Improvements</h3>
      <div className="grid gap-3 lg:grid-cols-3">
        {priorities.slice(0, 3).map((p) => (
          <div
            key={p.corner}
            className="rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-4"
          >
            <div className="mb-2 flex items-center justify-between">
              <span className="text-sm font-semibold text-[var(--text-primary)]">
                Turn {p.corner}
              </span>
              <span className="rounded-full bg-red-500/10 px-2 py-0.5 text-xs font-medium text-red-400">
                -{p.time_cost_s.toFixed(2)}s
              </span>
            </div>
            <p className="mb-1 text-sm text-[var(--text-secondary)]">{p.issue}</p>
            {isNovice && (
              <p className="mb-2 text-xs leading-relaxed text-[var(--text-muted)]">{p.tip}</p>
            )}
            <button
              type="button"
              onClick={() => handleExploreCorner(p.corner)}
              className="mt-2 flex items-center gap-1 text-xs font-medium text-[var(--cata-accent)] transition-colors hover:text-[var(--cata-accent)]/80"
            >
              Explore in Deep Dive <ArrowRight className="h-3 w-3" />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
