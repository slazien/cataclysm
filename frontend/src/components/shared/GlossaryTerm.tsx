'use client';

import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { glossary } from '@/lib/glossary';

interface GlossaryTermProps {
  term: string;
  children: React.ReactNode;
}

export function GlossaryTerm({ term, children }: GlossaryTermProps) {
  const definition = glossary[term];
  if (!definition) return <>{children}</>;

  return (
    <TooltipProvider delayDuration={300}>
      <Tooltip>
        <TooltipTrigger asChild>
          <span className="cursor-help border-b border-dotted border-[var(--text-muted)]">
            {children}
          </span>
        </TooltipTrigger>
        <TooltipContent className="max-w-xs text-sm">
          <p>{definition}</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
