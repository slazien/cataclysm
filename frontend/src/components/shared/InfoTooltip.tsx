'use client';

import { CircleHelp } from 'lucide-react';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
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
    <TooltipProvider delayDuration={200}>
      <Tooltip>
        <TooltipTrigger asChild>
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
        </TooltipTrigger>
        <TooltipContent side={side} sideOffset={6} className="max-w-xs text-xs leading-relaxed">
          {text}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
