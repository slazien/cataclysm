'use client';

import { useState } from 'react';
import { Trophy, Clock, Gauge, ChevronDown, ChevronUp, Quote } from 'lucide-react';
import { cn } from '@/lib/utils';
import { formatLapTime } from '@/lib/formatters';
import { ComparisonDeepDive } from '@/components/comparison/ComparisonDeepDive';
import type { ShareComparisonResult } from '@/lib/types';

interface ComparisonSummaryProps {
  comparison: ShareComparisonResult;
  inviterName: string;
  challengerName: string;
  trackName: string;
  token: string;
}

export function ComparisonSummary({
  comparison,
  inviterName,
  challengerName,
  trackName,
  token,
}: ComparisonSummaryProps) {
  const [expanded, setExpanded] = useState(false);

  const isTie = comparison.delta_s === 0;
  const aFaster = comparison.delta_s > 0;
  const deltaAbs = Math.abs(comparison.delta_s);
  const winnerName = aFaster ? inviterName : challengerName;

  // Count corners won by each driver
  const cornersWonA = comparison.corner_deltas.filter((c) => c.speed_diff_mph > 0).length;
  const cornersWonB = comparison.corner_deltas.filter((c) => c.speed_diff_mph < 0).length;
  const totalCorners = comparison.corner_deltas.length;

  return (
    <div className="flex flex-col gap-5">
      {/* Winner Banner */}
      <div className="relative overflow-hidden rounded-xl border border-emerald-500/30 bg-gradient-to-r from-emerald-900/20 via-emerald-800/10 to-emerald-900/20 px-6 py-5">
        <div className="flex items-center justify-center gap-3">
          <Trophy className="h-6 w-6 text-emerald-400" />
          <div className="text-center">
            <p className="text-base font-semibold text-[var(--text-primary)]">
              {isTie ? "It's a tie!" : winnerName === 'You' ? 'You win!' : `${winnerName} wins!`}
            </p>
            {!isTie && (
              <p className="mt-0.5 text-sm text-emerald-300/80">
                Faster by{' '}
                <span className="font-mono font-semibold">
                  {deltaAbs.toFixed(3)}s
                </span>
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Stat Pills */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        {/* Gap Pill */}
        <div className="rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] px-4 py-3 text-center">
          <div className="mb-1 flex items-center justify-center gap-1.5">
            <Clock className="h-3.5 w-3.5 text-[var(--text-secondary)]" />
            <span className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
              Gap
            </span>
          </div>
          <p className="font-mono text-lg font-semibold text-[var(--text-primary)]">
            {deltaAbs.toFixed(3)}s
          </p>
        </div>

        {/* Corners Won Pill */}
        <div className="rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] px-4 py-3 text-center">
          <div className="mb-1 flex items-center justify-center gap-1.5">
            <Gauge className="h-3.5 w-3.5 text-[var(--text-secondary)]" />
            <span className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
              Corners Won
            </span>
          </div>
          {totalCorners > 0 ? (
            <p className="text-sm text-[var(--text-primary)]">
              <span style={{ color: '#58a6ff' }} className="font-semibold">
                {cornersWonA}
              </span>
              <span className="mx-1 text-[var(--text-secondary)]">-</span>
              <span style={{ color: '#f97316' }} className="font-semibold">
                {cornersWonB}
              </span>
              <span className="ml-1 text-xs text-[var(--text-secondary)]">
                / {totalCorners}
              </span>
            </p>
          ) : (
            <p className="text-sm text-[var(--text-secondary)]">--</p>
          )}
        </div>

        {/* Lap Times Pill */}
        <div className="rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] px-4 py-3 text-center">
          <div className="mb-1">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
              Best Laps
            </span>
          </div>
          <div className="flex items-center justify-center gap-2 text-xs">
            <span
              className={cn(
                'font-mono font-semibold',
                aFaster ? 'text-[var(--color-throttle)]' : 'text-[var(--text-secondary)]',
              )}
            >
              {comparison.session_a_best_lap !== null
                ? formatLapTime(comparison.session_a_best_lap)
                : '--:--'}
            </span>
            <span className="text-[var(--text-secondary)]">vs</span>
            <span
              className={cn(
                'font-mono font-semibold',
                !aFaster ? 'text-[var(--color-throttle)]' : 'text-[var(--text-secondary)]',
              )}
            >
              {comparison.session_b_best_lap !== null
                ? formatLapTime(comparison.session_b_best_lap)
                : '--:--'}
            </span>
          </div>
        </div>
      </div>

      {/* AI Verdict Quote */}
      {comparison.ai_verdict && (
        <div className="flex gap-3 rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] px-4 py-3">
          <Quote className="mt-0.5 h-4 w-4 shrink-0 text-[var(--ai-icon)]" />
          <p className="text-sm italic leading-relaxed text-[var(--text-secondary)]">
            {comparison.ai_verdict}
          </p>
        </div>
      )}

      {/* Deep Dive Toggle */}
      <button
        type="button"
        onClick={() => setExpanded((prev) => !prev)}
        className={cn(
          'flex items-center justify-center gap-2 rounded-lg border px-5 py-2.5 text-sm font-medium transition-colors',
          expanded
            ? 'border-[var(--cata-accent)]/40 bg-[var(--cata-accent)]/10 text-[var(--cata-accent)]'
            : 'border-[var(--cata-border)] bg-[var(--bg-surface)] text-[var(--text-primary)] hover:border-[var(--text-muted)]/40',
        )}
      >
        {expanded ? (
          <>
            <ChevronUp className="h-4 w-4" />
            Hide Deep Dive
          </>
        ) : (
          <>
            <ChevronDown className="h-4 w-4" />
            Deep Dive
          </>
        )}
      </button>

      {/* Deep Dive Content */}
      {expanded && (
        <ComparisonDeepDive
          comparison={comparison}
          inviterName={inviterName}
          challengerName={challengerName}
          token={token}
        />
      )}
    </div>
  );
}
