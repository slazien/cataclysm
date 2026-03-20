'use client';

import { useCallback } from 'react';
import { Share2 } from 'lucide-react';
import { formatLapTime } from '@/lib/formatters';
import { useUnits } from '@/hooks/useUnits';
import { formatCoachingText } from '@/lib/textUtils';
import type { SessionSummary, MergedPriority } from '@/lib/types';

interface TracksideCardProps {
  session: SessionSummary;
  consistencyScore: number | null;
  topCorners: MergedPriority[];
  gapToOptimal: number | null;
  optimalLapTime: number | null;
}

/**
 * Single-screen trackside quick card — designed for pit-lane phone glance.
 * Large text, high contrast, no scrolling needed.
 * Uses `tip` (concise actionable text) for display, `issue` (full analysis) for share.
 */
export function TracksideCard({
  session,
  consistencyScore,
  topCorners,
  gapToOptimal,
  optimalLapTime,
}: TracksideCardProps) {
  const { resolveSpeed } = useUnits();
  const bestLap = session.best_lap_time_s;

  /** Resolve speed templates + strip formatting markers */
  const fmt = useCallback(
    (text: string) => formatCoachingText(resolveSpeed(text)),
    [resolveSpeed],
  );

  const handleShare = useCallback(async () => {
    const lines = [
      `${session.track_name ?? 'Track'} — ${session.session_date_local ?? session.session_date ?? ''}`,
      '',
      `Best: ${bestLap != null ? formatLapTime(bestLap) : '—'}`,
      optimalLapTime != null ? `Optimal: ${formatLapTime(optimalLapTime)}` : null,
      gapToOptimal != null ? `Gap: ${gapToOptimal.toFixed(1)}s` : null,
      consistencyScore != null ? `Consistency: ${consistencyScore}%` : null,
      '',
      'Focus:',
      ...topCorners.map(
        (c) => `  T${c.corner}: ${fmt(c.tip ?? 'Focus on this corner')} (−${c.time_cost_s.toFixed(1)}s)`,
      ),
    ].filter((l): l is string => l != null);
    const text = lines.join('\n');

    if (navigator.share) {
      try {
        await navigator.share({ text });
        return;
      } catch {
        // User cancelled or not supported — fall through to clipboard
      }
    }
    await navigator.clipboard.writeText(text);
  }, [session, bestLap, optimalLapTime, gapToOptimal, consistencyScore, topCorners, fmt]);

  return (
    <div className="rounded-xl border-2 border-[var(--cata-border)] bg-[var(--bg-surface)] p-5">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="border-l-[3px] border-[var(--text-secondary)] pl-3 font-[family-name:var(--font-display)] text-sm font-bold uppercase tracking-widest text-[var(--text-secondary)]">
          Trackside Card
        </h3>
        <button
          type="button"
          onClick={handleShare}
          className="flex min-h-[44px] items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)]"
          title="Share trackside card"
        >
          <Share2 className="h-3.5 w-3.5" />
          Share
        </button>
      </div>

      {/* Track + Date */}
      <p className="text-xs font-medium uppercase tracking-widest text-[var(--text-secondary)]">
        {session.track_name ?? 'Unknown Track'}
      </p>
      <p className="mb-4 text-[11px] text-[var(--text-secondary)]">
        {session.session_date_local ?? session.session_date ?? ''}
      </p>

      {/* Focus — biggest text, uses tip (concise actionable) */}
      {topCorners.length > 0 && (
        <div className="mb-4 rounded-lg bg-amber-500/10 px-4 py-3">
          <p className="text-[10px] font-bold uppercase tracking-widest text-[var(--cata-accent)]">
            Focus
          </p>
          <p className="font-[family-name:var(--font-display)] text-lg font-bold leading-snug text-[var(--text-primary)]">
            T{topCorners[0].corner}: {fmt(topCorners[0].tip ?? 'Focus on this corner')}
          </p>
        </div>
      )}

      {/* Top corners list — tip text, no truncation */}
      {topCorners.length > 0 && (
        <div className="mb-4 space-y-2">
          {topCorners.map((c) => (
            <div key={c.corner} className="flex items-start gap-2 text-sm">
              <span className="shrink-0 font-medium text-[var(--text-primary)]">T{c.corner}</span>
              <span className="min-w-0 flex-1 leading-snug text-[var(--text-secondary)]">{fmt(c.tip ?? 'Review in Deep Dive')}</span>
              <span className="shrink-0 font-mono text-xs font-semibold text-[var(--color-brake)]">
                −{c.time_cost_s.toFixed(1)}s
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Stats row */}
      <div className="flex items-center justify-between border-t border-[var(--cata-border)] pt-3 text-center">
        <div>
          <p className="font-[family-name:var(--font-display)] text-lg font-bold text-[var(--text-primary)]">
            {bestLap != null ? formatLapTime(bestLap) : '—'}
          </p>
          <p className="text-[10px] uppercase tracking-wider text-[var(--text-secondary)]">Best</p>
        </div>
        {optimalLapTime != null && (
          <div>
            <p className="font-[family-name:var(--font-display)] text-lg font-bold text-[var(--cata-accent)]">
              {formatLapTime(optimalLapTime)}
            </p>
            <p className="text-[10px] uppercase tracking-wider text-[var(--text-secondary)]">
              Optimal
            </p>
          </div>
        )}
        {consistencyScore != null && (
          <div>
            <p className="font-[family-name:var(--font-display)] text-lg font-bold text-[var(--text-primary)]">
              {consistencyScore}%
            </p>
            <p className="text-[10px] uppercase tracking-wider text-[var(--text-secondary)]">
              Consistency
            </p>
          </div>
        )}
        {gapToOptimal != null && gapToOptimal > 0 && (
          <div>
            <p className="font-[family-name:var(--font-display)] text-lg font-bold text-[var(--color-brake)]">
              {gapToOptimal.toFixed(1)}s
            </p>
            <p className="text-[10px] uppercase tracking-wider text-[var(--text-secondary)]">Gap</p>
          </div>
        )}
      </div>
    </div>
  );
}
