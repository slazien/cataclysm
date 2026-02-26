'use client';

import { useState, useCallback } from 'react';
import { ArrowLeft, Share2, Check, Trophy, Clock, MapPin } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { cn } from '@/lib/utils';
import { formatLapTime } from '@/lib/formatters';
import { Button } from '@/components/ui/button';
import { DeltaTimeChart } from './DeltaTimeChart';
import type { ComparisonResult } from '@/lib/types';

interface ComparisonOverviewProps {
  data: ComparisonResult;
}

export function ComparisonOverview({ data }: ComparisonOverviewProps) {
  const router = useRouter();
  const [copied, setCopied] = useState(false);

  const handleShare = useCallback(async () => {
    const url = `${window.location.origin}/compare/${data.session_a_id}?with=${data.session_b_id}`;
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback for environments without clipboard API
      const textArea = document.createElement('textarea');
      textArea.value = url;
      document.body.appendChild(textArea);
      textArea.select();
      document.execCommand('copy');
      document.body.removeChild(textArea);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }, [data.session_a_id, data.session_b_id]);

  const aFaster = data.delta_s < 0;
  const deltaAbs = Math.abs(data.delta_s);

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6 p-4 lg:p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={() => router.back()}
            title="Go back"
            className="text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
          >
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-xl font-semibold text-[var(--text-primary)]">
              Session Comparison
            </h1>
            <p className="text-sm text-[var(--text-secondary)]">
              Side-by-side analysis of two sessions
            </p>
          </div>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={handleShare}
          className="gap-1.5 border-[var(--cata-border)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
        >
          {copied ? (
            <>
              <Check className="h-3.5 w-3.5 text-[var(--color-throttle)]" />
              Copied
            </>
          ) : (
            <>
              <Share2 className="h-3.5 w-3.5" />
              Share
            </>
          )}
        </Button>
      </div>

      {/* Winner Banner */}
      <div
        className={cn(
          'rounded-lg border px-5 py-4',
          aFaster
            ? 'border-[var(--color-throttle)]/30 bg-[var(--color-throttle)]/5'
            : 'border-[var(--color-brake)]/30 bg-[var(--color-brake)]/5',
        )}
      >
        <div className="flex items-center gap-3">
          <Trophy
            className={cn(
              'h-5 w-5',
              aFaster ? 'text-[var(--color-throttle)]' : 'text-[var(--color-brake)]',
            )}
          />
          <div>
            <p className="text-sm font-medium text-[var(--text-primary)]">
              {aFaster ? 'Session A' : 'Session B'} is faster by{' '}
              <span className="font-mono font-semibold">{deltaAbs.toFixed(3)}s</span>
            </p>
            <p className="text-xs text-[var(--text-secondary)]">
              Based on best lap comparison
            </p>
          </div>
        </div>
      </div>

      {/* Side-by-side Session Cards */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* Session A */}
        <div
          className={cn(
            'rounded-lg border px-5 py-4',
            aFaster
              ? 'border-[var(--color-throttle)]/30 bg-[var(--bg-surface)]'
              : 'border-[var(--cata-border)] bg-[var(--bg-surface)]',
          )}
        >
          <div className="mb-3 flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
              Session A
            </span>
            {aFaster && (
              <span className="rounded-full bg-[var(--color-throttle)]/15 px-2 py-0.5 text-[10px] font-semibold uppercase text-[var(--color-throttle)]">
                Faster
              </span>
            )}
          </div>
          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-2">
              <MapPin className="h-3.5 w-3.5 text-[var(--text-muted)]" />
              <span className="text-sm text-[var(--text-primary)]">{data.session_a_track}</span>
            </div>
            <div className="flex items-center gap-2">
              <Clock className="h-3.5 w-3.5 text-[var(--text-muted)]" />
              <span className="font-mono text-lg font-semibold text-[var(--text-primary)]">
                {data.session_a_best_lap !== null
                  ? formatLapTime(data.session_a_best_lap)
                  : '--:--'}
              </span>
            </div>
            <p className="font-mono text-xs text-[var(--text-muted)]">
              {data.session_a_id.slice(0, 8)}
            </p>
          </div>
        </div>

        {/* Session B */}
        <div
          className={cn(
            'rounded-lg border px-5 py-4',
            !aFaster
              ? 'border-[var(--color-throttle)]/30 bg-[var(--bg-surface)]'
              : 'border-[var(--cata-border)] bg-[var(--bg-surface)]',
          )}
        >
          <div className="mb-3 flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
              Session B
            </span>
            {!aFaster && (
              <span className="rounded-full bg-[var(--color-throttle)]/15 px-2 py-0.5 text-[10px] font-semibold uppercase text-[var(--color-throttle)]">
                Faster
              </span>
            )}
          </div>
          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-2">
              <MapPin className="h-3.5 w-3.5 text-[var(--text-muted)]" />
              <span className="text-sm text-[var(--text-primary)]">{data.session_b_track}</span>
            </div>
            <div className="flex items-center gap-2">
              <Clock className="h-3.5 w-3.5 text-[var(--text-muted)]" />
              <span className="font-mono text-lg font-semibold text-[var(--text-primary)]">
                {data.session_b_best_lap !== null
                  ? formatLapTime(data.session_b_best_lap)
                  : '--:--'}
              </span>
            </div>
            <p className="font-mono text-xs text-[var(--text-muted)]">
              {data.session_b_id.slice(0, 8)}
            </p>
          </div>
        </div>
      </div>

      {/* Delta-T Chart */}
      {data.distance_m.length > 0 && (
        <div className="rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-4">
          <h2 className="mb-3 text-sm font-medium text-[var(--text-primary)]">
            Delta-T Over Distance
          </h2>
          <p className="mb-4 text-xs text-[var(--text-secondary)]">
            Green = Session A gaining time, Red = Session A losing time
          </p>
          <div className="h-64">
            <DeltaTimeChart
              distance_m={data.distance_m}
              delta_time_s={data.delta_time_s}
              totalDelta={data.delta_s}
            />
          </div>
        </div>
      )}

      {/* Corner Deltas Table */}
      {data.corner_deltas.length > 0 && (
        <div className="rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-4">
          <h2 className="mb-4 text-sm font-medium text-[var(--text-primary)]">
            Corner-by-Corner Comparison
          </h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--cata-border)]">
                  <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                    Corner
                  </th>
                  <th className="px-3 py-2 text-right text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                    A Min Speed
                  </th>
                  <th className="px-3 py-2 text-right text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                    B Min Speed
                  </th>
                  <th className="px-3 py-2 text-right text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                    Delta
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.corner_deltas.map((cd) => {
                  const isPositive = cd.speed_diff_mph > 0;
                  const isNegative = cd.speed_diff_mph < 0;
                  return (
                    <tr
                      key={cd.corner_number}
                      className="border-b border-[var(--cata-border)]/50 transition-colors hover:bg-[var(--bg-elevated)]"
                    >
                      <td className="px-3 py-2 font-medium text-[var(--text-primary)]">
                        T{cd.corner_number}
                      </td>
                      <td className="px-3 py-2 text-right font-mono text-[var(--text-secondary)]">
                        {cd.a_min_speed_mph.toFixed(1)} mph
                      </td>
                      <td className="px-3 py-2 text-right font-mono text-[var(--text-secondary)]">
                        {cd.b_min_speed_mph.toFixed(1)} mph
                      </td>
                      <td
                        className={cn(
                          'px-3 py-2 text-right font-mono font-medium',
                          isPositive && 'text-[var(--color-throttle)]',
                          isNegative && 'text-[var(--color-brake)]',
                          !isPositive && !isNegative && 'text-[var(--text-muted)]',
                        )}
                      >
                        {isPositive ? '+' : ''}
                        {cd.speed_diff_mph.toFixed(1)} mph
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
