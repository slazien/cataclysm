'use client';

import type { PriorityCorner } from '@/lib/types';

interface TimeLossCornersProps {
  corners: PriorityCorner[];
}

export function TimeLossCorners({ corners }: TimeLossCornersProps) {
  return (
    <div className="rounded-xl border border-[var(--cata-border)] bg-[var(--bg-surface)] p-5">
      {/* Section header with amber left-border accent */}
      <h3 className="mb-4 border-l-[3px] border-[var(--cata-accent)] pl-3 font-[family-name:var(--font-display)] text-sm font-bold uppercase tracking-widest text-[var(--cata-accent)]">
        Top 3 Focus
      </h3>

      {/* Clean scannable list — one line per corner */}
      <div className="space-y-2">
        {corners.map((pc) => (
          <div
            key={pc.corner}
            className="flex items-center gap-3 rounded-lg bg-[var(--bg-base)] px-4 py-3"
          >
            {/* Corner number — display font, bold */}
            <span className="w-10 shrink-0 font-[family-name:var(--font-display)] text-lg font-bold text-[var(--text-primary)]">
              T{pc.corner}
            </span>

            {/* Tip — single line, truncated if needed */}
            <span className="min-w-0 flex-1 truncate text-sm text-[var(--text-secondary)]">
              {pc.tip}
            </span>

            {/* Time delta — right-aligned, display font, green for gain */}
            <span className="shrink-0 font-[family-name:var(--font-display)] text-lg font-bold tracking-tight text-[var(--color-throttle)]">
              -{pc.time_cost_s.toFixed(2)}s
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
