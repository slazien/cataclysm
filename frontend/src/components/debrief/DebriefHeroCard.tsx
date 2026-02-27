'use client';

import { formatLapTime } from '@/lib/formatters';

interface DebriefHeroCardProps {
  bestLapTime: number;
  consistencyScore: number | null;
  trackName: string;
  sessionDate: string;
  nLaps: number;
}

export function DebriefHeroCard({
  bestLapTime,
  consistencyScore,
  trackName,
  sessionDate,
  nLaps,
}: DebriefHeroCardProps) {
  return (
    <div className="rounded-xl border border-[var(--cata-border)] bg-gradient-to-br from-[var(--bg-surface)] to-[var(--bg-elevated)] p-6 text-center">
      {/* Track + Date */}
      <p className="text-xs font-medium uppercase tracking-wider text-[var(--text-tertiary)]">
        {trackName}
      </p>
      <p className="mb-4 text-[10px] text-[var(--text-muted)]">{sessionDate}</p>

      {/* Best Lap Time — hero */}
      <p className="font-mono text-4xl font-bold text-[var(--text-primary)]">
        {formatLapTime(bestLapTime)}
      </p>
      <p className="mb-4 text-xs text-[var(--grade-a)]">Best Lap</p>

      {/* Stats row */}
      <div className="flex items-center justify-center gap-6">
        {consistencyScore !== null && (
          <div>
            <p className="text-lg font-bold text-[var(--text-primary)]">{consistencyScore}%</p>
            <p className="text-[10px] text-[var(--text-tertiary)]">Consistency</p>
          </div>
        )}
        <div>
          <p className="text-lg font-bold text-[var(--text-primary)]">{nLaps}</p>
          <p className="text-[10px] text-[var(--text-tertiary)]">Laps</p>
        </div>
      </div>
    </div>
  );
}
