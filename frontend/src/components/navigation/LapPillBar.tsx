'use client';

import { motion } from 'motion/react';
import { Flag } from 'lucide-react';
import { useSessionStore, useAnalysisStore } from '@/stores';
import { useSessionLaps } from '@/hooks/useSession';
import { LapPill } from '@/components/shared/LapPill';
import { formatLapTime } from '@/lib/formatters';
import { ScrollArea, ScrollBar } from '@/components/ui/scroll-area';
import {
  Popover,
  PopoverTrigger,
  PopoverContent,
} from '@/components/ui/popover';
import { cn } from '@/lib/utils';
import {
  isUserExcluded,
  useToggleLapTag,
  EXCLUDE_TAGS,
} from '@/hooks/useLapTags';
import type { LapSummary } from '@/lib/types';

const staggerContainer = {
  animate: { transition: { staggerChildren: 0.03 } },
};

const staggerItem = {
  initial: { opacity: 0, x: -8 },
  animate: { opacity: 1, x: 0 },
};

const TAG_LABELS: Record<string, string> = {
  traffic: 'Traffic',
  'off-line': 'Off-line',
  experimental: 'Experimental',
  'cold-tires': 'Cold tires',
};

function ExcludeTagPopover({
  lap,
  sessionId,
}: {
  lap: LapSummary;
  sessionId: string;
}) {
  const excluded = isUserExcluded(lap);
  const { mutate: toggleTag, isPending } = useToggleLapTag(sessionId);

  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label={`Tag lap ${lap.lap_number}`}
          className={cn(
            'absolute -right-3 -top-3 z-10 flex h-11 w-11 items-center justify-center',
            'transition-opacity duration-150',
            excluded
              ? 'opacity-100'
              : 'opacity-0 group-hover:opacity-100',
            excluded && 'sm:opacity-100',
          )}
          onClick={(e) => e.stopPropagation()}
        >
          <span
            className={cn(
              'flex h-5 w-5 items-center justify-center rounded-full',
              excluded ? 'bg-amber-500/90' : 'bg-[var(--bg-surface)]/80',
            )}
          >
            <Flag
              className={cn(
                'h-3 w-3',
                excluded ? 'text-white' : 'text-[var(--text-muted)]',
              )}
            />
          </span>
        </button>
      </PopoverTrigger>
      <PopoverContent
        side="bottom"
        align="start"
        sideOffset={6}
        className="bg-foreground text-background w-48 rounded-lg border-0 p-3 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <p className="mb-2 text-xs font-semibold uppercase tracking-wider opacity-70">
          Exclude L{lap.lap_number}
        </p>
        <div className="flex flex-col gap-1">
          {[...EXCLUDE_TAGS].map((tag) => {
            const checked = lap.tags.includes(tag);
            return (
              <label
                key={tag}
                className={cn(
                  'flex min-h-[44px] cursor-pointer items-center gap-2.5 rounded-md px-2 py-1.5',
                  'hover:bg-background/10 transition-colors',
                  isPending && 'pointer-events-none opacity-50',
                )}
              >
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={() =>
                    toggleTag({ lapNumber: lap.lap_number, tag, enable: !checked })
                  }
                  className="h-4 w-4 accent-amber-500"
                />
                <span className="text-sm">{TAG_LABELS[tag] ?? tag}</span>
              </label>
            );
          })}
        </div>
      </PopoverContent>
    </Popover>
  );
}

export function LapPillBar() {
  const activeSessionId = useSessionStore((s) => s.activeSessionId);
  const selectedLaps = useAnalysisStore((s) => s.selectedLaps);
  const selectLaps = useAnalysisStore((s) => s.selectLaps);
  const { data: laps } = useSessionLaps(activeSessionId);

  if (!laps || laps.length === 0) return null;

  // Show clean laps + any laps with user tags (anomalous-only laps stay hidden)
  const visibleLaps = laps.filter(
    (l) => l.is_clean || l.tags.length > 0,
  );
  if (visibleLaps.length === 0) return null;

  // Best lap time calculated from clean (non-excluded) laps only
  const cleanLaps = laps.filter((l) => l.is_clean);
  const bestLapTime =
    cleanLaps.length > 0
      ? Math.min(...cleanLaps.map((l) => l.lap_time_s))
      : null;

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

  return (
    <ScrollArea className="max-w-[50vw] touch-pan-x">
      <motion.div
        className="flex items-center gap-1.5 px-1 py-1.5"
        initial="initial"
        animate="animate"
        variants={staggerContainer}
      >
        {visibleLaps.map((lap, index) => {
          const excluded = isUserExcluded(lap);
          const selIdx = selectedLaps.indexOf(lap.lap_number);
          const role =
            selIdx === 0
              ? ('reference' as const)
              : selIdx === 1
                ? ('compare' as const)
                : undefined;

          // First exclusion tag for badge display
          const firstTag = lap.tags.find((t) => EXCLUDE_TAGS.has(t));

          return (
            <motion.div
              key={lap.lap_number}
              variants={staggerItem}
              className="group relative"
            >
              <LapPill
                lapNumber={lap.lap_number}
                time={formatLapTime(lap.lap_time_s)}
                isPb={bestLapTime !== null && lap.lap_time_s === bestLapTime}
                selected={selIdx >= 0}
                colorIndex={index}
                role={role}
                onClick={() => handleToggle(lap.lap_number)}
                className={cn(excluded && 'opacity-40 [&>span:last-child]:line-through')}
              />

              {/* Amber tag badge below pill for excluded laps */}
              {excluded && firstTag && (
                <span className="absolute -bottom-2.5 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-sm bg-amber-500/80 px-1 py-px text-[8px] font-bold uppercase leading-none text-white">
                  {TAG_LABELS[firstTag] ?? firstTag}
                </span>
              )}

              {/* Flag icon with popover — positioned top-right of pill */}
              {activeSessionId && (
                <ExcludeTagPopover
                  lap={lap}
                  sessionId={activeSessionId}
                />
              )}
            </motion.div>
          );
        })}
      </motion.div>
      <ScrollBar orientation="horizontal" />
    </ScrollArea>
  );
}
