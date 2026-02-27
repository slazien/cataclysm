'use client';

import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { glossary } from '@/lib/glossary';
import { useSkillLevel } from '@/hooks/useSkillLevel';

interface GlossaryTermProps {
  term: string;
  children: React.ReactNode;
}

export function GlossaryTerm({ term, children }: GlossaryTermProps) {
  const { isNovice, isAdvanced } = useSkillLevel();
  const entry = glossary[term];
  if (!entry) return <>{children}</>;

  // Advanced users: no underline, no tooltip — clean UI
  if (isAdvanced) return <>{children}</>;

  return (
    <TooltipProvider delayDuration={300}>
      <Tooltip>
        <TooltipTrigger asChild>
          <span
            className={`cursor-help border-b border-dotted ${isNovice ? 'border-[var(--cata-accent)]' : 'border-[var(--text-muted)]'}`}
          >
            {children}
          </span>
        </TooltipTrigger>
        <TooltipContent className="max-w-xs text-sm">
          <p className="font-medium">
            {isNovice ? entry.noviceExplanation : entry.definition}
          </p>
          {isNovice && entry.example && (
            <p className="mt-1 text-xs text-[var(--text-muted)] italic">
              Example: {entry.example}
            </p>
          )}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
