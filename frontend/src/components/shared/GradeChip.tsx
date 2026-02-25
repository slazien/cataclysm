'use client';

import { cn } from '@/lib/utils';

type Grade = 'A' | 'B' | 'C' | 'D' | 'F';

interface GradeChipProps {
  grade: Grade | string;
  className?: string;
}

const gradeColors: Record<string, string> = {
  A: 'bg-[var(--grade-a)]/15 text-[var(--grade-a)] border-[var(--grade-a)]/30',
  B: 'bg-[var(--grade-b)]/15 text-[var(--grade-b)] border-[var(--grade-b)]/30',
  C: 'bg-[var(--grade-c)]/15 text-[var(--grade-c)] border-[var(--grade-c)]/30',
  D: 'bg-[var(--grade-d)]/15 text-[var(--grade-d)] border-[var(--grade-d)]/30',
  F: 'bg-[var(--grade-f)]/15 text-[var(--grade-f)] border-[var(--grade-f)]/30',
};

export function GradeChip({ grade, className }: GradeChipProps) {
  const normalized = grade.toUpperCase();
  const colorClass = gradeColors[normalized] ?? gradeColors['C'];

  return (
    <span
      className={cn(
        'inline-flex items-center justify-center rounded-md border px-2 py-0.5 text-xs font-bold',
        colorClass,
        className,
      )}
    >
      {normalized}
    </span>
  );
}
