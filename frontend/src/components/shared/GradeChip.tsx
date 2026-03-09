'use client';

import { motion as m } from 'motion/react';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { cn } from '@/lib/utils';
import { motion as motionTokens } from '@/lib/design-tokens';
import { useUnits } from '@/hooks/useUnits';
import { resolveSpeedMarkers } from '@/lib/textUtils';

type Grade = 'A' | 'B' | 'C' | 'D' | 'F';

interface GradeChipProps {
  grade: Grade | string;
  reason?: string;
  className?: string;
}

const gradeColors: Record<string, string> = {
  A: 'bg-[var(--grade-a)]/15 text-[var(--grade-a)] border-[var(--grade-a)]/30',
  B: 'bg-[var(--grade-b)]/15 text-[var(--grade-b)] border-[var(--grade-b)]/30',
  C: 'bg-[var(--grade-c)]/15 text-[var(--grade-c)] border-[var(--grade-c)]/30',
  D: 'bg-[var(--grade-d)]/15 text-[var(--grade-d)] border-[var(--grade-d)]/30',
  F: 'bg-[var(--grade-f)]/15 text-[var(--grade-f)] border-[var(--grade-f)]/30',
};

const chipVariants = {
  initial: { opacity: 0, scale: 0.8 },
  animate: { opacity: 1, scale: 1 },
};

// Colorblind-safe indicators: shape/weight supplements color
const gradeIndicators: Record<string, { suffix: string; fontWeight: string }> = {
  A: { suffix: '\u00A0\u2713', fontWeight: 'font-bold' },
  B: { suffix: '\u00A0+', fontWeight: 'font-bold' },
  C: { suffix: '\u00A0~', fontWeight: 'font-medium' },
  D: { suffix: '\u00A0!', fontWeight: 'font-normal' },
  F: { suffix: '\u00A0\u25BC', fontWeight: 'font-bold' },
};

function ChipContent({ grade, className }: { grade: string; className?: string }) {
  const normalized = grade.toUpperCase();
  const colorClass = gradeColors[normalized] ?? gradeColors['C'];
  const indicator = gradeIndicators[normalized] ?? gradeIndicators['C'];

  return (
    <m.span
      variants={chipVariants}
      initial="initial"
      animate="animate"
      transition={motionTokens.gradeChip}
      className={cn(
        'inline-flex items-center justify-center rounded-md border px-2 py-0.5 text-xs',
        indicator.fontWeight,
        colorClass,
        className,
      )}
    >
      {normalized}
      {indicator.suffix && (
        <span className="text-[0.6rem] leading-none">{indicator.suffix}</span>
      )}
    </m.span>
  );
}

export function GradeChip({ grade, reason, className }: GradeChipProps) {
  const { isMetric } = useUnits();

  if (!reason) {
    return <ChipContent grade={grade} className={className} />;
  }

  const resolvedReason = resolveSpeedMarkers(reason, isMetric);

  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          className="inline-flex cursor-help"
          onClick={(e) => e.stopPropagation()}
        >
          <ChipContent grade={grade} className={className} />
        </button>
      </PopoverTrigger>
      <PopoverContent
        side="top"
        sideOffset={6}
        className="max-w-[220px] border-[var(--cata-border)] bg-[var(--bg-surface)] px-3 py-1.5 text-xs leading-relaxed text-[var(--text-primary)]"
      >
        {resolvedReason}
      </PopoverContent>
    </Popover>
  );
}
