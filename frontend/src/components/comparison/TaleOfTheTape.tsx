'use client';

import { cn } from '@/lib/utils';
import { formatLapTime } from '@/lib/formatters';
import { AiInsight } from '@/components/shared/AiInsight';

interface SessionSide {
  trackName: string;
  bestLap: number | null;
  score?: number | null;
  driverName?: string | null;
}

interface TaleOfTheTapeProps {
  sessionA: SessionSide;
  sessionB: SessionSide;
  aiSummary?: string | null;
}

function StatRow({
  label,
  valueA,
  valueB,
  format,
  lowerIsBetter = false,
}: {
  label: string;
  valueA: number | null | undefined;
  valueB: number | null | undefined;
  format: (v: number) => string;
  lowerIsBetter?: boolean;
}) {
  const aVal = valueA ?? null;
  const bVal = valueB ?? null;

  let aWins = false;
  let bWins = false;
  if (aVal !== null && bVal !== null) {
    if (lowerIsBetter) {
      aWins = aVal < bVal;
      bWins = bVal < aVal;
    } else {
      aWins = aVal > bVal;
      bWins = bVal > aVal;
    }
  }

  return (
    <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-3 border-b border-[var(--cata-border)]/50 py-3 last:border-b-0">
      <div className="text-right">
        <span
          className={cn(
            'font-mono text-sm font-semibold',
            aWins ? 'text-[var(--color-throttle)]' : 'text-[var(--text-secondary)]',
          )}
        >
          {aVal !== null ? format(aVal) : '--'}
        </span>
      </div>
      <div className="text-center">
        <span className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
          {label}
        </span>
      </div>
      <div className="text-left">
        <span
          className={cn(
            'font-mono text-sm font-semibold',
            bWins ? 'text-[var(--color-throttle)]' : 'text-[var(--text-secondary)]',
          )}
        >
          {bVal !== null ? format(bVal) : '--'}
        </span>
      </div>
    </div>
  );
}

export function TaleOfTheTape({ sessionA, sessionB, aiSummary }: TaleOfTheTapeProps) {
  return (
    <div className="rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-4 lg:p-6">
      {/* Header with driver names and VS */}
      <div className="mb-4 grid grid-cols-[1fr_auto_1fr] items-center gap-3">
        <div className="text-right">
          <p className="text-sm font-semibold text-[var(--text-primary)] font-[family-name:var(--font-display)]">
            {sessionA.driverName || 'Driver A'}
          </p>
          <p className="text-xs text-[var(--text-muted)]">{sessionA.trackName}</p>
        </div>
        <div className="flex h-10 w-10 items-center justify-center rounded-full border border-[var(--cata-accent)]/40 bg-[var(--cata-accent)]/10">
          <span className="text-xs font-bold text-[var(--cata-accent)] font-[family-name:var(--font-display)]">
            VS
          </span>
        </div>
        <div className="text-left">
          <p className="text-sm font-semibold text-[var(--text-primary)] font-[family-name:var(--font-display)]">
            {sessionB.driverName || 'Driver B'}
          </p>
          <p className="text-xs text-[var(--text-muted)]">{sessionB.trackName}</p>
        </div>
      </div>

      {/* Stat Rows */}
      <StatRow
        label="Best Lap"
        valueA={sessionA.bestLap}
        valueB={sessionB.bestLap}
        format={formatLapTime}
        lowerIsBetter
      />
      {(sessionA.score != null || sessionB.score != null) && (
        <StatRow
          label="Score"
          valueA={sessionA.score}
          valueB={sessionB.score}
          format={(v) => v.toFixed(0)}
        />
      )}

      {/* AI Summary */}
      {aiSummary && (
        <div className="mt-4">
          <AiInsight mode="inline">{aiSummary}</AiInsight>
        </div>
      )}
    </div>
  );
}
