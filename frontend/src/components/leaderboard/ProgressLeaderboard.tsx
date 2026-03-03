'use client';

import React, { useCallback } from 'react';
import { useProgressLeaderboard } from '@/hooks/useProgress';
import type { ProgressEntry } from '@/lib/types';
import { formatTimeShort } from '@/lib/formatters';
import { cn } from '@/lib/utils';

interface ProgressLeaderboardProps {
  trackName: string;
  days?: number;
}

function formatRate(rate: number): string {
  const sign = rate >= 0 ? '+' : '';
  return `${sign}${rate.toFixed(2)}s`;
}

function formatImprovement(total: number): string {
  const sign = total >= 0 ? '+' : '';
  return `${sign}${total.toFixed(1)}s`;
}

function PercentileBadge({ percentile }: { percentile: number }) {
  const color =
    percentile <= 10
      ? 'bg-yellow-500/20 text-yellow-300 border-yellow-500/30'
      : percentile <= 25
        ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
        : percentile <= 50
          ? 'bg-blue-500/20 text-blue-300 border-blue-500/30'
          : 'bg-zinc-500/20 text-zinc-300 border-zinc-500/30';

  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold',
        color,
      )}
    >
      Top {Math.max(1, Math.ceil(percentile))}%
    </span>
  );
}

export function ProgressLeaderboard({
  trackName,
  days = 90,
}: ProgressLeaderboardProps) {
  const { data, isLoading, error } = useProgressLeaderboard(trackName, days);

  const handleShare = useCallback(async () => {
    const text = `Check out the Improvement Leaderboard at ${trackName}!`;

    if (typeof navigator === 'undefined') return;
    if ('share' in navigator) {
      try {
        await (navigator as Navigator).share({ text, url: window.location.href });
      } catch {
        /* user cancelled */
      }
    } else {
      await (navigator as Navigator).clipboard.writeText(text);
    }
  }, [trackName]);

  if (isLoading) {
    return (
      <div className="animate-pulse text-sm text-zinc-400">
        Loading improvement leaderboard...
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-sm text-red-400">
        Failed to load improvement leaderboard
      </div>
    );
  }

  if (!data || data.entries.length === 0) {
    return null;
  }

  return (
    <div className="rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--cata-border)]">
        <div className="flex items-center gap-2">
          <span className="text-base">&#x1F4C8;</span>
          <h3 className="font-[family-name:var(--font-display)] text-sm font-semibold text-[var(--text-primary)]">
            Improvement Leaderboard
          </h3>
        </div>
        {data.your_rank != null && data.your_percentile != null && (
          <div className="flex items-center gap-2">
            <span className="text-xs text-[var(--text-muted)]">
              You: #{data.your_rank}
            </span>
            <PercentileBadge percentile={data.your_percentile} />
          </div>
        )}
      </div>

      {/* Table */}
      <table className="w-full text-sm">
        <thead>
          <tr className="text-xs text-[var(--text-muted)] border-b border-[var(--cata-border)]/50">
            <th className="px-4 py-2 text-left w-12">#</th>
            <th className="px-4 py-2 text-left">Driver</th>
            <th className="px-4 py-2 text-right">Rate/Session</th>
            <th className="hidden sm:table-cell px-4 py-2 text-right">Total</th>
            <th className="hidden md:table-cell px-4 py-2 text-right">Sessions</th>
          </tr>
        </thead>
        <tbody>
          {data.entries.map((entry: ProgressEntry) => {
            const isYou =
              data.your_rank != null && entry.rank === data.your_rank;
            return (
              <tr
                key={entry.rank}
                className={cn(
                  'border-b border-[var(--cata-border)]/30 transition-colors',
                  isYou
                    ? 'bg-[var(--cata-accent)]/10'
                    : 'hover:bg-[var(--bg-elevated)]/50',
                )}
              >
                <td className="px-4 py-2 font-mono text-[var(--text-muted)]">
                  {entry.rank}
                </td>
                <td className="px-4 py-2 text-[var(--text-primary)]">
                  <div className="flex items-center gap-2">
                    {entry.user_name}
                    {isYou && (
                      <span className="rounded-full bg-[var(--cata-accent)]/20 px-1.5 py-0.5 text-[10px] font-semibold text-[var(--cata-accent)]">
                        You
                      </span>
                    )}
                  </div>
                  <div className="mt-0.5 text-[10px] text-[var(--text-muted)] md:hidden">
                    {formatTimeShort(entry.best_lap_first)} &rarr;{' '}
                    {formatTimeShort(entry.best_lap_latest)}
                  </div>
                </td>
                <td
                  className={cn(
                    'px-4 py-2 text-right font-mono',
                    entry.improvement_rate_s < 0
                      ? 'text-[var(--color-throttle)]'
                      : 'text-[var(--color-brake)]',
                  )}
                >
                  {formatRate(entry.improvement_rate_s)}
                </td>
                <td
                  className={cn(
                    'hidden sm:table-cell px-4 py-2 text-right font-mono',
                    entry.total_improvement_s < 0
                      ? 'text-[var(--color-throttle)]'
                      : 'text-[var(--color-brake)]',
                  )}
                >
                  {formatImprovement(entry.total_improvement_s)}
                </td>
                <td className="hidden md:table-cell px-4 py-2 text-right text-[var(--text-muted)]">
                  {entry.n_sessions}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      {/* Footer */}
      <div className="flex items-center justify-between px-4 py-2 border-t border-[var(--cata-border)]">
        <span className="text-xs text-[var(--text-muted)]">
          Last {days} days
        </span>
        <button
          type="button"
          onClick={handleShare}
          className="flex items-center gap-1 text-xs font-medium text-[var(--cata-accent)] hover:underline"
        >
          Share
        </button>
      </div>
    </div>
  );
}
