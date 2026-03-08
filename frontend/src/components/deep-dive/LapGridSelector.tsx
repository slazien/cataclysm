'use client';

import { useState, useMemo, useEffect } from 'react';
import { motion } from 'motion/react';
import { ChevronDown, Star } from 'lucide-react';
import { useSessionStore, useAnalysisStore } from '@/stores';
import { useSessionLaps } from '@/hooks/useSession';
import { formatLapTime } from '@/lib/formatters';
import { cn } from '@/lib/utils';
import { Popover, PopoverTrigger, PopoverContent } from '@/components/ui/popover';

const gridStaggerContainer = {
  animate: { transition: { staggerChildren: 0.03 } },
};

const gridStaggerItem = {
  initial: { opacity: 0, scale: 0.85 },
  animate: { opacity: 1, scale: 1 },
};

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

  // Close on Escape key (capture phase ensures it fires even if other layers exist)
  useEffect(() => {
    if (!open) return;
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') setOpen(false);
    }
    document.addEventListener('keydown', handleKeyDown, true);
    return () => document.removeEventListener('keydown', handleKeyDown, true);
  }, [open]);

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
          <span className="max-w-[120px] truncate sm:max-w-[200px] lg:max-w-[260px]">{triggerLabel}</span>
          <ChevronDown className="h-3 w-3 shrink-0 opacity-60" />
        </button>
      </PopoverTrigger>

      <PopoverContent
        align="end"
        sideOffset={6}
        className="w-[calc(100vw-2rem)] border-[var(--cata-border)] bg-[var(--bg-surface)] p-3 sm:w-auto sm:min-w-[260px] sm:max-w-[360px]"
      >
        <p className="mb-2 text-[11px] font-medium uppercase tracking-wider text-[var(--text-secondary)]">
          Select up to 2 laps
        </p>

        {/* Grid */}
        <motion.div
          className="grid grid-cols-3 gap-1.5 sm:grid-cols-4 lg:grid-cols-5"
          initial="initial"
          animate="animate"
          variants={gridStaggerContainer}
        >
          {cleanLaps.map((lap) => {
            const isPb = lap.lap_time_s === bestLapTime;
            const percentile = timeRange > 0 ? (lap.lap_time_s - bestLapTime) / timeRange : 0;
            const dimmed = isDimmed(lap.lap_number, lap.lap_time_s, bestLapTime, firstCleanLapNumber);
            const selIdx = selectedLaps.indexOf(lap.lap_number);
            const isSelected = selIdx >= 0;
            const role = selIdx === 0 ? 'REF' : selIdx === 1 ? 'CMP' : null;

            return (
              <motion.button
                key={lap.lap_number}
                type="button"
                onClick={() => handleToggle(lap.lap_number)}
                variants={gridStaggerItem}
                whileTap={{ scale: 0.93 }}
                whileHover={{ scale: 1.06 }}
                transition={{ type: 'spring', stiffness: 400, damping: 25 }}
                className={cn(
                  'relative flex flex-col items-center justify-center rounded-md px-1 py-2 text-center transition-[color,border-color,background-color] min-h-[44px]',
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
                {/* PB star — subtle breathing pulse */}
                {isPb && (
                  <motion.div
                    className="absolute -right-0.5 -top-0.5"
                    animate={{ scale: [1, 1.03, 1] }}
                    transition={{ duration: 0.6, ease: 'easeInOut', repeat: Infinity, repeatDelay: 2 }}
                  >
                    <Star
                      className="h-3 w-3 fill-yellow-400 text-yellow-400"
                    />
                  </motion.div>
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
                <span className="mt-0.5 text-[11px] tabular-nums leading-none text-white/70">
                  {formatLapTime(lap.lap_time_s)}
                </span>
              </motion.button>
            );
          })}
        </motion.div>

        {/* Legend */}
        <div className="mt-2.5 flex items-center gap-3 text-[11px] text-[var(--text-secondary)]">
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
