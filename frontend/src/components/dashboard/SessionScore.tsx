'use client';

import { MetricCard } from '@/components/shared/MetricCard';

interface SessionScoreProps {
  score: number | null;
  isLoading: boolean;
}

export function SessionScore({ score, isLoading }: SessionScoreProps) {
  if (isLoading) {
    return (
      <div className="rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] px-4 py-3 animate-pulse">
        <div className="h-3 w-20 rounded bg-[var(--bg-elevated)]" />
        <div className="mt-2 h-8 w-16 rounded bg-[var(--bg-elevated)]" />
      </div>
    );
  }

  const displayScore = score !== null ? Math.round(score) : null;
  const highlight =
    displayScore !== null
      ? displayScore >= 80
        ? ('good' as const)
        : displayScore >= 60
          ? ('none' as const)
          : ('bad' as const)
      : ('none' as const);

  return (
    <MetricCard
      label="Session Score"
      value={displayScore !== null ? `${displayScore}/100` : '--'}
      subtitle={
        displayScore !== null
          ? displayScore >= 80
            ? 'Strong session'
            : displayScore >= 60
              ? 'Room to improve'
              : 'Focus on fundamentals'
          : undefined
      }
      highlight={highlight}
    />
  );
}
