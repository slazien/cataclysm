'use client';

import { useState } from 'react';
import { ChevronDown } from 'lucide-react';
import { MarkdownText } from '@/components/shared/MarkdownText';
import { useUnits } from '@/hooks/useUnits';
import type { MergedPriority } from '@/lib/types';
import { cn } from '@/lib/utils';

interface TimeLossCornersProps {
  corners: MergedPriority[];
}

function CornerRow({ pc }: { pc: MergedPriority }) {
  const [expanded, setExpanded] = useState(false);
  const { resolveSpeed } = useUnits();

  return (
    <button
      type="button"
      onClick={() => setExpanded((v) => !v)}
      className="flex w-full items-start gap-3 rounded-lg bg-[var(--bg-base)] px-4 py-3 text-left transition-colors hover:bg-[var(--bg-elevated)] min-h-[44px]"
    >
      {/* Corner number — display font, bold */}
      <span className="w-10 shrink-0 font-[family-name:var(--font-display)] text-lg font-bold text-[var(--text-primary)] leading-tight mt-0.5">
        T{pc.corner}
      </span>

      {/* Tip — full text when expanded, 2-line clamp when collapsed */}
      <span className={cn('min-w-0 flex-1 text-sm text-[var(--text-secondary)] text-left', !expanded && 'line-clamp-2')}>
        <MarkdownText>{resolveSpeed(pc.tip ?? 'Review corner data in Deep Dive')}</MarkdownText>
      </span>

      <span className="shrink-0 flex items-center gap-2">
        {/* Time delta — display font, green for gain */}
        <span className="font-[family-name:var(--font-display)] text-lg font-bold tracking-tight text-[var(--color-throttle)]">
          -{pc.time_cost_s.toFixed(2)}s
        </span>
        <ChevronDown
          className={cn(
            'h-4 w-4 shrink-0 text-[var(--text-secondary)] transition-transform',
            expanded && 'rotate-180',
          )}
        />
      </span>
    </button>
  );
}

export function TimeLossCorners({ corners }: TimeLossCornersProps) {
  return (
    <div className="rounded-xl border border-[var(--cata-border)] bg-[var(--bg-surface)] p-5">
      {/* Section header with amber left-border accent */}
      <h3 className="mb-4 border-l-[3px] border-[var(--cata-accent)] pl-3 font-[family-name:var(--font-display)] text-sm font-bold uppercase tracking-widest text-[var(--cata-accent)]">
        Top {corners.length} Focus
      </h3>

      {/* Expandable list — tap to reveal full coaching tip */}
      <div className="space-y-2">
        {corners.map((pc) => (
          <CornerRow key={pc.corner} pc={pc} />
        ))}
      </div>
    </div>
  );
}
