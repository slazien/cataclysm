'use client';

import { Brain } from 'lucide-react';

interface QuickTipProps {
  drill: string;
}

export function QuickTip({ drill }: QuickTipProps) {
  return (
    <div
      className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-4"
      style={{ borderLeftWidth: '3px', borderLeftColor: 'var(--cata-accent)' }}
    >
      <div className="flex items-start gap-3">
        <Brain className="mt-0.5 h-5 w-5 shrink-0 text-[var(--cata-accent)]" />
        <div>
          <h3 className="mb-1 font-[family-name:var(--font-display)] text-xs font-bold uppercase tracking-widest text-[var(--cata-accent)]">
            Coach&apos;s Tip
          </h3>
          <p className="text-sm leading-relaxed text-[var(--text-secondary)]">{drill}</p>
        </div>
      </div>
    </div>
  );
}
