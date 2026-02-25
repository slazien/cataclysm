'use client';

import { cn } from '@/lib/utils';

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
    <div
      className={cn(
        'rounded-lg border px-4 py-3 transition-colors',
        highlightStyles[highlight],
        className,
      )}
    >
      <p className="text-xs font-medium uppercase tracking-wider text-[var(--text-muted)]">
        {label}
      </p>
      <p className="mt-1 text-2xl font-semibold tabular-nums text-[var(--text-primary)]">
        {value}
      </p>
      <div className="mt-1 flex items-center gap-2">
        {delta !== undefined && (
          <span
            className={cn(
              'text-sm font-medium tabular-nums',
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
          <span className="text-xs text-[var(--text-muted)]">{deltaLabel ?? subtitle}</span>
        )}
      </div>
    </div>
  );
}
