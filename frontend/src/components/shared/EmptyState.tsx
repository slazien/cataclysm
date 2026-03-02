'use client';

import type { LucideIcon } from 'lucide-react';
import { cn } from '@/lib/utils';

interface EmptyStateProps {
  title?: string;
  message?: string;
  className?: string;
  icon?: LucideIcon;
  action?: { label: string; onClick: () => void };
  children?: React.ReactNode;
}

export function EmptyState({
  title = 'No session loaded',
  message = 'Upload a RaceChrono CSV to get started',
  className,
  icon: Icon,
  action,
  children,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center gap-3 py-20 text-center',
        className,
      )}
    >
      <div className="rounded-full bg-[var(--bg-elevated)] p-4">
        {Icon ? (
          <Icon className="h-8 w-8 text-[var(--cata-accent)]" />
        ) : (
          <svg
            className="h-8 w-8 text-[var(--text-muted)]"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={1.5}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"
            />
          </svg>
        )}
      </div>
      <h3 className="font-[family-name:var(--font-display)] text-lg font-medium text-[var(--text-primary)]">
        {title}
      </h3>
      <p className="max-w-sm text-sm text-[var(--text-secondary)]">{message}</p>
      {action && (
        <button
          type="button"
          onClick={action.onClick}
          className="mt-2 rounded-lg bg-[var(--cata-accent)] px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[var(--cata-accent)]/90"
        >
          {action.label}
        </button>
      )}
      {children}
    </div>
  );
}
