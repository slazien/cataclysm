'use client';

import { CircleHelp } from 'lucide-react';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { helpContent } from '@/lib/help-content';
import { cn } from '@/lib/utils';

interface InfoTooltipProps {
  helpKey: string;
  /** Override the help-content dictionary with custom text */
  content?: string;
  side?: 'top' | 'right' | 'bottom' | 'left';
  className?: string;
}

export function InfoTooltip({ helpKey, content, side = 'top', className }: InfoTooltipProps) {
  const text = content ?? helpContent[helpKey];
  if (!text) return null;

  const ariaLabel = `More info about ${helpKey.replace(/[.-]/g, ' ')}`;

  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          className={cn(
            'inline-flex shrink-0 items-center justify-center opacity-40 transition-opacity hover:opacity-80 focus-visible:opacity-80 focus-visible:ring-1 focus-visible:ring-[var(--text-muted)]',
            className,
          )}
          aria-label={ariaLabel}
        >
          <CircleHelp className="h-3.5 w-3.5" />
        </button>
      </PopoverTrigger>
      <PopoverContent
        side={side}
        sideOffset={6}
        className="w-auto max-w-xs border-0 bg-foreground px-3 py-1.5 text-xs leading-relaxed text-background"
      >
        {text}
      </PopoverContent>
    </Popover>
  );
}
