'use client';

import { Sparkles } from 'lucide-react';
import { MarkdownText } from '@/components/shared/MarkdownText';
import { useUnits } from '@/hooks/useUnits';
import { formatCoachingText } from '@/lib/textUtils';

interface CoachingSummaryHeroProps {
  report: { status: string; summary?: string | null } | null;
}

/** Split summary into a prominent first sentence and the rest. */
function splitSummary(text: string): { lead: string; rest: string } {
  // Match first sentence ending with . ! or ? followed by a space or end-of-string
  // Use [\s\S] instead of /s dotAll flag for broader TS target compat
  const match = text.match(/^([\s\S]+?[.!?])(\s+([\s\S]*))?$/);
  if (match) {
    return { lead: match[1].trim(), rest: (match[3] ?? '').trim() };
  }
  return { lead: text, rest: '' };
}

export function CoachingSummaryHero({ report }: CoachingSummaryHeroProps) {
  const isLoading = !report || report.status === 'generating';
  const { resolveSpeed } = useUnits();
  const summary = report?.summary ? formatCoachingText(resolveSpeed(report.summary)) : report?.summary;

  return (
    <div className="overflow-hidden rounded-xl border border-[var(--cata-accent)]/30 bg-gradient-to-r from-[var(--cata-accent)]/5 to-transparent p-5">
      <div className="mb-3 flex items-center gap-2">
        <Sparkles className="h-4 w-4 text-[var(--cata-accent)]" />
        <span className="font-[family-name:var(--font-display)] text-xs font-semibold uppercase tracking-wider text-[var(--cata-accent)]">
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
      ) : summary ? (
        <div className="border-l-[3px] border-[var(--cata-accent)] pl-4">
          {(() => {
            const { lead, rest } = splitSummary(summary);
            return (
              <>
                <p className="font-[family-name:var(--font-display)] text-base font-semibold leading-snug text-[var(--text-primary)]">
                  <MarkdownText>{lead}</MarkdownText>
                </p>
                {rest && (
                  <p className="mt-2 text-sm leading-relaxed text-[var(--text-secondary)]">
                    <MarkdownText>{rest}</MarkdownText>
                  </p>
                )}
              </>
            );
          })()}
        </div>
      ) : (
        <p className="text-sm text-[var(--text-muted)]">No coaching summary available.</p>
      )}
    </div>
  );
}
