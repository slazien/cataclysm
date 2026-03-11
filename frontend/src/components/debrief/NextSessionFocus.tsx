'use client';

import { Target } from 'lucide-react';
import { useUnits } from '@/hooks/useUnits';
import { formatCoachingText } from '@/lib/textUtils';
import type { PriorityCorner } from '@/lib/types';

interface NextSessionFocusProps {
  priority: PriorityCorner;
}

/**
 * Bold, impossible-to-miss "Next Session Focus" banner.
 * Shows the #1 priority corner tip + time cost.
 * Designed to be readable from arm's length (trackside phone glance).
 */
export function NextSessionFocus({ priority }: NextSessionFocusProps) {
  const { resolveSpeed } = useUnits();
  const tip = formatCoachingText(resolveSpeed(priority.tip));
  const timeCost = priority.time_cost_s;

  return (
    <div className="rounded-xl border-2 border-[var(--cata-accent)]/40 bg-gradient-to-r from-amber-500/10 to-transparent p-5 lg:p-6">
      <div className="flex items-start gap-3">
        <Target className="mt-1 h-6 w-6 shrink-0 text-[var(--cata-accent)]" />
        <div className="min-w-0">
          <h3 className="mb-1 font-[family-name:var(--font-display)] text-xs font-bold uppercase tracking-widest text-[var(--cata-accent)]">
            Next Session Focus
          </h3>
          <p className="font-[family-name:var(--font-display)] text-lg font-bold leading-snug text-[var(--text-primary)] lg:text-xl">
            {tip}
          </p>
          {timeCost > 0 && (
            <p className="mt-1 text-sm text-[var(--text-secondary)]">
              This alone could save you{' '}
              <span className="font-semibold text-[var(--color-throttle)]">
                ~{timeCost.toFixed(1)}s/lap
              </span>
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
