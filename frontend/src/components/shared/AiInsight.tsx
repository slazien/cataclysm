'use client';

import { cn } from '@/lib/utils';

type AiInsightMode = 'compact' | 'card';

interface AiInsightProps {
  children: React.ReactNode;
  mode?: AiInsightMode;
  className?: string;
}

export function AiInsight({ children, mode = 'card', className }: AiInsightProps) {
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
