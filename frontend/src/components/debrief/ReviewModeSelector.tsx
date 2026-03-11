'use client';

import { cn } from '@/lib/utils';

export type ReviewMode = '5m' | '15m' | '1hr';

const MODES: { key: ReviewMode; label: string; description: string }[] = [
  { key: '5m', label: '5 min', description: 'Quick glance' },
  { key: '15m', label: '15 min', description: 'Full review' },
  { key: '1hr', label: '1 hr', description: 'Deep dive' },
];

const STORAGE_KEY = 'cataclysm-debrief-review-mode';

export function getStoredReviewMode(): ReviewMode {
  if (typeof window === 'undefined') return '5m';
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored === '5m' || stored === '15m' || stored === '1hr') return stored;
  return '5m';
}

export function setStoredReviewMode(mode: ReviewMode) {
  localStorage.setItem(STORAGE_KEY, mode);
}

interface ReviewModeSelectorProps {
  mode: ReviewMode;
  onChange: (mode: ReviewMode) => void;
}

export function ReviewModeSelector({ mode, onChange }: ReviewModeSelectorProps) {
  return (
    <div className="flex items-center gap-1 rounded-lg border border-[var(--cata-border)] bg-[var(--bg-base)] p-1">
      {MODES.map((m) => (
        <button
          key={m.key}
          type="button"
          onClick={() => onChange(m.key)}
          title={m.description}
          className={cn(
            'min-h-[36px] rounded-md px-3 py-1.5 text-xs font-medium transition-colors',
            mode === m.key
              ? 'bg-[var(--cata-accent)] text-[var(--bg-base)] shadow-sm'
              : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]',
          )}
        >
          {m.label}
        </button>
      ))}
    </div>
  );
}
