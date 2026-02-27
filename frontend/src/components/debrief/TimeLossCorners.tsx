'use client';

import type { PriorityCorner } from '@/lib/types';

interface TimeLossCornersProps {
  corners: PriorityCorner[];
}

export function TimeLossCorners({ corners }: TimeLossCornersProps) {
  return (
    <div className="rounded-xl border border-[var(--cata-border)] bg-[var(--bg-surface)] p-4">
      <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-[var(--text-tertiary)]">
        Focus Areas
      </h3>
      <div className="space-y-3">
        {corners.map((pc, i) => (
          <div
            key={pc.corner}
            className="flex items-start gap-3 rounded-lg bg-[var(--bg-base)] p-3"
          >
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-red-500/15 text-sm font-bold text-red-400">
              T{pc.corner}
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-center justify-between">
                <p className="text-sm font-medium text-[var(--text-primary)]">{pc.issue}</p>
                <span className="shrink-0 text-xs font-mono text-red-400">
                  -{pc.time_cost_s.toFixed(2)}s
                </span>
              </div>
              <p className="mt-0.5 text-xs text-[var(--text-tertiary)]">{pc.tip}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
