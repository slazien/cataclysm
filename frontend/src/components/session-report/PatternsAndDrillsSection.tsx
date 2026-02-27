'use client';

import { TrendingUp, Target } from 'lucide-react';

interface PatternsAndDrillsSectionProps {
  patterns: string[];
  drills: string[];
}

export function PatternsAndDrillsSection({ patterns, drills }: PatternsAndDrillsSectionProps) {
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      {patterns.length > 0 && (
        <div className="rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-4">
          <div className="mb-3 flex items-center gap-2">
            <TrendingUp className="h-4 w-4 text-[var(--cata-accent)]" />
            <h4 className="text-sm font-medium text-[var(--text-primary)]">Patterns</h4>
          </div>
          <ul className="space-y-1.5">
            {patterns.map((p, i) => (
              <li key={i} className="text-sm text-[var(--text-secondary)]">
                <span className="mr-2 text-[var(--text-muted)]">&bull;</span>{p}
              </li>
            ))}
          </ul>
        </div>
      )}
      {drills.length > 0 && (
        <div className="rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-4">
          <div className="mb-3 flex items-center gap-2">
            <Target className="h-4 w-4 text-[var(--cata-accent)]" />
            <h4 className="text-sm font-medium text-[var(--text-primary)]">Recommended Drills</h4>
          </div>
          <ul className="space-y-1.5">
            {drills.map((d, i) => (
              <li key={i} className="text-sm text-[var(--text-secondary)]">
                <span className="mr-2 text-[var(--text-muted)]">{i + 1}.</span>{d}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
