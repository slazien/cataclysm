'use client';

import { cn } from '@/lib/utils';

interface EmptyStateProps {
  title?: string;
  message?: string;
  className?: string;
  children?: React.ReactNode;
}

export function EmptyState({
  title = 'No session loaded',
  message = 'Upload a RaceChrono CSV to get started',
  className,
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
      </div>
      <h3 className="text-lg font-medium text-[var(--text-primary)]">{title}</h3>
      <p className="max-w-sm text-sm text-[var(--text-secondary)]">{message}</p>
      {children}
    </div>
  );
}
