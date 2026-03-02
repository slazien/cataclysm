'use client';

import { formatLapTime } from '@/lib/formatters';

interface DebriefHeroCardProps {
  bestLapTime: number;
  consistencyScore: number | null;
  trackName: string;
  sessionDate: string;
  nLaps: number;
  /** Optional delta vs previous best in seconds (negative = improvement) */
  deltaPrevBest?: number | null;
  /** Whether this is a personal best session */
  isPB?: boolean;
}

export function DebriefHeroCard({
  bestLapTime,
  consistencyScore,
  trackName,
  sessionDate,
  nLaps,
  deltaPrevBest,
  isPB,
}: DebriefHeroCardProps) {
  return (
    <div className="rounded-xl border border-[var(--cata-border)] bg-gradient-to-br from-[var(--bg-surface)] to-[var(--bg-elevated)] p-6 text-center lg:p-10">
      {/* Track + Date — secondary info, muted */}
      <p className="text-xs font-medium uppercase tracking-widest text-[var(--text-muted)]">
        {trackName}
      </p>
      <p className="mb-3 text-[10px] text-[var(--text-muted)]">{sessionDate}</p>

      {/* Best Lap Time — pit board hero, massive */}
      <p
        className="font-[family-name:var(--font-display)] text-5xl font-bold tracking-tight text-[var(--text-primary)] lg:text-7xl"
        style={isPB ? { color: 'var(--cata-accent)' } : undefined}
      >
        {formatLapTime(bestLapTime)}
      </p>

      {/* PB badge + delta row */}
      <div className="mt-1 flex items-center justify-center gap-3">
        {isPB && (
          <span className="rounded-full bg-amber-500/15 px-2.5 py-0.5 text-xs font-bold uppercase tracking-wide text-[var(--cata-accent)]">
            PB
          </span>
        )}
        <span className="text-xs font-medium text-[var(--grade-a)]">Best Lap</span>
      </div>

      {/* Delta vs previous best */}
      {deltaPrevBest != null && (
        <p className="mt-2 font-[family-name:var(--font-display)] text-lg font-semibold tracking-tight text-[var(--color-throttle)]">
          {deltaPrevBest < 0 ? '' : '+'}
          {deltaPrevBest.toFixed(3)}s vs previous best
        </p>
      )}

      {/* Stats row — horizontal, display font for numbers */}
      <div className="mt-5 flex items-center justify-center gap-8 border-t border-[var(--cata-border)] pt-4">
        {consistencyScore !== null && (
          <div>
            <p className="font-[family-name:var(--font-display)] text-2xl font-bold text-[var(--text-primary)] lg:text-3xl">
              {consistencyScore}%
            </p>
            <p className="text-[10px] font-medium uppercase tracking-wider text-[var(--text-muted)]">
              Consistency
            </p>
          </div>
        )}
        <div>
          <p className="font-[family-name:var(--font-display)] text-2xl font-bold text-[var(--text-primary)] lg:text-3xl">
            {nLaps}
          </p>
          <p className="text-[10px] font-medium uppercase tracking-wider text-[var(--text-muted)]">
            Laps
          </p>
        </div>
      </div>
    </div>
  );
}
