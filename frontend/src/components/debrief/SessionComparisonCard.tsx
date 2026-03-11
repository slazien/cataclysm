'use client';

import { useMemo } from 'react';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { useSession } from '@/hooks/useSession';
import { useOptimalComparison, useConsistency } from '@/hooks/useAnalysis';
import { usePreviousSessionDelta } from '@/hooks/usePreviousSessionDelta';
import { useSessionStore } from '@/stores';
import { formatLapTime, normalizeScore, parseSessionDate } from '@/lib/formatters';
import type { SessionSummary, OptimalComparisonData } from '@/lib/types';

interface SessionComparisonCardProps {
  session: SessionSummary;
  optimalComparison: OptimalComparisonData | undefined;
}

function DeltaIndicator({ value, unit, inverted = false }: { value: number; unit: string; inverted?: boolean }) {
  const threshold = unit === 's' ? 0.05 : 1;
  if (Math.abs(value) < threshold) {
    return (
      <span className="inline-flex items-center gap-0.5 text-xs text-[var(--text-secondary)]">
        <Minus className="h-3 w-3" />
        <span className="tabular-nums">{Math.abs(value).toFixed(1)}{unit}</span>
      </span>
    );
  }
  // For lap times, negative = improved. For consistency, positive = improved
  const improved = inverted ? value > 0 : value < 0;
  return (
    <span
      className={`inline-flex items-center gap-0.5 text-xs font-semibold ${
        improved ? 'text-[var(--color-throttle)]' : 'text-[var(--color-brake)]'
      }`}
    >
      {improved ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
      <span className="tabular-nums">
        {value > 0 ? '+' : ''}{value.toFixed(1)}{unit}
      </span>
    </span>
  );
}

function MetricRow({
  label,
  current,
  previous,
  delta,
  unit,
  inverted = false,
}: {
  label: string;
  current: string;
  previous: string;
  delta: number;
  unit: string;
  inverted?: boolean;
}) {
  return (
    <div className="flex items-center justify-between py-1.5">
      <span className="text-xs text-[var(--text-secondary)]">{label}</span>
      <div className="flex items-center gap-3">
        <span className="text-xs tabular-nums text-[var(--text-secondary)]">{previous}</span>
        <span className="text-[var(--text-secondary)]">→</span>
        <span className="text-xs font-semibold tabular-nums text-[var(--text-primary)]">{current}</span>
        <DeltaIndicator value={delta} unit={unit} inverted={inverted} />
      </div>
    </div>
  );
}

export function SessionComparisonCard({ session, optimalComparison }: SessionComparisonCardProps) {
  const { cornerDeltas, prevSessionId, isPending } = usePreviousSessionDelta(session, optimalComparison);
  const { data: prevSession } = useSession(prevSessionId);
  const { data: prevOptimal } = useOptimalComparison(prevSessionId);
  const { data: currentConsistency } = useConsistency(session.session_id);
  const { data: prevConsistency } = useConsistency(prevSessionId);

  // Format previous session date
  const prevDateStr = prevSession?.session_date
    ? parseSessionDate(prevSession.session_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
    : null;
  const currentDateStr = session.session_date
    ? parseSessionDate(session.session_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
    : null;

  const currentBestLap = session.best_lap_time_s;
  const prevBestLap = prevSession?.best_lap_time_s;
  const lapDelta = currentBestLap != null && prevBestLap != null ? currentBestLap - prevBestLap : null;

  const currentConsScore = currentConsistency?.lap_consistency
    ? Math.round(normalizeScore(currentConsistency.lap_consistency.consistency_score))
    : null;
  const prevConsScore = prevConsistency?.lap_consistency
    ? Math.round(normalizeScore(prevConsistency.lap_consistency.consistency_score))
    : null;
  const consDelta = currentConsScore != null && prevConsScore != null ? currentConsScore - prevConsScore : null;

  const currentGap = optimalComparison?.is_valid ? optimalComparison.total_gap_s : null;
  const prevGap = prevOptimal?.is_valid ? prevOptimal.total_gap_s : null;
  // For gap: negative delta = improved (gap shrank)
  const gapDelta = currentGap != null && prevGap != null ? currentGap - prevGap : null;

  // Sort corner deltas by absolute value (biggest changes first)
  const sortedCornerDeltas = useMemo(() => {
    if (!cornerDeltas) return [];
    return Array.from(cornerDeltas.values())
      .filter((d) => Math.abs(d.delta_s) >= 0.05)
      .sort((a, b) => Math.abs(b.delta_s) - Math.abs(a.delta_s))
      .slice(0, 6);
  }, [cornerDeltas]);

  if (!prevSessionId || isPending) return null;
  if (!prevSession) return null;

  return (
    <div className="rounded-xl border border-[var(--cata-border)] bg-[var(--bg-surface)] p-5">
      <h3 className="mb-1 border-l-[3px] border-[var(--text-secondary)] pl-3 font-[family-name:var(--font-display)] text-sm font-bold uppercase tracking-widest text-[var(--text-secondary)]">
        Session Comparison
      </h3>
      <p className="mb-4 pl-[15px] text-[11px] text-[var(--text-secondary)]">
        {prevDateStr} vs {currentDateStr} at {session.track_name}
      </p>

      {/* Summary metrics */}
      <div className="mb-4 divide-y divide-[var(--cata-border)]">
        {lapDelta != null && currentBestLap != null && prevBestLap != null && (
          <MetricRow
            label="Best Lap"
            previous={formatLapTime(prevBestLap)}
            current={formatLapTime(currentBestLap)}
            delta={lapDelta}
            unit="s"
          />
        )}
        {consDelta != null && currentConsScore != null && prevConsScore != null && (
          <MetricRow
            label="Consistency"
            previous={String(prevConsScore)}
            current={String(currentConsScore)}
            delta={consDelta}
            unit=""
            inverted
          />
        )}
        {gapDelta != null && currentGap != null && prevGap != null && (
          <MetricRow
            label="Gap to Optimal"
            previous={`${prevGap.toFixed(1)}s`}
            current={`${currentGap.toFixed(1)}s`}
            delta={gapDelta}
            unit="s"
          />
        )}
      </div>

      {/* Per-corner changes */}
      {sortedCornerDeltas.length > 0 && (
        <div>
          <h4 className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
            Corner Changes
          </h4>
          <div className="space-y-1.5">
            {sortedCornerDeltas.map((d) => {
              const improved = d.delta_s > 0;
              const barWidth = Math.min(100, Math.abs(d.delta_s) * 100); // scale to %
              return (
                <div key={d.corner_number} className="flex items-center gap-2">
                  <span className="w-8 text-right text-xs font-semibold tabular-nums text-[var(--text-primary)]">
                    T{d.corner_number}
                  </span>
                  <div className="relative h-4 flex-1 overflow-hidden rounded-sm bg-[var(--bg-base)]">
                    <div
                      className="absolute inset-y-0 left-0 rounded-sm"
                      style={{
                        width: `${barWidth}%`,
                        backgroundColor: improved
                          ? 'var(--color-throttle)'
                          : 'var(--color-brake)',
                        opacity: 0.6,
                      }}
                    />
                  </div>
                  <span
                    className={`w-16 text-right text-xs font-semibold tabular-nums ${
                      improved ? 'text-[var(--color-throttle)]' : 'text-[var(--color-brake)]'
                    }`}
                  >
                    {improved ? '−' : '+'}{Math.abs(d.delta_s).toFixed(1)}s
                    {improved ? ' better' : ' worse'}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
