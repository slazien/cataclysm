'use client';

import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { glossary } from '@/lib/glossary';
import { useSkillLevel } from '@/hooks/useSkillLevel';
import { useUnits } from '@/hooks/useUnits';

interface GlossaryTermProps {
  term: string;
  children: React.ReactNode;
}

export function GlossaryTerm({ term, children }: GlossaryTermProps) {
  const { isNovice, isAdvanced } = useSkillLevel();
  const { resolveSpeed } = useUnits();
  const entry = glossary[term];
  if (!entry) return <>{children}</>;

  const contentText = isNovice ? entry.noviceExplanation : entry.definition;
  const exampleText = entry.example ? resolveSpeed(entry.example) : '';

  // Advanced users: no underline, no tooltip — clean UI
  if (isAdvanced) return <>{children}</>;

  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          className={`inline cursor-help border-b border-dotted text-inherit ${isNovice ? 'border-[var(--cata-accent)]' : 'border-[var(--text-muted)]'}`}
        >
          {children}
        </button>
      </PopoverTrigger>
      <PopoverContent
        side="top"
        sideOffset={6}
        className="max-w-xs border-[var(--cata-border)] bg-[var(--bg-surface)] p-3 text-sm"
      >
        <p className="font-medium text-[var(--text-primary)]">
          {resolveSpeed(contentText)}
        </p>
        {isNovice && entry.example && (
          <p className="mt-1 text-xs text-[var(--text-secondary)] italic">
            Example: {exampleText}
          </p>
        )}
      </PopoverContent>
    </Popover>
  );
}
