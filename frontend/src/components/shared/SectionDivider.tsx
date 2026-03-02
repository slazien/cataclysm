'use client';

import { cn } from '@/lib/utils';

export function SectionDivider({ className }: { className?: string }) {
  return (
    <div
      className={cn('h-px', className)}
      style={{
        background: 'linear-gradient(to right, var(--cata-accent), transparent 60%)',
      }}
    />
  );
}
