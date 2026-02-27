'use client';

import { useState, useMemo } from 'react';
import { ChevronDown, Star } from 'lucide-react';
import { useSessionStore, useAnalysisStore } from '@/stores';
import { useSessionLaps } from '@/hooks/useSession';
import { formatLapTime } from '@/lib/formatters';
import { cn } from '@/lib/utils';
import { Popover, PopoverTrigger, PopoverContent } from '@/components/ui/popover';

/** Map a 0-1 percentile to a green-yellow-red HSL color string. */
function percentileColor(percentile: number): string {
  // 0 = best (green, hue 130), 1 = worst (red, hue 0)
  const hue = Math.round(130 * (1 - percentile));
  return `hsl(${hue}, 70%, 35%)`;
}

/** Check if a lap should be dimmed (warm-up / outlier). */
function isDimmed(
  lapNumber: number,
  lapTimeS: number,
  bestTimeS: number,
  firstCleanLapNumber: number,
): boolean {
  if (lapNumber === firstCleanLapNumber) return true; // first lap = warm-up
  if (lapTimeS > bestTimeS * 1.15) return true; // >115% of best
  return false;
}

export function LapGridSelector() {
  const [open, setOpen] = useState(false);
  const activeSessionId = useSessionStore((s) => s.activeSessionId);
  const selectedLaps = useAnalysisStore((s) => s.selectedLaps);
  const selectLaps = useAnalysisStore((s) => s.selectLaps);
  const { data: laps } = useSessionLaps(activeSessionId);

  const cleanLaps = useMemo(() => laps?.filter((l) => l.is_clean) ?? [], [laps]);

  const bestLapTime = useMemo(
    () => (cleanLaps.length > 0 ? Math.min(...cleanLaps.map((l) => l.lap_time_s)) : 0),
    [cleanLaps],
  );

  const worstLapTime = useMemo(
    () => (cleanLaps.length > 0 ? Math.max(...cleanLaps.map((l) => l.lap_time_s)) : 0),
    [cleanLaps],
  );

  const firstCleanLapNumber = useMemo(
    () => (cleanLaps.length > 0 ? cleanLaps[0].lap_number : -1),
    [cleanLaps],
  );

  // Build the trigger label from selected laps
  const triggerLabel = useMemo(() => {
    if (selectedLaps.length === 0) return 'Select laps...';
    const parts = selectedLaps.map((lapNum) => {
      const lap = cleanLaps.find((l) => l.lap_number === lapNum);
      if (!lap) return `L${lapNum}`;
      return `L${lapNum} ${formatLapTime(lap.lap_time_s)}`;
    });
    return parts.join(' vs ');
  }, [selectedLaps, cleanLaps]);

  function handleToggle(lapNumber: number) {
    if (selectedLaps.includes(lapNumber)) {
      selectLaps(selectedLaps.filter((n) => n !== lapNumber));
    } else if (selectedLaps.length < 2) {
      selectLaps([...selectedLaps, lapNumber]);
    } else {
      // Replace the oldest (first) selection
      selectLaps([selectedLaps[1], lapNumber]);
    }
  }

  if (cleanLaps.length === 0) return null;

  const timeRange = worstLapTime - bestLapTime;

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          className={cn(
            'inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs font-medium transition-colors',
            'border-[var(--cata-border)] text-[var(--text-secondary)]',
            'hover:border-[var(--text-muted)] hover:text-[var(--text-primary)]',
          )}
        >
          <span className="max-w-[260px] truncate">{triggerLabel}</span>
          <ChevronDown className="h-3 w-3 shrink-0 opacity-60" />
        </button>
      </PopoverTrigger>

      <PopoverContent
        align="end"
        sideOffset={6}
        className="w-auto min-w-[260px] max-w-[360px] border-[var(--cata-border)] bg-[var(--bg-surface)] p-3"
      >
        <p className="mb-2 text-[11px] font-medium uppercase tracking-wider text-[var(--text-muted)]">
          Select up to 2 laps
        </p>

        {/* Grid */}
        <div className="grid grid-cols-3 gap-1.5 sm:grid-cols-4 lg:grid-cols-5">
          {cleanLaps.map((lap) => {
            const isPb = lap.lap_time_s === bestLapTime;
            const percentile = timeRange > 0 ? (lap.lap_time_s - bestLapTime) / timeRange : 0;
            const dimmed = isDimmed(lap.lap_number, lap.lap_time_s, bestLapTime, firstCleanLapNumber);
            const selIdx = selectedLaps.indexOf(lap.lap_number);
            const isSelected = selIdx >= 0;
            const role = selIdx === 0 ? 'REF' : selIdx === 1 ? 'CMP' : null;

            return (
              <button
                key={lap.lap_number}
                type="button"
                onClick={() => handleToggle(lap.lap_number)}
                className={cn(
                  'relative flex flex-col items-center justify-center rounded-md px-1 py-1.5 text-center transition-all',
                  'cursor-pointer select-none',
                  dimmed && !isSelected && 'opacity-50',
                )}
                style={{
                  backgroundColor: percentileColor(percentile),
                  border: isSelected
                    ? `2px solid ${role === 'REF' ? 'var(--cata-accent, #58a6ff)' : '#f97316'}`
                    : '2px solid transparent',
                }}
              >
                {/* PB star */}
                {isPb && (
                  <Star
                    className="absolute -right-0.5 -top-0.5 h-3 w-3 fill-yellow-400 text-yellow-400"
                  />
                )}

                {/* Role badge */}
                {role && (
                  <span
                    className={cn(
                      'absolute -left-0.5 -top-0.5 rounded-sm px-1 text-[8px] font-bold leading-tight text-white',
                      role === 'REF' ? 'bg-[#58a6ff]' : 'bg-[#f97316]',
                    )}
                  >
                    {role}
                  </span>
                )}

                <span className="text-[11px] font-semibold leading-none text-white/90">
                  L{lap.lap_number}
                </span>
                <span className="mt-0.5 text-[10px] tabular-nums leading-none text-white/70">
                  {formatLapTime(lap.lap_time_s)}
                </span>
              </button>
            );
          })}
        </div>

        {/* Legend */}
        <div className="mt-2.5 flex items-center gap-3 text-[10px] text-[var(--text-muted)]">
          <span className="flex items-center gap-1">
            <span
              className="inline-block h-2 w-4 rounded-sm"
              style={{ background: 'linear-gradient(to right, hsl(130,70%,35%), hsl(65,70%,35%), hsl(0,70%,35%))' }}
            />
            Fast → Slow
          </span>
          <span className="flex items-center gap-1">
            <Star className="h-2.5 w-2.5 fill-yellow-400 text-yellow-400" />
            PB
          </span>
          <span className="opacity-50">Dimmed = warm-up/outlier</span>
        </div>
      </PopoverContent>
    </Popover>
  );
}
