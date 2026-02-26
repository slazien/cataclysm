'use client';

import { useSessionStore, useAnalysisStore } from '@/stores';
import { useSessionLaps } from '@/hooks/useSession';
import { useDelta } from '@/hooks/useAnalysis';
import { formatLapTime } from '@/lib/formatters';
import { colors } from '@/lib/design-tokens';

export function ComparisonLegend() {
  const sessionId = useSessionStore((s) => s.activeSessionId);
  const selectedLaps = useAnalysisStore((s) => s.selectedLaps);
  const { data: laps } = useSessionLaps(sessionId);

  const refLap = selectedLaps.length >= 2 ? selectedLaps[0] : null;
  const compLap = selectedLaps.length >= 2 ? selectedLaps[1] : null;
  const { data: delta } = useDelta(sessionId, refLap, compLap);

  if (selectedLaps.length < 2 || !laps) return null;

  const refInfo = laps.find((l) => l.lap_number === selectedLaps[0]);
  const cmpInfo = laps.find((l) => l.lap_number === selectedLaps[1]);

  if (!refInfo || !cmpInfo) return null;

  const totalDelta = delta?.total_delta_s;

  return (
    <div className="flex items-center gap-4 rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] px-4 py-2 text-xs">
      {/* Reference lap */}
      <div className="flex items-center gap-1.5">
        <span
          className="inline-block h-2.5 w-2.5 rounded-full"
          style={{ backgroundColor: colors.comparison.reference }}
        />
        <span className="font-medium text-[var(--text-primary)]">
          L{refInfo.lap_number}
        </span>
        <span className="tabular-nums text-[var(--text-secondary)]">
          {formatLapTime(refInfo.lap_time_s)}
        </span>
        <span className="text-[var(--text-muted)]">Reference</span>
      </div>

      {/* Compare lap */}
      <div className="flex items-center gap-1.5">
        <span
          className="inline-block h-2.5 w-2.5 rounded-full"
          style={{ backgroundColor: colors.comparison.compare }}
        />
        <span className="font-medium text-[var(--text-primary)]">
          L{cmpInfo.lap_number}
        </span>
        <span className="tabular-nums text-[var(--text-secondary)]">
          {formatLapTime(cmpInfo.lap_time_s)}
        </span>
        <span className="text-[var(--text-muted)]">Compare</span>
      </div>

      {/* Delta summary */}
      {totalDelta !== undefined && (
        <div
          className="ml-auto rounded-md px-2 py-0.5 font-mono font-semibold tabular-nums"
          style={{
            color: totalDelta > 0 ? colors.motorsport.brake : colors.motorsport.throttle,
            backgroundColor:
              totalDelta > 0 ? 'rgba(239, 68, 68, 0.12)' : 'rgba(34, 197, 94, 0.12)',
          }}
        >
          {totalDelta >= 0 ? '+' : ''}{totalDelta.toFixed(3)}s
        </div>
      )}
    </div>
  );
}
