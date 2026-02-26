'use client';

import { cn } from '@/lib/utils';
import { colors } from '@/lib/design-tokens';

interface LapPillProps {
  lapNumber: number;
  time: string;
  isPb?: boolean;
  selected?: boolean;
  colorIndex?: number;
  role?: 'reference' | 'compare';
  onClick?: () => void;
  className?: string;
}

export function LapPill({
  lapNumber,
  time,
  isPb = false,
  selected = false,
  colorIndex,
  role,
  onClick,
  className,
}: LapPillProps) {
  const roleColor = role
    ? colors.comparison[role]
    : colors.lap[(colorIndex ?? lapNumber - 1) % colors.lap.length];

  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition-all',
        selected
          ? 'border-transparent text-[var(--bg-base)]'
          : 'border-[var(--cata-border)] text-[var(--text-secondary)] hover:border-[var(--text-muted)]',
        className,
      )}
      style={
        selected
          ? { backgroundColor: roleColor, borderColor: roleColor }
          : undefined
      }
    >
      {isPb && <span className="text-[10px]" aria-label="Personal best">&#9733;</span>}
      {selected && role && (
        <span className="text-[9px] font-bold uppercase opacity-80">
          {role === 'reference' ? 'REF' : 'CMP'}
        </span>
      )}
      <span>L{lapNumber}</span>
      <span className="tabular-nums">{time}</span>
    </button>
  );
}
