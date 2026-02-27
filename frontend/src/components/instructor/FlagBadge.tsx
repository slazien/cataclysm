'use client';

import { cn } from '@/lib/utils';

const FLAG_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  attention: {
    bg: 'bg-amber-500/15',
    text: 'text-amber-400',
    label: 'Attention',
  },
  safety: {
    bg: 'bg-[var(--color-brake)]/15',
    text: 'text-[var(--color-brake)]',
    label: 'Safety',
  },
  improvement: {
    bg: 'bg-[var(--color-throttle)]/15',
    text: 'text-[var(--color-throttle)]',
    label: 'Improvement',
  },
  praise: {
    bg: 'bg-purple-500/15',
    text: 'text-purple-400',
    label: 'Praise',
  },
};

interface FlagBadgeProps {
  flagType: string;
  className?: string;
}

export function FlagBadge({ flagType, className }: FlagBadgeProps) {
  const style = FLAG_STYLES[flagType] ?? {
    bg: 'bg-[var(--bg-elevated)]',
    text: 'text-[var(--text-muted)]',
    label: flagType,
  };

  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider',
        style.bg,
        style.text,
        className,
      )}
    >
      {style.label}
    </span>
  );
}
