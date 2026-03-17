'use client';

import { useEffect, useRef, useState } from 'react';
import { Sparkles } from 'lucide-react';
import { MarkdownText } from '@/components/shared/MarkdownText';
import { ThumbsRating } from '@/components/shared/ThumbsRating';
import { useUnits } from '@/hooks/useUnits';
import { formatCoachingText } from '@/lib/textUtils';
import { useCoachingNav } from '@/hooks/useCoachingNav';
import { useCoachingFeedback } from '@/hooks/useCoachingFeedback';
import { useSessionStore } from '@/stores';
import type { CoachingReport } from '@/lib/types';

interface CoachingSummaryHeroProps {
  report: Pick<CoachingReport, 'status' | 'summary' | 'primary_focus' | 'generation_started_at' | 'generation_estimated_s'> | null;
  onRetry?: () => void;
}

/** Split summary into a prominent first sentence and the rest. */
function splitSummary(text: string): { lead: string; rest: string } {
  const match = text.match(/^([\s\S]+?[.!?])(\s+([\s\S]*))?$/);
  if (match) {
    return { lead: match[1].trim(), rest: (match[3] ?? '').trim() };
  }
  return { lead: text, rest: '' };
}

const GENERATION_TIMEOUT_S = 300;

function GeneratingProgress({ startedAt, estimatedS, onRetry }: { startedAt?: string | null; estimatedS?: number | null; onRetry?: () => void }) {
  const [progress, setProgress] = useState(0);
  const [timedOut, setTimedOut] = useState(false);
  const mountedAt = useRef(Date.now());

  useEffect(() => {
    const startMs = startedAt ? new Date(startedAt).getTime() : NaN;
    const hasValidStart = !Number.isNaN(startMs);

    const tick = () => {
      // Timeout: use server start time if available, otherwise time since mount
      const elapsedS = hasValidStart
        ? (Date.now() - startMs) / 1000
        : (Date.now() - mountedAt.current) / 1000;

      if (elapsedS > GENERATION_TIMEOUT_S) {
        setTimedOut(true);
      }

      if (hasValidStart && estimatedS && estimatedS > 0) {
        const pct = Math.min(95, (elapsedS / estimatedS) * 90);
        setProgress(Math.max(0, pct));
      }
    };

    tick();
    const id = setInterval(tick, 500);
    return () => clearInterval(id);
  }, [startedAt, estimatedS]);

  const hasEta = startedAt && estimatedS && estimatedS > 0;

  if (timedOut) {
    return (
      <div className="space-y-2">
        <p className="text-sm text-[var(--text-secondary)]">
          Coaching generation is taking longer than expected.
        </p>
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className="rounded-md border border-[var(--cata-accent)]/40 bg-[var(--cata-accent)]/10 px-3 py-1.5 text-xs font-medium text-[var(--cata-accent)] transition-colors hover:bg-[var(--cata-accent)]/20"
          >
            Retry
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {hasEta ? (
        <>
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-[var(--bg-elevated)]">
            <div
              className="h-full rounded-full bg-[var(--cata-accent)] transition-[width] duration-500 ease-out"
              style={{ width: `${progress}%` }}
            />
          </div>
          <p className="text-xs text-[var(--text-secondary)]">
            Generating coaching insights... ~{Math.ceil(estimatedS)}s
          </p>
        </>
      ) : (
        <>
          <div className="h-4 w-3/4 animate-pulse rounded bg-[var(--bg-elevated)]" />
          <div className="h-4 w-1/2 animate-pulse rounded bg-[var(--bg-elevated)]" />
          <p className="mt-2 text-xs text-[var(--text-secondary)]">Generating coaching insights...</p>
        </>
      )}
    </div>
  );
}

export function CoachingSummaryHero({ report, onRetry }: CoachingSummaryHeroProps) {
  const isLoading = !report || report.status === 'generating';
  const { resolveSpeed } = useUnits();
  const coachingNav = useCoachingNav();
  const activeSessionId = useSessionStore((s) => s.activeSessionId);
  const { getRating, submitFeedback } = useCoachingFeedback(activeSessionId);
  const summary = report?.summary ? formatCoachingText(resolveSpeed(report.summary)) : report?.summary;
  const primaryFocus = report?.primary_focus ? formatCoachingText(resolveSpeed(report.primary_focus)) : null;

  return (
    <div className="overflow-hidden rounded-xl border border-[var(--cata-accent)]/30 bg-gradient-to-r from-[var(--cata-accent)]/5 to-transparent p-4 sm:p-5">
      <div className="mb-3 flex items-center gap-2">
        <Sparkles className="h-4 w-4 text-[var(--cata-accent)]" />
        <span className="font-[family-name:var(--font-display)] text-xs font-semibold uppercase tracking-wider text-[var(--cata-accent)]">
          AI Coaching Summary
        </span>
      </div>

      {isLoading ? (
        <GeneratingProgress
          startedAt={report?.generation_started_at}
          estimatedS={report?.generation_estimated_s}
          onRetry={onRetry}
        />
      ) : report?.status === 'error' ? (
        <p className="text-sm text-[var(--text-secondary)]">{summary ?? 'Coaching report unavailable.'}</p>
      ) : summary ? (
        <div className="space-y-3">
          {primaryFocus && (
            <div className="rounded-lg bg-[var(--cata-accent)]/10 border border-[var(--cata-accent)]/20 px-4 py-3">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--cata-accent)]">
                Your #1 Focus
              </span>
              <p className="mt-1 text-sm font-medium leading-relaxed text-[var(--text-primary)]">
                <MarkdownText linkHandlers={coachingNav}>{primaryFocus}</MarkdownText>
              </p>
              <p className="mt-2 text-[11px] text-[var(--text-secondary)]">
                Based on Allen Berg corner prioritization methodology
              </p>
            </div>
          )}
          <div className="border-l-[3px] border-[var(--cata-accent)] pl-4">
            {(() => {
              const { lead, rest } = splitSummary(summary);
              return (
                <>
                  <p className="font-[family-name:var(--font-display)] text-base font-semibold leading-snug text-[var(--text-primary)]">
                    <MarkdownText linkHandlers={coachingNav}>{lead}</MarkdownText>
                  </p>
                  {rest && (
                    <p className="mt-2 text-sm leading-relaxed text-[var(--text-secondary)]">
                      <MarkdownText linkHandlers={coachingNav}>{rest}</MarkdownText>
                    </p>
                  )}
                </>
              );
            })()}
          </div>
          <div className="mt-3 flex justify-end">
            <ThumbsRating
              rating={getRating('summary')}
              onRate={(r) => submitFeedback.mutate({ section: 'summary', rating: r })}
              disabled={submitFeedback.isPending}
            />
          </div>
        </div>
      ) : (
        <p className="text-sm text-[var(--text-secondary)]">No coaching summary available.</p>
      )}
    </div>
  );
}
