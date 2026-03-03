'use client';

import { Sparkles } from 'lucide-react';
import { cn } from '@/lib/utils';

type AiInsightMode = 'compact' | 'card' | 'inline';

interface AiInsightProps {
  children: React.ReactNode;
  mode?: AiInsightMode;
  className?: string;
  /** Optional badge text (e.g. time saved) shown to the right */
  badge?: string;
}

export function AiInsight({ children, mode = 'card', className, badge }: AiInsightProps) {
  if (mode === 'compact') {
    return (
      <span
        className={cn(
          'inline-flex items-center gap-1.5 text-sm text-[var(--ai-icon)]',
          className,
        )}
      >
        <span className="text-xs" role="img" aria-label="AI">&#x1F916;</span>
        {children}
      </span>
    );
  }

  if (mode === 'inline') {
    return (
      <div
        className={cn(
          'flex items-start gap-2 rounded-md bg-[var(--ai-bg)] px-3 py-2',
          className,
        )}
      >
        <Sparkles className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[var(--ai-icon)]" />
        <div className="min-w-0 flex-1 text-xs leading-relaxed text-[var(--text-secondary)]">
          {children}
        </div>
        {badge && (
          <span className="shrink-0 rounded-full bg-[var(--ai-icon)]/10 px-2 py-0.5 text-[10px] font-semibold tabular-nums text-[var(--ai-icon)]">
            {badge}
          </span>
        )}
      </div>
    );
  }

  return (
    <div
      className={cn(
        'relative rounded-lg border border-transparent p-4',
        'bg-[var(--ai-bg)]',
        className,
      )}
      style={{
        borderImage: 'linear-gradient(135deg, #6366f1, #a855f7) 1',
      }}
    >
      {/* Gradient border via pseudo-element for rounded corners */}
      <div
        className="pointer-events-none absolute inset-0 rounded-lg"
        style={{
          padding: '1px',
          background: 'linear-gradient(135deg, #6366f1, #a855f7)',
          mask: 'linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0)',
          maskComposite: 'exclude',
          WebkitMaskComposite: 'xor',
        }}
      />
      <div className="flex items-start gap-2">
        <span className="mt-0.5 text-sm text-[var(--ai-icon)]" role="img" aria-label="AI">
          &#x1F916;
        </span>
        <div className="min-w-0 flex-1 text-sm text-[var(--text-primary)]">{children}</div>
      </div>
    </div>
  );
}
