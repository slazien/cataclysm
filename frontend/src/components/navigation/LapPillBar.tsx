'use client';

import { motion } from 'motion/react';
import { useSessionStore, useAnalysisStore } from '@/stores';
import { useSessionLaps } from '@/hooks/useSession';
import { LapPill } from '@/components/shared/LapPill';
import { formatLapTime } from '@/lib/formatters';
import { ScrollArea, ScrollBar } from '@/components/ui/scroll-area';

const staggerContainer = {
  animate: { transition: { staggerChildren: 0.03 } },
};

const staggerItem = {
  initial: { opacity: 0, x: -8 },
  animate: { opacity: 1, x: 0 },
};

export function LapPillBar() {
  const activeSessionId = useSessionStore((s) => s.activeSessionId);
  const selectedLaps = useAnalysisStore((s) => s.selectedLaps);
  const selectLaps = useAnalysisStore((s) => s.selectLaps);
  const { data: laps } = useSessionLaps(activeSessionId);

  if (!laps || laps.length === 0) return null;

  const cleanLaps = laps.filter((l) => l.is_clean);
  if (cleanLaps.length === 0) return null;

  const bestLapTime = Math.min(...cleanLaps.map((l) => l.lap_time_s));

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
        {cleanLaps.map((lap, index) => {
          const selIdx = selectedLaps.indexOf(lap.lap_number);
          const role = selIdx === 0 ? 'reference' as const
            : selIdx === 1 ? 'compare' as const
            : undefined;
          return (
            <motion.div key={lap.lap_number} variants={staggerItem}>
              <LapPill
                lapNumber={lap.lap_number}
                time={formatLapTime(lap.lap_time_s)}
                isPb={lap.lap_time_s === bestLapTime}
                selected={selIdx >= 0}
                colorIndex={index}
                role={role}
                onClick={() => handleToggle(lap.lap_number)}
              />
            </motion.div>
          );
        })}
      </motion.div>
      <ScrollBar orientation="horizontal" />
    </ScrollArea>
  );
}
