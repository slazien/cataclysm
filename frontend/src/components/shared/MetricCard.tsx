'use client';

import { motion as m } from 'motion/react';
import { cn } from '@/lib/utils';
import { motion as motionTokens } from '@/lib/design-tokens';

type Highlight = 'pb' | 'good' | 'bad' | 'none';

interface MetricCardProps {
  label: string;
  value: string | number;
  subtitle?: string;
  delta?: number;
  deltaLabel?: string;
  highlight?: Highlight;
  className?: string;
}

const highlightStyles: Record<Highlight, string> = {
  pb: 'border-[var(--color-pb)]/30 bg-[var(--color-pb)]/5',
  good: 'border-[var(--color-throttle)]/30 bg-[var(--color-throttle)]/5',
  bad: 'border-[var(--color-brake)]/30 bg-[var(--color-brake)]/5',
  none: 'border-[var(--cata-border)] bg-[var(--bg-surface)]',
};

const cardVariants = {
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0 },
};

export function MetricCard({
  label,
  value,
  subtitle,
  delta,
  deltaLabel,
  highlight = 'none',
  className,
}: MetricCardProps) {
  const isPositive = delta !== undefined && delta > 0;
  const isNegative = delta !== undefined && delta < 0;

  return (
    <m.div
      variants={cardVariants}
      initial="initial"
      animate="animate"
      transition={motionTokens.cardEntrance}
      className={cn(
        'overflow-hidden rounded-lg border px-3 py-2 transition-colors',
        highlightStyles[highlight],
        className,
      )}
    >
      <p className="truncate font-[family-name:var(--font-display)] text-[10px] font-medium uppercase tracking-wider text-[var(--text-muted)]">
        {label}
      </p>
      <p className="mt-0.5 truncate font-[family-name:var(--font-display)] text-base font-semibold tracking-tight tabular-nums text-[var(--text-primary)] sm:text-lg">
        {value}
      </p>
      {(delta !== undefined || subtitle || deltaLabel) && (
        <div className="mt-0.5 flex items-center gap-1.5">
          {delta !== undefined && (
            <span
              className={cn(
                'text-xs font-medium tabular-nums',
                isPositive && 'text-[var(--color-brake)]',
                isNegative && 'text-[var(--color-throttle)]',
                !isPositive && !isNegative && 'text-[var(--text-muted)]',
              )}
            >
              {isPositive ? '+' : ''}
              {delta.toFixed(3)}s
            </span>
          )}
          {(subtitle || deltaLabel) && (
            <span className="text-[11px] text-[var(--text-muted)]">{deltaLabel ?? subtitle}</span>
          )}
        </div>
      )}
    </m.div>
  );
}
