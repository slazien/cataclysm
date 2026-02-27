'use client';

import { Sparkles } from 'lucide-react';

interface CoachingSummaryHeroProps {
  report: { status: string; summary?: string | null } | null;
}

export function CoachingSummaryHero({ report }: CoachingSummaryHeroProps) {
  const isLoading = !report || report.status === 'generating';
  const summary = report?.summary;

  return (
    <div className="rounded-xl border border-[var(--cata-accent)]/30 bg-gradient-to-r from-[var(--cata-accent)]/5 to-transparent p-5">
      <div className="mb-2 flex items-center gap-2">
        <Sparkles className="h-4 w-4 text-[var(--cata-accent)]" />
        <span className="text-xs font-semibold uppercase tracking-wider text-[var(--cata-accent)]">
          AI Coaching Summary
        </span>
      </div>

      {isLoading ? (
        <div className="space-y-2">
          <div className="h-4 w-3/4 animate-pulse rounded bg-[var(--bg-elevated)]" />
          <div className="h-4 w-1/2 animate-pulse rounded bg-[var(--bg-elevated)]" />
          <p className="mt-2 text-xs text-[var(--text-muted)]">Generating coaching insights...</p>
        </div>
      ) : report?.status === 'error' ? (
        <p className="text-sm text-[var(--text-muted)]">{summary ?? 'Coaching report unavailable.'}</p>
      ) : (
        <p className="text-sm leading-relaxed text-[var(--text-primary)]">{summary}</p>
      )}
    </div>
  );
}
